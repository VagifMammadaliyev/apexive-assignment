from functools import partial

from django.db import transaction
from django.utils.translation import ugettext as _
from rest_framework import serializers

from ontime import messages as msg
from domain.services import (
    complete_shopping_assistant_creation,
    complete_warehouseman_creation,
    complete_cashier_creation,
    complete_customer_service_creation,
    get_staff_user_data,
)
from core.models import City
from core.serializers.admin import CityReadSerializer, CountryReadSerializer
from customer.serializers import RoleSerializer
from customer.models import Customer, Role, Recipient


class RecipientReadSerializer(serializers.ModelSerializer):
    city = CityReadSerializer()
    country = CountryReadSerializer(source="city.country")
    is_billed_recipient = serializers.SerializerMethodField()
    gender = serializers.CharField(source="get_gender_display")

    class Meta:
        model = Recipient
        fields = [
            "id",
            "title",
            "first_name",
            "last_name",
            "full_name",
            "gender",
            "id_pin",
            "phone_number",
            "country",
            "city",
            "address",
            "address_extra",
            "is_billed_recipient",
        ]

    def get_is_billed_recipient(self, recipient):
        is_billed_recipient = getattr(recipient, "_is_billed_recipient", None)

        if is_billed_recipient is not None:
            return is_billed_recipient

        billed_recipient_id = self.context.get("billed_recipient_id")
        return recipient.id == billed_recipient_id


class RecipientWriteSerializer(serializers.ModelSerializer):
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.filter(country__is_base=True)
    )
    is_billed_recipient = serializers.NullBooleanField(required=False)

    class Meta:
        model = Recipient
        fields = [
            "id",
            "user",
            "title",
            "gender",
            "first_name",
            "last_name",
            "id_pin",
            "phone_number",
            "city",
            "address",
            "address_extra",
            "is_billed_recipient",
        ]

    def validate_id_pin(self, id_pin: str):
        id_pin = id_pin.upper()

        if not (id_pin.isalnum() and len(id_pin) == 7):
            raise serializers.ValidationError(msg.INVALID_ID_PIN)

        return id_pin

    def validate_phone_number(self, phone_number):
        number, _ = validate_phone_number(phone_number, validate_user=False)
        return number

    def save(self, *args, **kwargs):
        user = self.validated_data.get["user"]

        is_billing = self.validated_data.pop("is_billed_recipient", None)

        if is_billing is None:
            is_billing = not user.recipients.filter(is_deleted=False).exists()

        recipient = super().save(*args, **kwargs)
        if is_billing is not None and user:
            if is_billing:
                user.billed_recipient = recipient
                recipient._is_billed_recipient = True
                user.save(update_fields=["billed_recipient"])
            elif user.billed_recipient_id == recipient.id:
                user.billed_recipient = None
                user.save(update_fields=["billed_recipient"])

        return recipient

    def to_representation(self, instance):
        return RecipientReadSerializer(instance, context=self.context).data


class ProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        # model = Profile
        fields = [
            "gender",
            "birth_date",
            "id_serial",
            "id_number",
            "id_pin",
        ]


class CustomerReadSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source="full_phone_number")
    role = RoleSerializer()
    verification_data = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "client_code",
            "phone_number",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_created_by_admin",
            "date_joined",
            "updated_at",
            "role",
            "verification_data",
        ]

    def get_verification_data(self, customer):
        expired = customer.is_expired(
            customer.get_verification_code_expire(domain="sms")
        )

        return {
            "phone_verified": customer.phone_is_verified,
            "email_verified": customer.email_is_verified,
            "activation_code": customer.get_verification_code(domain="sms"),
            "is_activation_code_expired": expired,
        }


class CustomerDetailedSerializer(CustomerReadSerializer):
    # profile = ProfileReadSerializer()
    staff_data = serializers.SerializerMethodField()

    class Meta(CustomerReadSerializer.Meta):
        fields = CustomerReadSerializer.Meta.fields + ["profile", "staff_data"]

    def get_staff_data(self, user):
        if user.role.type != Role.USER:
            return get_staff_user_data(user)
        return None


class CustomerWriteSerializer(serializers.ModelSerializer):
    # profile = ProfileWriteSerializer()
    role = serializers.SlugRelatedField(slug_field="type", queryset=Role.objects.all())
    staff_data = serializers.JSONField(required=False)
    password = serializers.CharField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "email",
            "role",
            "full_phone_number",
            "client_code",
            "first_name",
            "last_name",
            "is_active",
            "profile",
            "staff_data",
            "password",
            # 'is_staff',
            # 'date_joined',
            # 'updated_at',
        ]

    def _get_callback(self, role, staff_data):
        callback = None
        if role.type == Role.SHOPPING_ASSISTANT:
            callback = complete_shopping_assistant_creation
        elif role.type == Role.WAREHOUSEMAN:
            callback = complete_warehouseman_creation
        elif role.type == Role.CASHIER:
            callback = complete_cashier_creation
        elif role.type == Role.CUSTOMER_SERVICE:
            callback = complete_customer_service_creation

        if callback:
            callback = partial(callback, role=role, staff_data=staff_data)

        return callback

    @transaction.atomic
    def update(self, customer, validated_data):
        callback = self._get_callback(
            validated_data.get("role", customer.role),
            validated_data.pop("staff_data", {}),
        )
        profile_data = validated_data.pop("profile", {})
        password = validated_data.pop("password", None)

        if password:
            customer.set_password(password)

        profile = customer.profile

        update_fields = []
        for field, value in profile_data.items():
            update_fields.append(field)
            setattr(profile, field, value)

        if update_fields:
            profile.save(update_fields=update_fields)

        if callback:
            callback(user=customer)
        return super().update(customer, validated_data)

    @transaction.atomic
    def create(self, validated_data):
        callback = self._get_callback(
            validated_data.get("role", None), validated_data.pop("staff_data", {})
        )
        profile_data = validated_data.pop("profile", {})

        full_phone_number = validated_data.pop("full_phone_number", None)
        email = validated_data.pop("email", None)
        password = validated_data.pop("password", None)

        customer = Customer.objects.create_staff_user(
            full_phone_number=full_phone_number,
            email=email,
            password=password,
            commit=True,
        )

        update_fields = []
        for field, value in validated_data.items():
            update_fields.append(field)
            setattr(customer, field, value)

        if update_fields:
            customer.save(update_fields=update_fields)

        profile_data["user_id"] = customer.id
        Profile.objects.create(**profile_data)

        if callback:
            callback(user=customer)
        return customer

    def validate_password(self, password):
        if len(password) < 8:
            raise serializers.ValidationError(msg.AT_LEAST_8_SYMBOLS_IN_PASSWORD)

        return password

    def to_representation(self, instance):
        return CustomerDetailedSerializer(instance).data
