import math

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.db.models import OuterRef, Exists, Prefetch, Q, Subquery, F
from rest_framework import generics, permissions, status, views
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from domain.services import get_additional_services
from domain.utils import TariffCalculator, ShipmentDimensions
from core.serializers.client import (
    CurrencySerializer,
    CitySerializer,
    CountrySerializer,
)
from core.models import Country, City
from core.filters import CityFilter, CountryFilter
from fulfillment.models import (
    AdditionalService,
    Address,
    ProductCategory,
    ProductType,
    Status,
    Tariff,
    Warehouse,
    Transaction,
    CourierRegion,
    CourierTariff,
    UserCountryLog,
    OrderedProduct,
    Shop,
)
from fulfillment.serializers.common import (
    AdditionalServiceSerializer,
    AddressSerializer,
    ProductCategorySerializer,
    ProductTypeExtraCompactSerializer,
    StatusSerializer,
    TariffCompactSerializer,
    TariffCalculatorSerializer,
    WarehouseReadSerializer,
    CountryDetailedSerializer,
    CountryWithMinTariffSerializer,
    CountryWithCurrencySerializer,
    CountryWithAddressSerializer,
    CourierRegionSerializer,
    CourierTariffSerializer,
    OrderProductReadSerializer,
    ShopSerializer,
    get_from_city_defaults_for_calculator,
    get_to_city_defaults_for_calculator,
    get_from_country_defaults_for_calculator,
    get_to_country_defaults_for_calculator,
)
from fulfillment.filters import (
    AdditionalServiceFilter,
    OrderedProductFilter,
    WarehouseFilter,
    CourierRegionFilter,
)
from fulfillment.pagination import DynamicPagination


class WarehouseApiView(generics.ListAPIView):
    serializer_class = WarehouseReadSerializer
    queryset = Warehouse.objects.filter(
        Q(country__is_base=True) | Q(city__country__is_base=True),  # is_universal=False
    )
    pagination_class = None
    filter_backends = [DjangoFilterBackend]
    filterset_class = WarehouseFilter


class OrderStatusListApiView(generics.ListAPIView):
    pagination_class = None
    serializer_class = StatusSerializer
    queryset = Status.objects.filter(type=Status.ORDER_TYPE)


class PackageStatusListApiView(generics.ListAPIView):
    pagination_class = None
    serializer_class = StatusSerializer
    queryset = Status.objects.filter(type=Status.PACKAGE_TYPE)


class ShipmentStatusListApiView(generics.ListAPIView):
    pagination_class = None
    serializer_class = StatusSerializer
    queryset = Status.objects.filter(type=Status.SHIPMENT_TYPE)


class TicketStatusListApiView(generics.ListAPIView):
    pagination_class = None
    serializer_class = StatusSerializer
    queryset = Status.objects.filter(type=Status.TICKET_TYPE).exclude(
        codename="deleted"
    )


class CourierOrderListApiView(generics.ListAPIView):
    pagination_class = None
    serializer_class = StatusSerializer
    queryset = Status.objects.filter(type=Status.COURIER_ORDER_TYPE)


class TariffCalculatorApiView(views.APIView):
    throttle_scope = "light"
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        force_from_city = "force" in request.query_params

        calculator_data = TariffCalculatorSerializer(
            data=request.data, context={"force_from_city": force_from_city}
        )
        calculator_data.is_valid(raise_exception=True)

        from_country = calculator_data.validated_data.get("from_country")
        from_city = calculator_data.validated_data.get("from_city")

        to_country = calculator_data.validated_data.get("to_country")
        to_city = calculator_data.validated_data.get("to_city")
        is_dangerous = calculator_data.validated_data["is_dangerous"]
        weight = calculator_data.validated_data["weight"]
        dimensions = calculator_data.validated_data.get("dimensions")

        shipment_dimensions = None
        if dimensions:
            shipment_dimensions = ShipmentDimensions(
                dimensions["height"], dimensions["width"], dimensions["length"]
            )

        if from_country and to_country:
            source_id = from_country.id
            destination_id = to_country.id
            is_by_country = True
        elif from_city and to_city:
            source_id = from_city.id
            destination_id = to_city.id
            is_by_country = False
        else:  # Hardly possible
            raise Exception("Tariff calculator serializer failed to validate data")

        calculator = TariffCalculator()
        price, tariff = calculator.calculate(
            weight=weight,
            dimensions=shipment_dimensions,
            source_id=source_id,
            destination_id=destination_id,
            is_dangerous=is_dangerous,
            is_by_country=is_by_country,
        )

        return Response(
            {
                "price": str(price) if price else price,
                "currency": tariff and CurrencySerializer(tariff.price_currency).data,
            },
            status=status.HTTP_200_OK,
        )


