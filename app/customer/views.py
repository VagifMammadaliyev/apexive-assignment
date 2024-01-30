from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext as _
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from django.http import Http404, JsonResponse
from django.utils.decorators import method_decorator
from knox.views import LoginView as KnoxLoginView
from knox.models import AuthToken
from rest_framework import permissions, status, views, generics
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response
from defender.decorators import watch_login

from ontime import messages as msg
from core.models import Currency
from domain.services import generate_promo_code
from domain.exceptions.customer import (
    AlreadyVerifiedError,
    VerificationError,
    PasswordResetCodeInvalidError,
)
from customer.permissions import IsOntimeStaffUser
from customer.serializers import (
    BalanceSerializer,
    LoginSerializer,
    RegisterSerializer,
    ProfileReadSerializer,
    ProfileWriteSerializer,
    AdminLoginSerializer,
    MinimalStaffUserSerializer,
    StaffUserSerializer,
    ResetPasswordSerializer,
)

User = get_user_model()


@method_decorator(watch_login(status_code=403), name="dispatch")
class LoginView(KnoxLoginView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    login_serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.login_serializer_class(data=request.data)
        user = serializer.authenticate(request, check_email_confirmation=False)
        response = super().post(request, format=None)
        return JsonResponse(response.data, status=response.status_code)


class RegisterApiView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_scope = "hard"

    # @transaction.atomic
    def post(self, request, *args, **kwargs):
        print("Register request started")
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        print("serializer is valid")
        user = serializer.save()
        print('user saved, starting generating promo code')
        generate_promo_code(user=user)
        print('promo code generated')

        return Response(
            {"detail": msg.SENT_VERIFICATION_SMS},
            status=status.HTTP_200_OK,
        )


class VerifyPhoneNumberApiView(views.APIView):
    throttle_scope = "hard"
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        phone_number = request.data.get("phone_number")

        try:
            user = User.objects.get(full_phone_number=phone_number)
        except User.DoesNotExist:
            raise VerificationError

        if user.phone_is_verified:
            raise AlreadyVerifiedError

        if user.check_verification_code(
            request.data.get("code"), domain="sms", activate=True
        ):
            instance, token = AuthToken.objects.create(user)
            data = {"token": token}
            return Response(data, status=status.HTTP_200_OK)

        raise VerificationError


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def confirm_email_view(request):
    uid = request.data.get("uid")
    token = request.data.get("token")

    try:
        user_pk = force_text(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_pk)
    except (TypeError, ValueError, OverflowError, AttributeError, User.DoesNotExist):
        user = None

    if user and token:
        user.confirm_email(token)

    return Response({"detail": msg.EMAIL_VERIFIED}, status=status.HTTP_200_OK)


class ResendVerificationSmsApiView(views.APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_scope = "hardcore"

    def post(self, request, *args, **kwargs):
        phone_number = request.data.get("phone_number")

        try:
            user = User.objects.get(full_phone_number=phone_number)
        except User.DoesNotExist:
            user = None

        # Send only if it is inactive user and phone number is not verified
        if user and not user.is_active and not user.phone_is_verified:
            user.set_verification_code(domain="sms", send=True)

        return Response(
            {"detail": msg.RESENT_VERIFICATION_SMS}, status=status.HTTP_200_OK
        )


class ProfileApiView(generics.RetrieveUpdateAPIView):
    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return ProfileReadSerializer
        return ProfileWriteSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context["user"] = self.request.user
        return context


class AdminLoginView(LoginView):
    login_serializer_class = AdminLoginSerializer

    def get_user_serializer_class(self):
        if "minimal" in self.request.query_params:
            return MinimalStaffUserSerializer
        return StaffUserSerializer


@api_view(["GET"])
@permission_classes([IsOntimeStaffUser])
def admin_profile_view(request):
    if "minimal" in request.query_params:
        return Response(MinimalStaffUserSerializer(request.user).data)
    return Response(StaffUserSerializer(request.user).data)


class SendResetPasswordSmsApiView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "hardcore"

    def post(self, request, *args, **kwargs):
        phone_number = request.data.get("phone_number")
        user = User.objects.filter(
            is_active=True, full_phone_number=phone_number
        ).first()

        if user:
            user.send_reset_password_sms(send=settings.PROD)

        return Response({"status": "OK"})


class VerifySmsResetPasswordCode(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "hard"

    def post(self, request, *args, **kwargs):
        phone_number = request.data.get("phone_number")
        user = User.objects.filter(
            is_active=True, full_phone_number=phone_number
        ).first()

        verified = False
        if user:
            verified = user.check_reset_password_sms_code(
                request.data.get("reset_code")
            )

        if not verified:
            raise PasswordResetCodeInvalidError

        return Response(
            {"verified": verified},
        )


class ConfirmSmsResetPasswordApiView(views.APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "hardcore"

    def post(self, request, *args, **kwargs):
        phone_number = request.data.get("phone_number")
        user = User.objects.filter(
            is_active=True, full_phone_number=phone_number
        ).first()

        if user:
            reset = ResetPasswordSerializer(data=request.data)
            reset.is_valid(raise_exception=True)
            confirmed = reset.confirm(user=user)

        return Response({"status": "OK"})


class ResendEmailActivationApiView(views.APIView):
    throttle_scope = "hardcore"

    def post(self, request):
        if request.user.email and not request.user.email_is_verified:
            request.user.send_activation_email(request.user.email)
            return Response({"status": "OK"})
        raise AlreadyVerifiedError


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def check_promo_code(request):
    from fulfillment.models import PromoCode

    valid = PromoCode.objects.filter(
        user__is_active=True, value=request.data.get("promo_code", None)
    ).exists()
    return Response({"valid": valid})
