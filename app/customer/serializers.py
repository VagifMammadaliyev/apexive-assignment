import re
import base64

from django.db.models import Q
from django.contrib.auth import get_user_model, login
from django.utils.translation import ugettext as _
from rest_framework import serializers, validators
from rest_framework.exceptions import AuthenticationFailed

from ontime import messages as msg
from domain.services import (
    get_staff_user_data,
    get_staff_user_timezone,
    calculate_monthly_spendings,
    check_if_customer_can_top_up_balance,
)
from domain.services import create_notification
from domain.validators import validate_phone_number
from core.models import MobileOperator
from core.serializers.client import CurrencySerializer
from customer.models import Balance, Role
from fulfillment.serializers.common import WarehouseReadSerializer
from fulfillment.serializers.customer import RecipientReadSerializer
from fulfillment.models import PromoCode, Warehouse

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)

    def get_users_queryset(self):
        return User.objects.filter(is_active=True)

    def authenticate(self, request, check_email_confirmation=True):
        """Returns user, if can't raises authentication error."""
        self.is_valid(raise_exception=True)
        username = self.validated_data["username"]
        password = self.validated_data["password"]

        # check if number starting with 994 is used (but no plus sign is provided) (e.g. 994552228811)
        if (
            len(username) > len("0XXYYYZZEE")
            and username.isdigit()
            and username.startswith("994")
        ):
            # fix username so it starts with plus and fits our old logic
            username = "+" + username

        email_used = "@" in username
        full_phone_used = "+" in username

        if email_used:
            login_query = Q(email__iexact=username)
        elif full_phone_used:
            login_query = Q(full_phone_number=username)
        else:
            login_query = Q(client_code=username)

        try:
            user = self.get_users_queryset().get(login_query)

            if check_email_confirmation and email_used and not user.email_is_verified:
                user = None

            if user and not user.check_password(password):
                user = None
        except User.DoesNotExist:
            user = None

        if user is not None and user.is_active:
            login(request, user)
            return user

        raise AuthenticationFailed(msg.LOGIN_FAILED)


def validate_user_password(password):
    errors = []

    if not any(ch.isdigit() for ch in password):
        errors.append(msg.AT_LEAST_ONE_DIGIT_IN_PASSWORD)

    if not len(password) > 7:
        errors.append(msg.AT_LEAST_8_SYMBOLS_IN_PASSWORD)

    if errors:
        raise serializers.ValidationError(errors)

    return password


class RegisterSerializer(serializers.Serializer):
    phone_number = serializers.CharField(required=True, max_length=15)
    first_name = serializers.CharField(required=True, max_length=50)
    last_name = serializers.CharField(required=True, max_length=50)
    email = serializers.EmailField(
        required=True,
        max_length=255,
        validators=[
            validators.UniqueValidator(queryset=User.objects.filter(is_active=True))
        ],
    )
    password = serializers.CharField(required=True)
    promo_code = serializers.SlugRelatedField(
        slug_field="value",
        queryset=PromoCode.objects.filter(user__is_active=True),
        required=False,
    )

    def validate_password(self, password: str):
        return validate_user_password(password)

    def validate_phone_number(self, number: str):
        number, self.old_user = validate_phone_number(number, validate_user=True)

        return number

    def save(self):
        phone_number = self.validated_data["phone_number"]
        first_name = self.validated_data["first_name"]
        last_name = self.validated_data["last_name"]
        password = self.validated_data["password"]
        email = self.validated_data.pop("email", None)
        promo_code: PromoCode = self.validated_data.pop("promo_code", None)

        old_user = self.old_user  # old inactive user -- overriding
        print("  old user is ", old_user)
        if old_user:
            print("  overriding existing user")
            user = old_user
        else:
            print("  creating new user")
            user = User.objects.create_user(
                phone_number, password=password, commit=False
            )

        print("  setting user fields")
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.set_password(password)
        user.save()
        # user.send_activation_email(email)
        print("  sending verification code")
        user.set_verification_code(domain="sms", send=True)

        print("  registering promo code ->", promo_code)
        if promo_code:
            promo_code.register(user)

        return user


