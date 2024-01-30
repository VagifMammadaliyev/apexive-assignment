from django.urls import path
from rest_framework import routers

from core.views import admin as core_views

router = routers.SimpleRouter()
router.register("countries", core_views.CountryViewSet)
router.register("currencies", core_views.CurrencyViewSet)
router.register("mobile-operators", core_views.MobileOperatorViewSet)
router.register("cities", core_views.CityViewSet)

urlpatterns = [
    path("roles/", core_views.role_list_view, name="role-list"),
    path("timezones/", core_views.timezone_list_view, name="timezone-list"),
]

urlpatterns += router.urls
