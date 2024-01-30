from django.db.models import Q, OuterRef, Exists
from django.utils.translation import ugettext as _
from rest_framework import serializers

from ontime import messages as msg
from core.models import Country, City, Currency
from core.converter import Converter
from core.serializers.client import (
    CurrencySerializer,
    CountrySerializer,
    CountryWithCurrencySerializer,
    CitySerializer,
)
from fulfillment.models import (
    AdditionalService,
    AddressField,
    Address,
    Warehouse,
    Status,
    StatusEvent,
    Tariff,
    ProductCategory,
    ProductType,
    Transaction,
    CourierRegion,
    CourierTariff,
    OrderedProduct,
    Shop,
)


class WarehouseReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = [
            "id",
            "title",
            "address",
            "does_consider_volume",
            "does_serve_dangerous_packages",
            "is_universal",
        ]


class StatusSerializer(serializers.ModelSerializer):
    hex_color = serializers.SerializerMethodField()
    icon = serializers.SerializerMethodField()
    is_default = serializers.SerializerMethodField()

    class Meta:
        model = Status
        fields = ["id", "display_name", "hex_color", "icon", "is_default"]

    def get_hex_color(self, status):
        return status.extra.get("color", "#00631b")

    def get_icon(self, status):
        return status.extra.get("icon", "")

    def get_is_default(self, status):
        return status.type == Status.ORDER_TYPE and status.codename in [
            "processing",
            "paid",
        ]


class NextPrevStatusSerializer(StatusSerializer):
    next = StatusSerializer(read_only=True)
    prev = StatusSerializer(read_only=True)

    class Meta(StatusSerializer.Meta):
        fields = StatusSerializer.Meta.fields + ["next", "prev"]


class StatusEventSerializer(serializers.ModelSerializer):
    status = StatusSerializer(source="to_status", read_only=True)
    # to_status = StatusSerializer(read_only=True)

    class Meta:
        model = StatusEvent
        fields = ["status", "message", "timestamp"]


def get_from_city_defaults_for_calculator(country_id=None):
    country_query = Q(country_id=country_id) if country_id else Q()
    warehouses = Warehouse.objects.filter(city=OuterRef("pk")).values("pk")
    return City.objects.annotate(warehouse_exists=Exists(warehouses)).filter(
        country_query, country__is_active=True, warehouse_exists=True
    )


def get_from_country_defaults_for_calculator():
    warehouses = Warehouse.objects.filter(city__country=OuterRef("pk")).values("pk")
    return Country.objects.annotate(warehouse_exists=Exists(warehouses)).filter(
        is_active=True, warehouse_exists=True
    )


def get_to_city_defaults_for_calculator(country_id=None):
    country_query = Q(country_id=country_id) if country_id else Q()
    warehouses = Warehouse.objects.filter(city=OuterRef("pk")).values("pk")
    return City.objects.annotate(warehouse_exists=Exists(warehouses)).filter(
        country_query, country__is_base=True, warehouse_exists=True
    )


def get_to_country_defaults_for_calculator():
    warehouses = Warehouse.objects.filter(city__country=OuterRef("pk")).values("pk")
    return Country.objects.annotate(warehouse_exists=Exists(warehouses)).filter(
        is_base=True, warehouse_exists=True
    )


class ShipmentDimensionsSerializer(serializers.Serializer):
    height = serializers.DecimalField(max_digits=9, decimal_places=2)
    width = serializers.DecimalField(max_digits=9, decimal_places=2)
    length = serializers.DecimalField(max_digits=9, decimal_places=2)


