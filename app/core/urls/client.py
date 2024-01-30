from django.urls import path
from core.views import client as views

urlpatterns = [
    path("phone-prefixes/", views.phone_prefixes_view, name="phone-code-list"),
    path("currencies/", views.CurrencyApiView.as_view(), name="currency-list"),
    path("ordering-info/", views.ordering_info_view, name="ordering-info"),
]