class ProductCategoryListApiView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    pagination_class = None
    queryset = ProductCategory.objects.filter(is_active=True).order_by(
        "needs_description"
    )
    serializer_class = ProductCategorySerializer


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@authentication_classes([])
def product_types_view(request, category_pk):
    return Response(
        ProductTypeExtraCompactSerializer(
            ProductType.objects.filter(category__id=category_pk, is_active=True),
            many=True,
        ).data,
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def address_by_country_view(request, country_pk):
    return Response(
        AddressSerializer(
            Address.objects.filter(country__pk=country_pk, country__is_active=True),
            many=True,
            context={"request": request},
        ).data,
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@authentication_classes([])
def tariff_by_country_view(request, country_pk):
    return Response(
        TariffCompactSerializer(
            Tariff.objects.filter(
                source_city__country_id=country_pk,
                source_city__country__is_active=True,
            ).order_by("is_dangerous", "min_weight"),
            many=True,
        ).data,
        status=status.HTTP_200_OK,
    )


available_countries = Country.objects.filter(
    Q(is_active=True) | Q(is_base=True)
).order_by("display_order")


class CountryListApiView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    queryset = available_countries
    filter_backends = [DjangoFilterBackend]
    filterset_class = CountryFilter

    def get_serializer_class(self, *args, **kwargs):
        if "minTariff" in self.request.query_params:
            return CountryWithMinTariffSerializer
        if "address" in self.request.query_params:
            return CountryWithAddressSerializer
        return CountryWithCurrencySerializer

    def get_queryset(self):
        tariff_field = self.request.query_params.get("tariff")

        if tariff_field == "source":
            countries = get_from_country_defaults_for_calculator()
        elif tariff_field == "dest":
            countries = get_to_country_defaults_for_calculator()
        else:
            countries = super().get_queryset()

        if self.request.user.is_authenticated:
            if "address" in self.request.query_params:
                # Order countries by user preference
                countries = countries.annotate(
                    preference=Subquery(
                        self.request.user.country_logs.filter(
                            country_id=OuterRef("pk")
                        ).values("updated_at")[:1]
                    )
                ).order_by(F("preference").desc(nulls_last=True), "display_order")

        return countries.prefetch_related(
            Prefetch("warehouses", to_attr="prefetched_warehouses")
        ).order_by("display_order")


class CountryRetrieveApiVIew(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    queryset = available_countries
    serializer_class = CountryDetailedSerializer


class AdditionalServiceListApiView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    queryset = AdditionalService.objects.order_by("price").select_related(
        "price_currency"
    )
    pagination_class = None
    serializer_class = AdditionalServiceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = AdditionalServiceFilter

    def get_queryset(self):
        return get_additional_services(
            country_id=self.request.query_params.get("country"),
            services=super().get_queryset(),
        )


class CityListApiView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    queryset = City.objects.all()
    serializer_class = CitySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CityFilter

    def get_queryset(self):
        tariff_field = self.request.query_params.get("tariff")

        if tariff_field == "source":
            return get_from_city_defaults_for_calculator()

        elif tariff_field == "dest":
            return get_to_city_defaults_for_calculator()

        return super().get_queryset()

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)


class CourierRegionListApiView(generics.ListAPIView):
    pagination_class = None
    queryset = CourierRegion.objects.order_by("title")
    serializer_class = CourierRegionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = CourierRegionFilter


class CourierTariffListApiView(generics.ListAPIView):
    pagination_class = None
    serializer_class = CourierTariffSerializer

    def get_region(self):
        return get_object_or_404(CourierRegion, pk=self.kwargs.get("pk"))

    def get_queryset(self):
        region = self.get_region()
        if region.area_id:
            return region.area.tariffs.all()
        raise Http404


class OrderedProductListApiView(generics.ListAPIView):
    pagination_class = None
    permission_classes = [permissions.AllowAny]
    queryset = OrderedProduct.objects.filter(is_visible=True).order_by("-id")
    pagination_class = DynamicPagination
    serializer_class = OrderProductReadSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = OrderedProductFilter


class ShopListApiView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    pagination_class = DynamicPagination
    queryset = Shop.objects.filter(is_active=True)
    serializer_class = ShopSerializer
