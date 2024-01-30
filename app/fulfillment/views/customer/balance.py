from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from core.converter import Converter
from core.models import Currency
from domain.exceptions.customer import CantTopUpBalanceError
from domain.services import (
    check_if_customer_can_top_up_balance,
    prepare_balance_add_form,
)
from fulfillment.models import Transaction
from fulfillment.serializers.customer import BalanceAddSerializer
from paypal.client import PayPalClient
from paytr.client import PayTR
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from customer.serializers import BalanceSerializer


@api_view(["GET"])
def balance_view(request):
    balance = request.user.as_customer.active_balance
    return Response(BalanceSerializer(balance).data, status=status.HTTP_200_OK)


@api_view(["GET"])
def cybersource_payment_form(request):
    serializer = BalanceAddSerializer(
        data={
            "amount": request.query_params.get("amount"),
            "currency": request.query_params.get("currency_code"),
        }
    )
    serializer.is_valid(raise_exception=True)

    return Response(
        prepare_balance_add_form(
            request.user,
            serializer.validated_data["amount"],
            serializer.validated_data["currency"],
        )
    )


@api_view(["POST"])
def set_up_paypal_transaction_view(request):
    if not check_if_customer_can_top_up_balance(
        request.user.as_customer, Transaction.PAYPAL_SERVICE
    ):
        raise CantTopUpBalanceError

    serializer = BalanceAddSerializer(
        data={
            "amount": request.data.get("amount"),
            "currency": request.data.get("currency_code"),
        }
    )
    serializer.is_valid(raise_exception=True)

    order_id, approve_link = PayPalClient().create_order(
        request,
        serializer.validated_data["amount"],
        serializer.validated_data["currency"],
    )
    return Response(
        {"order_id": order_id, "approve_link": approve_link},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def set_up_paytr_transaction_view(request):
    if not check_if_customer_can_top_up_balance(
        request.user.as_customer, Transaction.PAYTR_SERVICE
    ):
        raise CantTopUpBalanceError

    serializer = BalanceAddSerializer(
        data={
            "amount": request.data.get("amount"),
            "currency": request.data.get("currency_code"),
        }
    )
    serializer.is_valid(raise_exception=True)
    amount = Converter.convert(
        serializer.validated_data["amount"],
        serializer.validated_data["currency"].code,
        "TRY",
    )

    transaction = Transaction.objects.create(
        user=request.user,
        currency=Currency.objects.get(code="TRY"),
        amount=amount,
        purpose=Transaction.BALANCE_INCREASE,
        type=Transaction.CARD,
        payment_service=Transaction.PAYTR_SERVICE,
    )
    client = PayTR(request=request, transaction=transaction)
    token_response = client.generate_token()
    if isinstance(token_response, dict):
        if token_response["status"] == "success":
            return Response({"token": token_response["token"], "error": None})
        else:
            return Response({"token": None, "error": token_response["reason"]})
    return Response({"token": None, "error": "PayTR response was not valid"})


# TODO: Remove this later
def test_cyber_add_balance_view(request):
    if settings.PROD:
        raise Http404

    from core.models import Currency

    return render(
        request,
        "balance_cyber.html",
        {
            "form_data": prepare_balance_add_form(
                request.user,
                request.GET.get("amount", "200"),
                Currency.objects.get(code=request.GET.get("currency_code", "USD")),
            ),
        },
    )
