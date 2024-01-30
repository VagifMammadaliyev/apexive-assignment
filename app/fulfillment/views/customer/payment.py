from decimal import Decimal

from django.shortcuts import get_list_or_404, get_object_or_404
from django.db.models import Q
from django.http import Http404
from rest_framework import generics, status, views
from django.db import transaction as db_transaction
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django_filters.rest_framework import DjangoFilterBackend
from core.models import Currency

from domain.services import (
    complete_payments,
    get_exposable_customer_payments,
    make_payment_partial,
    prepare_balance_add_form,
    get_invoice,
    merge_invoices,
    get_user_transactions as get_transactions,
    prepare_transaction_for_courier_order,
    get_serialized_multiple_invoice,
    normalize_transactions,
    transactions_are_mergable,
    merge_transactions,
)
from domain.exceptions.payment import PaymentError
from core.converter import Converter
from customer.serializers import BalanceSerializer
from fulfillment.models import Transaction, Shipment
from fulfillment.serializers.customer import (
    ArchiveSerializer,
    BulkArchiveSerializer,
    PaymentSerializer,
    UlduzumWithShipmentSerializer,
    UlduzumIdenticalCodeSerializer,
    CurrencySerializer,
)
from fulfillment.filters import PaymentFilter
from fulfillment.views.utils import filter_by_archive_status
from paypal.client import PayPalClient
from paytr.client import PayTR
from ulduzum.client import UlduzumClient
from ulduzum.exceptions import UlduzumException
from core.converter import Converter


@api_view(["POST"])
@db_transaction.atomic
def payment_view(request):
    transactions = get_transactions(
        request.user,
        request.data.get("identifiers", []),
        request.data.get("invoice_numbers", []),
    )

    nice_transactions = []
    for transaction in transactions:
        if (
            transaction.object_type_id
            and transaction.object_type.model == "courierorder"
        ):
            merged_transaction = prepare_transaction_for_courier_order(
                transaction, Transaction.BALANCE
            )
            nice_transactions.append(merged_transaction)
        else:
            nice_transactions.append(transaction)

    transaction = complete_payments(
        nice_transactions,
        override_type=Transaction.BALANCE,
    )

    return Response(
        {
            "active_balance": BalanceSerializer(
                request.user.as_customer.active_balance
            ).data,
            "payment": PaymentSerializer(transaction).data,
        },
        status=status.HTTP_200_OK,
    )


class PaymentListApiView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = PaymentFilter

    def get_queryset(self):
        transactions = get_exposable_customer_payments(self.request.user)
        transactions = filter_by_archive_status(transactions, self.request)

        return transactions


class PaymentDetailApiView(generics.RetrieveAPIView):
    serializer_class = PaymentSerializer
    lookup_field = "invoice_number"
    lookup_url_kwarg = "invoice_number"

    def get_queryset(self):
        return get_exposable_customer_payments(self.request.user)


@api_view(["GET"])
def payment_invoice_view(request, invoice_number):
    transaction = get_object_or_404(
        request.user.transactions.filter(is_deleted=False),
        invoice_number=invoice_number,
    )

    if transaction.purpose == Transaction.MERGED:
        # Must return merged invoice
        invoice = merge_invoices(
            request.user,
            [get_invoice(t.related_object) for t in transaction.children.all()],
        )
        return Response(invoice.serialize())

    related_object = transaction.related_object
    if not related_object:
        raise Http404

    invoice = get_invoice(related_object).serialize()

    if not invoice:
        raise Http404

    return Response(invoice)


