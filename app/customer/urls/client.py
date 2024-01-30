from django.urls import path, include

from customer import views
from knox import views as knox_views
from django_rest_resetpassword import views as resetpassword_views

urlpatterns = [
    path("me/", views.ProfileApiView.as_view(), name="profile"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", knox_views.LogoutView.as_view(), name="logout"),
    path("logout-all/", knox_views.LogoutAllView.as_view(), name="logout-all"),
    path("register/", views.RegisterApiView.as_view(), name="register"),
    path(
        "verify-phone-number/",
        views.VerifyPhoneNumberApiView.as_view(),
        name="verify-sms-code",
    ),
    path(
        "resend-email-activation-link/",
        views.ResendEmailActivationApiView.as_view(),
        name="resend-email-activation",
    ),
    path("confirm-email/", views.confirm_email_view, name="confirm-email"),
    path(
        "resend-verification-code/",
        views.ResendVerificationSmsApiView.as_view(),
        name="resent-sms-code",
    ),
    path(
        "password/reset/request-sms-code/",
        views.SendResetPasswordSmsApiView.as_view(),
        name="request-reset-password-token",
    ),
    path(
        "password/reset/verify-sms-code/",
        views.VerifySmsResetPasswordCode.as_view(),
        name="validate-reset-password-token",
    ),
    path(
        "password/reset/confirm/",
        views.ConfirmSmsResetPasswordApiView.as_view(),
        name="confirm-reset-password",
    ),
    path("check-promo-code/", views.check_promo_code, name="check-promo-code"),
]
