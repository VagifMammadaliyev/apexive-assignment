from decimal import Decimal

from rest_framework import status, views, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view

from domain.services import (
    get_exposable_customer_payments,
    get_left_promo_code_benefits,
    get_consumers_for_promo_code,
)
from domain.utils.autofill import AutoFiller
from domain.conf import Configuration
from ontime.utils import parse_int
from core.models import Country, Currency
from fulfillment.views.utils import filter_by_archive_status
from fulfillment.serializers.common import TransactionSerializer
from fulfillment.serializers.customer import (
    PackageReadSerializer,
    OrderReadSerializer,
    ShipmentReadSerializer,
    PaymentSerializer,
    CurrencySerializer,
)
from fulfillment.models import Package, Order, Shipment, Transaction


@api_view(["GET"])
def dashboard_view(request):
    customer = request.user.as_customer
    limit = parse_int(request.query_params.get("limit")) or 5
    shipments = filter_by_archive_status(customer.shipments.all(), request)
    packages = filter_by_archive_status(customer.packages.all(), request)
    orders = filter_by_archive_status(customer.orders.all(), request)
    payments = filter_by_archive_status(
        get_exposable_customer_payments(customer), request
    )

    return Response(
        {
            "packages": PackageReadSerializer(
                packages.filter(shipment__isnull=True)
                .order_by("-updated_at")
                .select_related()[:limit],
                many=True,
                context={"request": request},
            ).data,
            "orders": OrderReadSerializer(
                orders.order_by("-updated_at").select_related()[:limit],
                many=True,
                context={"request": request},
            ).data,
            "shipments": ShipmentReadSerializer(
                shipments.order_by("-updated_at").select_related()[:limit],
                many=True,
                context={"request": request},
            ).data,
            "payments": PaymentSerializer(
                payments[:limit],
                many=True,
                context={"request": request},
            ).data,
        },
        status=status.HTTP_200_OK,
    )


class ProductAutofillApiView(views.APIView):
    def get(self, request, *args, **kwargs):
        url = self.request.query_params.get("product_url")
        autofiller = AutoFiller(product_url=url)
        data, status = autofiller.fetch()

        return Response(data, status=status)


class PromoCodeDataView(views.APIView):
    def get_promo_code_data(self, user):
        cashback_percentage = Configuration().invite_friend_cashback_percentage
        promo_code = getattr(user, "promo_code", None)
        usd_currency_serialized = CurrencySerializer(
            instance=Currency.objects.get(code="USD")
        ).data
        if promo_code or user.registered_promo_code_id:
            value = promo_code and promo_code.value
            benefit_count = get_left_promo_code_benefits(user)
            friends = []  # list of friends of this user who got cashback
            if promo_code:
                friends = get_consumers_for_promo_code(promo_code)
            return {
                "promo_code": value,
                "registered_promo_code": user.registered_promo_code_id
                and user.registered_promo_code.value,
                "can_get_cashbacks": benefit_count > 0,
                "left_cashback_amount": benefit_count,
                "cashback_percentage": str(cashback_percentage),
                "friends": [
                    {
                        "full_name": consumer.full_name,
                        "total_cashback": str(
                            round(consumer.total_cashback_amount or Decimal("0"), 2)
                        ),
                        "total_cashback_currency": usd_currency_serialized,
                        "used_cashbacks_count": consumer.used_benefits,
                    }
                    for consumer in friends
                ],
            }
        return None

    def get(self, *args, **kwargs):
        data = self.get_promo_code_data(self.request.user)
        return Response(data)