class TariffCalculatorSerializer(serializers.Serializer):
    from_country = serializers.PrimaryKeyRelatedField(
        queryset=get_from_country_defaults_for_calculator(), required=False
    )
    to_country = serializers.PrimaryKeyRelatedField(
        queryset=get_to_country_defaults_for_calculator(), required=False
    )
    from_city = serializers.PrimaryKeyRelatedField(
        queryset=get_from_city_defaults_for_calculator(), required=False
    )
    to_city = serializers.PrimaryKeyRelatedField(
        queryset=get_to_city_defaults_for_calculator(), required=False
    )
    dimensions = ShipmentDimensionsSerializer(required=False)
    is_dangerous = serializers.BooleanField(default=False)
    weight = serializers.DecimalField(max_digits=9, decimal_places=4)

    def validate(self, data):
        from_city = data.get("from_city")
        to_city = data.get("to_city")

        from_country = data.get("from_country")
        to_country = data.get("to_country")

        # Try to take any possible value for from city parameter,
        # because client doesn't want to select from city.
        force_from_city = self.context.get("force_from_city", False)
        if not from_city and force_from_city:
            from_city = get_from_city_defaults_for_calculator(
                country_id=from_country.id
            ).first()

        city_error = {
            "from_city": msg.MUST_BE_GIVEN_WITH_DEST_CITY,
            "to_city": msg.MUST_BE_GIVEN_WITH_SOURCE_CITY,
        }

        if not any([from_city, from_country, to_city, to_country]):
            raise serializers.ValidationError(city_error)

        if (from_city and not to_city) or (to_city and not from_city):
            raise serializers.ValidationError(city_error)

        if (from_country and not to_country) or (to_country and not from_country):
            raise serializers.ValidationError(
                {
                    "from_country": msg.MUST_BE_GIVEN_WITH_DEST_COUNTRY,
                    "to_country": msg.MUST_BE_GIVEN_WITH_SOURCE_COUNTRY,
                }
            )

        return data


class TariffCompactSerializer(serializers.ModelSerializer):
    price_currency = CurrencySerializer(read_only=True)
    source_city = CitySerializer(read_only=True)
    destination_city = CitySerializer(read_only=True)
    destination_country = CountrySerializer(
        read_only=True, source="destination_city.country"
    )

    class Meta:
        model = Tariff
        fields = [
            "title",
            "source_city",
            "destination_country",
            "destination_city",
            "price",
            "discounted_price",
            "price_currency",
            "min_weight",
            "max_weight",
            "is_per_kg",
            "is_dangerous",
        ]


class TariffByCountrySerializer(CountrySerializer):
    tariffs = serializers.SerializerMethodField()

    class Meta(CountrySerializer.Meta):
        fields = CountrySerializer.Meta.fields + ["tariffs"]

    def get_tariffs(self, country):
        return TariffCompactSerializer(
            country.tariffs.order_by("is_dangerous", "min_weight"), many=True
        ).data


class ProductCategorySerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)

    class Meta:
        model = ProductCategory
        fields = ["id", "name", "country", "needs_description"]


class ProductCategoryCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ["id", "name", "needs_description"]


class ProductTypeSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)

    class Meta:
        model = ProductType
        fields = ["id", "name", "category"]


class ProductTypeExtraCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductType
        fields = ["id", "name"]


class ProductTypeCompactSerializer(ProductTypeSerializer):
    category = ProductCategoryCompactSerializer(read_only=True)


class TransactionSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    type = serializers.CharField(source="get_type_display", read_only=True)
    purpose = serializers.CharField(source="get_purpose_display", read_only=True)

    class Meta:
        model = Transaction
        fields = ["amount", "currency", "purpose", "type", "created_at"]


class AddressFieldSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField()

    class Meta:
        model = AddressField
        fields = ["name", "value"]

    def get_value(self, field):
        request = self.context.get("request")
        to_append = []

        if field.append_user_full_name:
            full_name = ""
            if request.user.is_authenticated:
                full_name = request.user.full_name
                to_append.append(full_name)

        if field.append_client_code:
            client_code = ""
            if request.user.is_authenticated:
                client_code = request.user.client_code
                to_append.append(client_code)

        if to_append:
            to_append = " ".join(to_append)
            field_value = "%s %s" % (field.value, to_append)
            return field_value.strip()

        return field.value


class AddressSerializer(serializers.ModelSerializer):
    fields = AddressFieldSerializer(many=True, read_only=True)

    class Meta:
        model = Address
        fields = ["id", "fields"]