class MakePaymentPartialApiView(views.APIView):
    @db_transaction.atomic
    def post(self, request, *args, **kwargs):
        payment_service = self.kwargs.get("payment_service")
        if payment_service not in Transaction.FLAT_PAYMENT_SERVICES:
            raise Http404

        identifier = request.data.get("identifier", None)
        identifiers = request.data.get("identifiers", [])
        invoice_number = request.data.get("invoice_number", None)
        invoice_numbers = request.data.get("invoice_numbers", [])

        if identifier:
            identifiers += [identifier]

        if invoice_number:
            invoice_numbers += [invoice_number]

        transactions = []
        if identifiers:
            transactions = get_transactions(request.user, identifiers=identifiers)
        elif invoice_numbers:
            transactions = get_transactions(
                request.user, invoice_numbers=invoice_numbers
            )

        if not transactions:
            raise PaymentError

        nice_transactions = []

        for transaction in transactions:
            if (
                transaction.object_type_id
                and transaction.object_type.model == "courierorder"
            ):
                nice_transactions.append(
                    prepare_transaction_for_courier_order(transaction, Transaction.CARD)
                )
            else:
                nice_transactions.append(transaction)

        if len(nice_transactions) == 1:
            transaction = nice_transactions[0]
        elif nice_transactions:
            mergable, type_, currency_id, user_id = transactions_are_mergable(
                nice_transactions, override_type=Transaction.CARD
            )

            if not mergable:
                nice_transactions = normalize_transactions(
                    nice_transactions,
                    to_currency=self.request.user.active_balance.currency,
                )

                mergable, type_, currency_id, user_id = transactions_are_mergable(
                    nice_transactions, override_type=Transaction.CARD
                )

                if not mergable:
                    raise PaymentError

            transaction = merge_transactions(
                user_id, type_, currency_id, nice_transactions
            )

        else:
            raise PaymentError

        transaction = make_payment_partial(transaction, payment_service)

        data = {}

        status_code = 200
        if payment_service == Transaction.CYBERSOURCE_SERVICE:
            data = prepare_balance_add_form(request.user, transaction=transaction)
        elif payment_service == Transaction.PAYPAL_SERVICE:
            order_id, approve_link = PayPalClient().create_order(
                request, transaction=transaction
            )
            data = {"order_id": order_id, "approve_link": approve_link}
        elif payment_service == Transaction.PAYTR_SERVICE:
            if transaction.currency.code != "TRY":
                try_currency = Currency.objects.get(code="TRY")
                transaction.amount = Converter.convert(
                    transaction.amount, transaction.currency.code, "TRY"
                )
                transaction.currency = try_currency
            client = PayTR(request=request, transaction=transaction)
            token_response = client.generate_token()
            if isinstance(token_response, dict):
                if token_response["status"] == "success":
                    data = {"token": token_response["token"], "error": None}
                else:
                    data = {"token": None, "error": token_response["reason"]}
                    status_code = 500
            else:
                data = {"token": None, "error": "PayTR response was not valid"}
                status_code = 500
        return Response(data, status=status_code)


@api_view(["GET"])
def multiple_payment_invoice_view(request):
    identifiers = request.query_params.getlist("identifier")
    invoice_numbers = request.query_params.getlist("invoice_number")

    transactions = Transaction.objects.filter(
        ~Q(purpose=Transaction.MERGED),
        Q(invoice_number__in=invoice_numbers)
        | Q(related_object_identifier__in=identifiers),
        user=request.user,
        is_deleted=False,
        completed=False,
    )

    instances = [t.related_object for t in transactions]

    return Response(
        get_serialized_multiple_invoice(request.user.active_balance, instances)
    )


@api_view(["POST"])
def payment_archive_view(request, invoice_number):
    transaction = get_object_or_404(
        Transaction,
        invoice_number=invoice_number,
        user=request.user,
    )

    serializer = ArchiveSerializer(data={"instance": transaction})
    serializer.is_valid(raise_exception=True)
    serializer.perform_archive()

    return Response(PaymentSerializer(transaction).data, status=status.HTTP_200_OK)


@api_view(["POST"])
def payment_bulk_archive_view(request):
    serializer = BulkArchiveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    payments = get_list_or_404(
        Transaction, invoice_number__in=serializer.validated_data["ids"]
    )
    serializer.perform_archive(payments)

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
def ulduzum_check_view(request):
    serializer = UlduzumWithShipmentSerializer(
        data=request.data, context={"user_id": request.user.id}
    )
    serializer.is_valid(raise_exception=True)

    identical_code = serializer.validated_data["identical_code"]
    shipment = serializer.validated_data["shipment"]

    client = UlduzumClient(identical_code=identical_code, test_mode=False)
    data = client.calculate_for_shipment(shipment)

    discount_data = data

    return Response(
        {
            "cashback_amount": str(
                Converter.convert(
                    Decimal(str(discount_data["discount_amount"])),
                    "AZN",
                    request.user.active_balance.currency.code,
                )
            ),
            "cashback_currency": CurrencySerializer(
                request.user.active_balance.currency
            ).data,
        }
    )


@api_view(["POST"])
def ulduzum_cancel_view(request):
    shipment = request.user.shipments.filter(number=request.data.get("number"))
    if shipment:
        identical_code = shipment.extra.get("ulduzum_data", {}).get(
            "identical_code", ""
        )
        client = UlduzumClient(identical_code=identical_code, test_mode=False)
        try:
            data = client.cancel_for_shipment(shipment=shipment)
        except UlduzumException:
            pass

    return Response({"status": "OK"})