class ProfileReadSerializer(serializers.ModelSerializer):
    is_email_verified = serializers.BooleanField(
        source="email_is_verified", read_only=True
    )
    phone_number = serializers.CharField(source="full_phone_number", read_only=True)
    balance = serializers.SerializerMethodField()
    billed_recipient = RecipientReadSerializer(read_only=True)
    # monthly_spendings = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    prefered_warehouse = WarehouseReadSerializer()

    class Meta:
        model = User
        fields = [
            "client_code",
            "first_name",
            "last_name",
            "email",
            "is_email_verified",
            "phone_number",
            "is_completed",
            # "monthly_spendings",
            "birth_date",
            "billed_recipient",
            "balance",
            "prefered_warehouse",
            "photo",
        ]
        read_only_fields = fields

    def get_photo(self, user):
        return None  # do not show customer photo!

        if not user.photo_base64:
            return None

        return {
            "base64": user.photo_base64,
        }

    def get_balance(self, user):
        balance = user.as_customer.active_balance
        return BalanceSerializer(balance).data

    # def get_monthly_spendings(self, user):
    #     monthly_spendings = calculate_monthly_spendings(user)

    #     if monthly_spendings:
    #         return {
    #             "amount": monthly_spendings.amount,
    #             "currency": CurrencySerializer(monthly_spendings.currency).data,
    #         }

    #     return None


class ProfileWriteSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False)
    old_password = serializers.CharField(required=False)
    password = serializers.CharField(required=False)
    prefered_warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.filter(country__is_base=True)
    )

    class Meta:
        model = User
        fields = [
            "email",
            "birth_date",
            "old_password",
            "password",
            "prefered_warehouse",
        ]

    def validate_password(self, password):
        return validate_user_password(password)

    def save(self, *args, **kwargs):
        password = self.validated_data.pop("password", None)
        if password and self.instance and self.instance.id:
            self.instance.set_password(password)
            self.instance.save(update_fields=["password"])

        return super().save(*args, **kwargs)

    def update(self, instance, validated_data):
        email = validated_data.get("email", None)

        if email and not instance.email_is_verified and email != instance.email:
            self.instance.send_activation_email(email)

        return super().update(instance, validated_data)

    def validate(self, data):
        old_password = data.get("old_password")
        new_password = data.get("password")

        if new_password and not self.instance.check_password(old_password):
            raise serializers.ValidationError({"old_password": msg.INVALID_PASSWORD})

        return data

    def validate_email(self, email):
        current_user = self.context["user"]

        if current_user.email and current_user.email_is_verified:
            # Don't allow to change email address
            return current_user.email

        if User.objects.filter(email=email).exclude(pk=current_user.pk).exists():
            raise serializers.ValidationError(msg.ALREADY_USER_EMAIL)
        return email

    def to_representation(self, instance):
        return ProfileReadSerializer(instance).data


class BalanceSerializer(serializers.ModelSerializer):
    can_be_topped_up = serializers.SerializerMethodField()
    currency = CurrencySerializer(read_only=True)

    class Meta:
        model = Balance
        fields = ["can_be_topped_up", "amount", "currency"]

    def get_can_be_topped_up(self, balance):
        from fulfillment.models import Transaction

        return check_if_customer_can_top_up_balance(
            balance.user, Transaction.CYBERSOURCE_SERVICE
        )


class RoleSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="get_type_display")

    class Meta:
        model = Role
        fields = ["display_name", "type"]


class StaffUserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    timezone = serializers.SerializerMethodField()
    worker_data = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "role",
            "first_name",
            "last_name",
            "email",
            "timezone",
            "worker_data",
        ]

    def get_timezone(self, staff_user):
        return get_staff_user_timezone(staff_user)

    def get_worker_data(self, staff_user):
        return get_staff_user_data(staff_user)


class MinimalStaffUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id"]


class AdminLoginSerializer(LoginSerializer):
    def get_users_queryset(self):
        return super().get_users_queryset().filter(is_staff=True)


class ResetPasswordSerializer(serializers.Serializer):
    reset_code = serializers.CharField(max_length=100)
    new_password = serializers.CharField(max_length=500)

    def validate_new_password(self, new_password):
        return validate_user_password(new_password)

    def confirm(self, user):
        data = self.validated_data
        reset_code = data.get("reset_code")
        new_password = data.get("new_password")

        return user.check_reset_password_sms_code(reset_code, new_password)
