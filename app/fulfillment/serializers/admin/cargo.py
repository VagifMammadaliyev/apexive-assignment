from rest_framework import serializers

from core.serializers.admin import (
    CurrencyCompactSerializer,
    CityCompactSerializer,
    CountryCompactSerializer,
)
from ontime.utils import get_expanded_fields, get_expanded_extra_kwargs
from fulfillment.models import (
    Tariff,
    Warehouse,
    Address,
    AddressField,
    ProductCategory,
    ProductType,
)
from fulfillment.translation import (
    TariffTranslationOptions,
    ProductTypeTranslationOptions,
    ProductCategoryTranslationOptions,
)


class TariffReadSerializer(serializers.ModelSerializer):
    price_currency = CurrencyCompactSerializer(read_only=True)
    source_city = CityCompactSerializer(read_only=True)
    destination_city = CityCompactSerializer(read_only=True)

    class Meta:
        model = Tariff
        fields = [
            "id",
            "title",
            "source_city",
            "destination_city",
            "price",
            "discounted_price",
            "price_currency",
            "min_weight",
            "max_weight",
            "is_per_kg",
            "is_dangerous",
        ]


class TariffTranslatedReadSerializer(TariffReadSerializer):
    class Meta(TariffReadSerializer.Meta):
        fields = get_expanded_fields(
            TariffReadSerializer.Meta.fields,
            TariffTranslationOptions.fields,
        )


class TariffWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tariff
        fields = get_expanded_fields(
            [
                "id",
                "title",
                "source_city",
                "destination_city",
                "price",
                "discounted_price",
                "price_currency",
                "min_weight",
                "max_weight",
                "is_per_kg",
                "is_dangerous",
            ],
            TariffTranslationOptions.fields,
        )
        extra_kwargs = get_expanded_extra_kwargs(
            {
                "title": {"required": True},
                "price": {"required": True},
                "discounted_price": {"required": True},
            },
            TariffTranslationOptions.fields,
        )

    def to_representation(self, instance):
        return TariffReadSerializer(instance).data


class WarehouseCompactSerializer(serializers.ModelSerializer):
    country = CountryCompactSerializer(read_only=True)

    class Meta:
        model = Warehouse
        fields = ["id", "title", "country"]


class WarehouseReadSerializer(serializers.ModelSerializer):
    country = CountryCompactSerializer(read_only=True)
    city = CityCompactSerializer(read_only=True)

    class Meta:
        model = Warehouse
        fields = ["id", "title", "codename", "country", "city", "address", "is_default"]


class WarehouseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "title", "codename", "country", "city", "address", "is_default"]

    def to_representation(self, instance):
        return WarehouseReadSerializer(instance).data


class AddressFielSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddressField
        fields = ["id", "name", "value", "append_client_code"]


class AddressReadSerializer(serializers.ModelSerializer):
    country = CountryCompactSerializer(read_only=True)
    fields = AddressFielSerializer(many=True)

    class Meta:
        model = Address
        fields = ["id", "country", "fields"]


class AddressWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["id", "country"]

    def to_representation(self, instance):
        return AddressReadSerializer(instance).data


class ProductCategoryCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = ["id", "name", "hs_code", "needs_description"]
        # extra_kwargs = {"needs_description": {"write_only": True}}


class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = get_expanded_fields(
            ["id", "name", "hs_code", "needs_description"],
            ProductCategoryTranslationOptions.fields,
        )
        extra_kwargs = get_expanded_extra_kwargs(
            {"name": {"required": True}},
            ProductCategoryTranslationOptions.fields,
        )


class ProductTypeWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductType
        fields = get_expanded_fields(
            ["id", "name", "category"], ProductTypeTranslationOptions.fields
        )
        extra_kwargs = get_expanded_extra_kwargs(
            {"name": {"required": True}}, ProductTypeTranslationOptions.fields
        )

    def to_representation(self, instance):
        return ProductTypeTranslatedReadSerializer(instance).data


class ProductTypeCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductType
        fields = ["id", "name"]


class ProductTypeReadSerializer(serializers.ModelSerializer):
    category = ProductCategoryCompactSerializer(read_only=True)

    class Meta:
        model = ProductType
        fields = ["id", "name", "category"]


class ProductTypeTranslatedReadSerializer(ProductTypeReadSerializer):
    class Meta(ProductTypeReadSerializer.Meta):
        model = ProductType
        fields = get_expanded_fields(
            ProductTypeReadSerializer.Meta.fields, ProductTypeTranslationOptions.fields
        )
