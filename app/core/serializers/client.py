from rest_framework import serializers

from domain.services import is_consolidation_enabled_for_country
from core.models import Country, Currency, City


class PhoneCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["name", "phone_code"]


class CountrySerializer(serializers.ModelSerializer):
    # Each country has only one warehouse, so for now
    # we have to expose that field from countries
    is_consolidation_enabled = serializers.SerializerMethodField()
    ordering = serializers.SerializerMethodField()
    packaging = serializers.SerializerMethodField()

    class Meta:
        model = Country
        fields = [
            "id",
            "name",
            "is_active",
            "is_base",
            "local_time",
            "flag_image",
            "map_image",
            "is_consolidation_enabled",
            "is_default_destination",
            "is_default_source",
            "is_smart_customs_enabled",
            "ordering",
            "packaging",
            "description",
        ]

    def get_ordering(self, country):
        return {
            "enabled": country.is_ordering_enabled,
            "disabled_message": country.ordering_disabled_message,
        }

    def get_packaging(self, country):
        return {
            "enabled": country.is_packages_enabled,
            "disabled_message": country.packages_disabled_message,
        }

    def get_is_consolidation_enabled(self, country):
        return is_consolidation_enabled_for_country(
            country, getattr(country, "prefetched_warehouses", [])
        )


class CountryCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "name", "flag_image", "is_smart_customs_enabled"]


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["id", "name", "code", "symbol", "rate", "is_base"]


class CountryCompactWithCurrencySerializer(CountryCompactSerializer):
    currency = CurrencySerializer()

    class Meta(CountryCompactSerializer.Meta):
        fields = CountryCompactSerializer.Meta.fields + ["currency"]


class CountryWithCurrencySerializer(CountrySerializer):
    currency = CurrencySerializer(read_only=True)

    class Meta(CountrySerializer.Meta):
        fields = CountrySerializer.Meta.fields + ["currency"]


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["id", "name", "is_default_destination", "is_default_source"]
