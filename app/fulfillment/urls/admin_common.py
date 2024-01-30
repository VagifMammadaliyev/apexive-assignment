from django.urls import path

from fulfillment.views.admin import common as views

urlpatterns = [
    path(
        "autocomplete/users/", views.autocomplete_user_view, name="autocomplete-users"
    ),
    path(
        "users/<int:customer_pk>/recipients/",
        views.CustomerRecipientListApiView.as_view(),
        name="customer-recipient",
    ),
]
