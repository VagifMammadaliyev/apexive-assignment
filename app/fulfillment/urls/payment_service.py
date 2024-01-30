from django.urls import path

from fulfillment.views.payment_service import views


urlpatterns = [
    path(
        "cybersource/public/result/",
        views.CybersourceAutoResultNotificationView.as_view(),
        name="cybersource-result",
    ),
    path(
        "cybersource/private/result/",
        views.CybersourceResultNotificationView.as_view(),
        name="cybersource-private-result",
    ),
    path(
        "paypal/public/result/",
        views.PayPalAutoNotificationView.as_view(),
        name="paypal-result",
    ),
    path(
        "paytr/public/success/", views.PayTRSuccessView.as_view(), name="paytr-success"
    ),
    path("paytr/public/fail/", views.PayTRSuccessView.as_view(), name="paytr-fail"),
]