class CountryWithMinTariffSerializer(CountryWithCurrencySerializer):
    min_tariff = serializers.SerializerMethodField()

    class Meta(CountryWithCurrencySerializer.Meta):
        fields = CountryWithCurrencySerializer.Meta.fields + ["min_tariff"]

    def get_min_tariff(self, country):
        min_tariff = (
            Tariff.objects.filter(source_city__country=country)
            .order_by("discounted_price")
            .first()
        )

        if min_tariff:
            return {
                "title": msg.MIN_TARIFF_FMT
                % {
                    "price": str(min_tariff.active_price),
                    "currency": min_tariff.price_currency.symbol,
                },
                "price": str(min_tariff.active_price),
                "currency": CurrencySerializer(min_tariff.price_currency).data,
            }

        return None


class CountryWithAddressSerializer(CountryWithMinTariffSerializer):
    address = serializers.SerializerMethodField()

    class Meta(CountryWithMinTariffSerializer.Meta):
        fields = CountryWithMinTariffSerializer.Meta.fields + ["address"]

    def get_address(self, country):
        from fulfillment.serializers.common import AddressSerializer

        address = country.addresses.last()

        return AddressSerializer(address, context=self.context).data


class CountryDetailedSerializer(CountryWithMinTariffSerializer):
    tariffs = serializers.SerializerMethodField()
    addresses = AddressSerializer(many=True, read_only=True)

    class Meta(CountryWithMinTariffSerializer.Meta):
        fields = CountryWithMinTariffSerializer.Meta.fields + [
            "description",
            "tariffs",
            "addresses",
        ]

    def get_tariffs(self, country):
        return TariffCompactSerializer(
            Tariff.soft_objects.filter(source_city__country=country).order_by(
                "is_dangerous", "destination_city", "min_weight"
            ),
            many=True,
        ).data


class AdditionalServiceSerializer(serializers.ModelSerializer):
    price_currency = CurrencySerializer(read_only=True)

    class Meta:
        model = AdditionalService
        fields = [
            "id",
            "needs_note",
            "needs_attachment",
            "title",
            "description",
            "price",
            "price_currency",
        ]


class CourierRegionSerializer(serializers.ModelSerializer):
    # price = serializers.DecimalField(
    #    max_digits=9, decimal_places=2, source="area.active_price"
    # )
    # price_currency = CurrencySerializer(source="area.price_currency")

    class Meta:
        model = CourierRegion
        fields = [
            "id",
            "title",
        ]


class CourierTariffSerializer(serializers.ModelSerializer):
    price_currency = CurrencySerializer()

    class Meta:
        model = CourierTariff
        fields = ["id", "title", "price", "discounted_price", "price_currency"]


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["name", "address", "logo", "url"]


class OrderProductReadSerializer(serializers.ModelSerializer):
    source_country = CountrySerializer(source="country")
    product_category = ProductCategoryCompactSerializer(source="category")
    price = serializers.SerializerMethodField()
    shipping_price = serializers.SerializerMethodField()
    product_image = serializers.CharField(source="image")
    shop = ShopSerializer()
    product_description = serializers.CharField(source="description")
    description = serializers.CharField(source="user_description")
    product_color = serializers.CharField(source="color")
    product_size = serializers.CharField(source="size")
    product_url = serializers.CharField(source="url")

    class Meta:
        model = OrderedProduct
        fields = [
            "product_description",
            "description",
            "product_url",
            "product_color",
            "product_size",
            "product_image",
            "product_category",
            "source_country",
            "price",
            "shipping_price",
            "shop",
        ]

    def get_shipping_price(self, product: OrderedProduct):
        return {
            "amount": str(product.shipping_price),
            "currency": CurrencySerializer(
                product.shipping_price_currency, context=self.context
            ).data,
        }

    def get_price(self, product: OrderedProduct):
        currency_azn = Currency.objects.filter(code="AZN").first()
        currency_usd = Currency.objects.filter(code="USD").first()

        azn_data = None
        if currency_azn:
            azn_data = {
                "amount": str(
                    Converter.convert(product.price, product.price_currency.code, "AZN")
                ),
                "currency": CurrencySerializer(currency_azn, context=self.context).data,
            }

        usd_data = None
        if currency_usd:
            usd_data = {
                "amount": str(
                    Converter.convert(product.price, product.price_currency.code, "USD")
                ),
                "currency": CurrencySerializer(currency_usd, context=self.context).data,
            }

        return [azn_data, usd_data]
