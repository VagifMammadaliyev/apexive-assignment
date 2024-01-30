from django_filters.rest_framework import FilterSet

from core.models import City, Country, Currency


class CityFilter(FilterSet):
    class Meta:
        model = City
        fields = {
            "country": ["exact"],
            "country__is_base": ["exact"],
            "country__is_active": ["exact"],
        }


class CurrencyFilter(FilterSet):
    class Meta:
        model = Currency
        fields = {
            # "country": ["exact"],
            "code": ["icontains"],
            "name": ["icontains"],
        }


class CountryFilter(FilterSet):
    class Meta:
        model = Country
        fields = {
            "is_base": ["exact"],
            "is_active": ["exact"],
            "is_ordering_enabled": ["exact"],
            "code": ["icontains"],
            "name": ["icontains"],
        }
