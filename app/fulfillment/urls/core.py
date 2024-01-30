from django.urls import path
from django.views.decorators.cache import cache_page

from fulfillment.views import common as common_views


urlpatterns = [
    path(
        "countries/",
        (common_views.CountryListApiView.as_view()),
        name="country-list",
    ),
    path(
        "countries/<int:country_pk>/addresses/",
        (common_views.address_by_country_view),
        name="country-address-list",
    ),
    path(
        "countries/<int:pk>/",
        (common_views.CountryRetrieveApiVIew.as_view()),
        name="country-retrieve",
    ),
    path(
        "countries/<int:country_pk>/tariffs/",
        (common_views.tariff_by_country_view),
        name="country-tariff-list",
    ),
    path("cities/", common_views.CityListApiView.as_view(), name="city-list"),
]
