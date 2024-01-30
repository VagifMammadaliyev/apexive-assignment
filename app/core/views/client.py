from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from django.utils.translation import get_language

from domain.conf import Configuration
from core.models import Country, Currency, MobileOperator
from core.serializers.client import (
    PhoneCodeSerializer,
    CurrencySerializer,
)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@authentication_classes([])
def phone_prefixes_view(request):
    operators = MobileOperator.objects.select_related("country")

    return Response(
        [operator.full_prefix for operator in operators],
        status=status.HTTP_200_OK,
    )


class CurrencyApiView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    pagination_class = None
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer


@api_view(["GET"])
def ordering_info_view(request):
    conf = Configuration()._conf  # get the real configuration object
    return Response(
        {
            # "commission_percentage": conf.order_commission_percentage,
            # "minimum_order_commission_price": conf.minimum_order_commission_price,
            # "minimun_order_commission_price_currency": CurrencySerializer(
            #     conf.minimum_order_commission_price_currency
            # ).data,
            "commission_info_text": conf.order_commission_info_text,
        }
    )
