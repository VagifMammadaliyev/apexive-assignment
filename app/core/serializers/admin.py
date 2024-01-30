from rest_framework import serializers

from ontime.utils import get_expanded_extra_kwargs, get_expanded_fields
from core.translation import (
    CurrencyTranslationOptions,
    CountryTranslationOptions,
    CityTranslationOptions,
)
from customer.models import Role
from core.models import Country, Currency, MobileOperator, City


class RoleSerizlier(serializers.ModelSerializer):
    type = serializers.CharField(source="get_type_display", read_only=True)
    codename = serializers.CharField(source="type", read_only=True)

    class Meta:
        model = Role
        fields = ["id", "type", "codename"]


class CurrencyCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["id", "name", "code", "symbol", "rate"]


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = [
            "id",
            "name",
            "code",
            "symbol",
            "rate",
        ]
        extra_kwargs = {"name": {"required": True}}


class CurrencyTranslatedSerializer(CurrencySerializer):
    class Meta(CurrencySerializer.Meta):
        fields = get_expanded_fields(
            CurrencySerializer.Meta.fields, CurrencyTranslationOptions.fields
        )
        extra_kwargs = get_expanded_extra_kwargs(
            CurrencySerializer.Meta.extra_kwargs, CurrencyTranslationOptions.fields
        )


class CountryReadSerializer(serializers.ModelSerializer):
    currency = CurrencyCompactSerializer(read_only=True)

    class Meta:
        model = Country
        fields = [
            "id",
            "name",
            "code",
            "description",
            "map_image",
            "timezone",
            "is_base",
            "is_active",
            "phone_code",
            "currency",
        ]


class CountryTranslatedReadSerializer(CountryReadSerializer):
    class Meta(CountryReadSerializer.Meta):
        fields = get_expanded_fields(
            CountryReadSerializer.Meta.fields,
            CountryTranslationOptions.fields,
        )


class CountryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = get_expanded_fields(
            [
                "id",
                "name",
                "code",
                "description",
                "map_image",
                "timezone",
                "is_base",
                "is_active",
                "phone_code",
                "currency",
            ],
            CountryTranslationOptions.fields,
        )
        extra_kwargs = get_expanded_extra_kwargs(
            {"name": {"required": True}, "description": {"required": True}},
            CountryTranslationOptions.fields,
        )

    def to_representation(self, instance):
        return CountryReadSerializer(instance).data


class CountryCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_base",
            "is_active",
            "is_smart_customs_enabled",
        ]


class MobileOperatorReadSerializer(serializers.ModelSerializer):
    country = CountryCompactSerializer(read_only=True)

    class Meta:
        model = MobileOperator
        fields = [
            "id",
            "name",
            "country",
            "prefix",
        ]


class MobileOperatorWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileOperator
        fields = [
            "id",
            "name",
            "country",
            "prefix",
        ]


class CityCompactSerializer(serializers.ModelSerializer):
    country = CountryCompactSerializer(read_only=True)

    class Meta:
        model = City
        fields = [
            "id",
            "name",
            "code",
            "country",
        ]


class CityReadSerializer(serializers.ModelSerializer):
    country = CountryCompactSerializer(read_only=True)

    class Meta:
        model = City
        fields = ["id", "name", "code", "country"]


class CityTranslatedReadSerializer(CityReadSerializer):
    class Meta(CityReadSerializer.Meta):
        fields = get_expanded_fields(
            CityReadSerializer.Meta.fields, CityTranslationOptions.fields
        )


class CityWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = get_expanded_fields(
            ["id", "name", "code", "country"], CityTranslationOptions.fields
        )
        extra_kwargs = get_expanded_extra_kwargs(
            {"name": {"required": True}}, CityTranslationOptions.fields
        )

    def to_representation(self, instance):
        return CityReadSerializer(instance).data
