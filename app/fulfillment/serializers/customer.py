import os
import json
from typing import Union, Optional

from django.db import transaction
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext as _
from django.utils import timezone
from django.core.files import File
from django.conf import settings
from rest_framework import serializers
from rest_framework import validators

from ontime import messages as msg
from domain.validators import validate_phone_number
from domain.services import (
    calculate_monthly_spendings,
    get_user_transactions,
    get_courier_order_related_shipment_transactions,
    create_shipment,
    update_additional_services,
    is_consolidation_enabled_for_country,
    get_additional_services,
    promote_status,
)
from domain.exceptions.logic import DisabledCountryError
from customer.models import Recipient
from customer.tasks import fetch_user_data_from_government_resource
from core.utils.security import validate_input_file
from core.converter import Converter
from core.models import Country, Currency, City
from core.serializers.client import (
    CountrySerializer,
    CountryCompactSerializer,
    CurrencySerializer,
    CitySerializer,
)
from fulfillment.serializers.common import (
    StatusSerializer,
    # NextPrevStatusSerializer,
    ProductTypeExtraCompactSerializer,
    ProductCategoryCompactSerializer,
    ProductTypeCompactSerializer,
    WarehouseReadSerializer,
    AdditionalServiceSerializer,
    CourierRegionSerializer,
    CourierTariffSerializer,
)
from fulfillment.models import (
    AdditionalService,
    PackageAdditionalService,
    ShipmentAdditionalService,
    Order,
    Package,
    ProductType,
    ProductCategory,
    Product,
    Shipment,
    Warehouse,
    Transaction,
    Comment,
    Notification,
    Subscriber,
    ContactUsMessage,
    TicketCategory,
    Ticket,
    TicketAttachment,
    TicketComment,
    CourierOrder,
    CourierTariff,
    CourierRegion,
    Status,
    Shop,
)

User = get_user_model()


# class AddressCompactSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Address
#         fields = ["id", "title"]


class RecipientCompactSerializer(serializers.ModelSerializer):
    monthly_spendings = serializers.SerializerMethodField()
    region = CourierRegionSerializer(read_only=True)

    class Meta:
        model = Recipient
        fields = [
            "id",
            "title",
            "full_name",
            "id_pin",
            "phone_number",
            "address",
            "region",
            "monthly_spendings",
        ]

    def get_monthly_spendings(self, recipient):
        monthly_spendings = calculate_monthly_spendings(recipient)

        if monthly_spendings:
            return {
                "amount": monthly_spendings.amount,
                "currency": CurrencySerializer(monthly_spendings.currency).data,
                "status": monthly_spendings.status,
            }

        return None


class RecipientVeryCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipient
        fields = [
            "id",
            "title",
            "full_name",
            "id_pin",
        ]


class OrderReadSerializer(serializers.ModelSerializer):
    status = StatusSerializer(read_only=True)
    source_country = CountrySerializer(read_only=True)
    product_price_currency = CurrencySerializer(read_only=True)
    cargo_price_currency = CurrencySerializer(read_only=True)
    commission_price_currency = CurrencySerializer(read_only=True)
    total_price_currency = CurrencySerializer(read_only=True)
    discounted_total_price = serializers.DecimalField(decimal_places=2, max_digits=9)
    discounted_total_price_currency = CurrencySerializer(read_only=True)
    actions = serializers.SerializerMethodField()
    product_category = ProductCategoryCompactSerializer(read_only=True)
    product_type = ProductTypeExtraCompactSerializer(read_only=True)
    # destination_user_address = AddressCompactSerializer(read_only=True)
    destination_warehouse = WarehouseReadSerializer(read_only=True)
    recipient = RecipientCompactSerializer(
        read_only=True, source="recipient.real_recipient"
    )

    class Meta:
        model = Order
        fields = [
            "identifier",
            "order_code",
            "status",
            "is_paid",
            "source_country",
            "description",
            "product_color",
            "product_size",
            "product_url",
            "product_quantity",
            "product_description",
            "product_category",
            "product_type",
            "product_price",
            "product_price_currency",
            "cargo_price",
            "cargo_price_currency",
            "commission_price",
            "commission_price_currency",
            "total_price",
            "total_price_currency",
            "discounted_total_price",
            "discounted_total_price_currency",
            "actions",
            "created_at",
            "status_last_update_time",
            # "is_oneclick",
            "consolidate",
            # "destination_user_address",
            "recipient",
            "destination_warehouse",
            "user_note",
            "has_remainder",
            "is_archived",
        ]

    def get_actions(self, order):
        return {
            "can_pay": order.can_be_payed_by_user,
            "can_edit": order.can_be_edited_by_user,
            "can_delete": order.can_be_deleted_by_user,
            "can_archive": order.can_user_archive,
        }


class CommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["body"]
        extra_kwargs = {
            "body": {
                "allow_blank": False,
                "allow_null": False,
                "required": True,
            }
        }

    def to_representation(self, instance):
        return CommentReadSerializer(instance).data


class CommentReadSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "title", "body", "time"]

    def get_time(self, comment):
        return timezone.localtime(comment.created_at).strftime("%d/%m/%Y %H:%M")


class OrderDetailedSerializer(OrderReadSerializer):
    comments = CommentReadSerializer(many=True)

    class Meta(OrderReadSerializer.Meta):
        fields = OrderReadSerializer.Meta.fields + ["comments"]


class OrderWriteSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    consolidate = serializers.BooleanField(default=True)
    # oneclick = serializers.BooleanField(source="is_oneclick", default=True)
    recipient = serializers.PrimaryKeyRelatedField(
        queryset=Recipient.objects.filter(is_deleted=False), required=False
    )
    destination_warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.filter(
            Q(country__is_base=True) | Q(city__country__is_base=True)
        ),
        required=False,
    )

    class Meta:
        model = Order
        fields = [
            "user",
            "source_country",
            "description",
            "product_color",
            "product_size",
            "product_url",
            "product_price",
            "product_price_currency",
            # "product_category",
            # "product_type",
            "cargo_price",
            "cargo_price_currency",
            "product_quantity",
            "product_description",
            "consolidate",
            "recipient",
            "destination_warehouse",
            "user_note",
        ]
        extra_kwargs = {
            field: {"required": True, "allow_null": False}
            for field in fields
            if not field
            in [
                "user_note",
                "product_type",
                "product_color",
                "product_size",
                "product_description",
                "recipient",
                "destination_warehouse",
                "product_price_currency",
                "cargo_price_currency",
                # "destination_user_address",
            ]
        }
        extra_kwargs["description"]["allow_blank"] = False
        extra_kwargs["source_country"]["queryset"] = Country.objects.filter(
            is_active=True
        )
        extra_kwargs["product_price_currency"] = {"required": False}
        extra_kwargs["cargo_price_currency"] = {"required": False}

    def validate(self, data):
        user = self.context["user"]
        source_country = data.get("source_country")
        product_category = data.get("product_category")
        product_type = data.get("product_type")
        product_description = data.get("product_description")
        # Expose field using different name to API
        is_oneclick = not data.pop("consolidate", True)
        data["is_oneclick"] = is_oneclick
        recipient = data.get("recipient")
        destination_warehouse = data.get("destination_warehouse")

        # if product price currency and cargo price currency are provided
        # and both are the same, then set total price currency too
        cargo_price_currency = data.get("cargo_price_currency", None)
        product_price_currency = data.get("product_price_currency", None)

        if (
            cargo_price_currency
            and product_price_currency
            and cargo_price_currency == product_price_currency
        ):
            data["total_price_currency_id"] = product_price_currency.id  # why?
            data[
                "total_price_currency"
            ] = product_price_currency  # this must be enough...

        if source_country and not source_country.is_ordering_enabled:
            raise DisabledCountryError

        if not is_oneclick:  # FIXME: may be it is not a good idea to handle it there?
            # Remove recipient and destination warehouse from order
            # if it is not oneclick!
            data["recipient"] = None
            data["destination_warehouse"] = None

        if (
            product_category
            and not product_category.needs_description
            and not product_type
        ):
            raise serializers.ValidationError(
                {"product_type": msg.MISSING_PRODUCT_TYPE}
            )

        if (
            product_category
            and product_type
            and product_type.category_id != product_category.id
        ):
            raise serializers.ValidationError(
                {"product_type": msg.INVALID_PRODUCT_TYPE}
            )

        if (
            product_category
            and product_category.needs_description
            and not product_description
        ):
            raise serializers.ValidationError(
                {"product_description": msg.CUSTOMS_DESCRIPTION}
            )

        if source_country and not (
            is_oneclick or is_consolidation_enabled_for_country(source_country)
        ):
            raise serializers.ValidationError(
                {"source_country": msg.NO_CONSOLIDATION_FOR_THIS_COUNTRY}
            )

        if is_oneclick and not recipient:
            raise serializers.ValidationError({"recipient": msg.MISSING_RECIPIENT})

        if is_oneclick and not destination_warehouse:
            raise serializers.ValidationError(
                {"destination_warehouse": msg.MISSING_DESTINATION_WAREHOUSE}
            )

        if is_oneclick and recipient and not recipient.user_id == user.id:
            raise serializers.ValidationError(
                {"recipient": msg.RECIPIENT_DOES_NOT_BELONGS_TO_USER}
            )

        if recipient:
            data["recipient"] = recipient.freeze()

        return data

    def to_representation(self, instance):
        return OrderReadSerializer(instance).data


class OrderArchiveSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = []

    def to_representation(self, instance):
        return OrderReadSerializer(instance).data


class ProductReadSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source="normalized_description", read_only=True)
    price_currency = CurrencySerializer(read_only=True)
    category = ProductCategoryCompactSerializer(read_only=True)
    type = ProductTypeExtraCompactSerializer(read_only=True)
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "type",
            "description",
            "warehouseman_description",
            "quantity",
            "url",
            "price",
            "price_currency",
            "photos",
        ]

    def get_photos(self, product: Product):
        request = self.context.get("request")
        photos = product.photos.all()
        return [
            request.build_absolute_uri(photo.file.url) if request else photo.file.url
            for photo in photos
        ]


class PackageCompactSerializer(serializers.ModelSerializer):
    status = StatusSerializer(read_only=True)
    products = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            "tracking_code",
            "status",
            "seller",
            "status_last_update_time",
            "consolidate",
            "arrival_date",
            "products",
        ]

    def get_products(self, package):
        product_types = []

        for product in package.products.select_related():
            product_types.append(product.normalized_description)

        return product_types


class PackageReadSerializer(serializers.ModelSerializer):
    # status = StatusSerializer(read_only=True)
    status = serializers.SerializerMethodField()
    source_country = CountrySerializer(read_only=True)
    actions = serializers.SerializerMethodField()
    products = ProductReadSerializer(many=True, read_only=True)
    photos = serializers.SerializerMethodField()
    arrival_date = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            "identifier",
            "tracking_code",
            "status",
            "is_archived",
            "seller",
            "source_country",
            "weight",
            "products",
            "attachment",
            "actions",
            "consolidate",
            "arrival_date",
            "user_note",
            "warehouseman_description",
            "photos",
            "created_at",
            "status_last_update_time",
        ]

    def get_arrival_date(self, package: Package):
        arrival_date = (
            package.real_arrival_date
            if package.real_arrival_date
            else package.arrival_date
        )
        if arrival_date:
            return serializers.DateField().to_representation(arrival_date)
        return None

    def get_status(self, package: Package):
        if (
            package.shipment_id
            and package.shipment.status_id
            and package.shipment.status.codename != "processing"
        ):
            return StatusSerializer(package.shipment.status, context=self.context).data

        return StatusSerializer(package.status).data

    def get_actions(self, package):
        return {
            "can_consolidate": package.can_be_consolidated_by_user,
            "can_edit": package.can_be_edited_by_user,
            "can_delete": package.can_be_deleted_by_user,
            "can_pay": package.can_be_payed_by_user,
            "can_archive": package.can_user_archive,
        }

    def get_photos(self, package):
        request = self.context.get("request")
        photos = package.photos.all()
        return [
            request.build_absolute_uri(photo.file.url) if request else photo.file.url
            for photo in photos
        ]


class PackageDetailedSerializer(PackageReadSerializer):
    additional_services = serializers.SerializerMethodField()
    has_additional_services = serializers.SerializerMethodField()

    class Meta(PackageReadSerializer.Meta):
        fields = PackageReadSerializer.Meta.fields + [
            "has_additional_services",
            "additional_services",
        ]

    def get_has_additional_services(self, package):
        return package.ordered_services.exists()

    def get_additional_services(self, package):
        ordered_services = package.ordered_services.all()

        all_services = AdditionalServiceSerializer(
            get_additional_services(
                country_id=package.source_country_id,
                type=AdditionalService.PACKAGE_TYPE,
            ).order_by("price"),
            many=True,
        ).data

        for service in all_services:
            service["selected"] = False
            service["note"] = None
            service["attachments"] = []

            for ordered_service in ordered_services:

                if service["id"] == ordered_service.service_id:
                    service["selected"] = True
                    service["is_completed"] = ordered_service.is_completed

                    if service["needs_note"]:
                        service["note"] = ordered_service.note

                    if service["needs_attachment"]:
                        service["attachments"] = [
                            attachment.file.url
                            for attachment in ordered_service.attachments.all()
                        ]

                    break

        return all_services


class ProductWriteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "type",
            "description",
            "url",
            "price",
            "price_currency",
            "quantity",
        ]
        extra_kwargs = {
            field: {"required": True, "allow_null": False}
            for field in fields
            if not field in ["type", "description", "url", "price_currency"]
        }
        extra_kwargs["quantity"]["min_value"] = 1
        extra_kwargs["price_currency"] = {"required": False}
        extra_kwargs["category"]["queryset"] = ProductCategory.objects.filter(
            is_active=True
        )

    def validate(self, data):
        category = data.get("category")
        type = data.get("type")
        description = data.get("description")

        # if category and not category.needs_description and not type:
        #    raise serializers.ValidationError({"type": msg.MISSING_PRODUCT_TYPE})

        if category and type and type.category_id != category.id:
            raise serializers.ValidationError({"type": msg.INVALID_PRODUCT_TYPE})

        if category and category.needs_description and not description:
            raise serializers.ValidationError({"description": msg.CUSTOMS_DESCRIPTION})

        return data


class PackageWriteSerializer(serializers.ModelSerializer):
    tracking_code = serializers.CharField(
        source="user_tracking_code",
        validators=[validators.UniqueValidator(queryset=Package.objects.all())],
    )
    consolidate = serializers.BooleanField(default=True)
    products = serializers.JSONField()
    recipient = serializers.PrimaryKeyRelatedField(
        queryset=Recipient.objects.filter(is_deleted=False), required=False
    )
    destination_warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.filter(
            Q(country__is_base=True) | Q(city__country__is_base=True)
        ),
        required=False,
    )
    additional_services = serializers.JSONField(required=False)

    class Meta:
        model = Package
        fields = [
            "tracking_code",
            "source_country",
            "seller",
            "user_note",
            "products",
            "attachment",
            "arrival_date",
            "consolidate",
            "recipient",
            "destination_warehouse",
            "additional_services",
        ]
        extra_kwargs = {
            field: {"required": True, "allow_null": False}
            for field in fields
            if not field
            in [
                "user_note",
                "destination_warehouse",
                "recipient",
                "arrival_date",
            ]
        }
        extra_kwargs["tracking_code"] = {
            "allow_blank": False,
            "allow_null": False,
        }
        extra_kwargs["source_country"]["queryset"] = Country.objects.filter(
            is_active=True
        )

    def validate_attachment(self, attachment):
        valid = validate_input_file(attachment)
        if not valid:
            raise serializers.ValidationError("Invalid file type, only PDF or image")
        return attachment

    def validate(self, data):
        consolidate = data.get("consolidate")
        country = data.get("country")

        if country and not country.is_packages_enabled:
            raise DisabledCountryError

        if country and (
            consolidate and not is_consolidation_enabled_for_country(country)
        ):
            raise serializers.ValidationError(msg.NO_CONSOLIDATION_FOR_THIS_COUNTRY)

        user = self.context["user"]
        # Exposing under different name to client API
        oneclick = not data.pop("consolidate", True)
        data["oneclick"] = oneclick
        recipient = data.get("recipient")
        destination_warehouse = data.get("destination_warehouse")
        # payment_method = data.get("payment_method")

        if oneclick and not destination_warehouse:
            raise serializers.ValidationError(
                {"destination_warehouse": msg.MISSING_DESTINATION_WAREHOUSE}
            )

        if oneclick and not recipient:
            raise serializers.ValidationError({"recipient": msg.MISSING_RECIPIENT})

        if oneclick and recipient and recipient.user_id != user.id:
            raise serializers.ValidationError(
                {"recipient": msg.RECIPIENT_DOES_NOT_BELONGS_TO_USER}
            )

        return data

    def validate_products(self, products):
        serializer = ProductWriteSerializer(data=products, many=True)

        if not serializer.is_valid():
            raise serializers.ValidationError(serializer.errors)

        return serializer.validated_data

    # def validate_source_country(self, country):
    #    consolidate = self.initial_data.get("consolidate", False)

    #    if country and not country.is_packages_enabled:
    #        raise DisabledCountryError

    #    if consolidate and not is_consolidation_enabled_for_country(country):
    #        raise serializers.ValidationError(msg.NO_CONSOLIDATION_FOR_THIS_COUNTRY)

    #    return country

    @transaction.atomic
    def update(self, package, validated_data):
        oneclick = validated_data.pop("oneclick", False)
        recipient = validated_data.pop("recipient", None)
        destination_warehouse = validated_data.pop("destination_warehouse", None)
        # payment_method = validated_data.pop("payment_method", None)

        products_data = validated_data.pop("products", None)
        source_country = validated_data.get("source_country", package.source_country)
        additional_services = validated_data.pop("additional_services", None)

        # Update package
        update_fields = []
        for field, value in validated_data.items():
            setattr(package, field, value)
            update_fields.append(field)

        package.save(update_fields=update_fields)
        products = package.products.select_related()

        if products_data is not None:
            for product_data in products_data:
                id_ = product_data.get("id", None)

                for product in products:
                    if product.id == id_:
                        product_update_fields = []

                        for field, value in product_data.items():
                            if field == "id":
                                continue

                            setattr(product, field, value)
                            product_update_fields.append(field)

                        product.save(update_fields=product_update_fields)

                if not id_:
                    if "price_currency" not in product_data:
                        product_data["price_currency_id"] = source_country.currency_id
                    package.products.create(
                        **product_data,
                    )

            provided_ids = [data.get("id", None) for data in products_data]

            for product in products:
                if product.id not in provided_ids:
                    product.delete()

        if oneclick:
            shipment = self._create_shipment(package, recipient, destination_warehouse)
            shipment._skip_commiting = True
            update_additional_services(
                additional_services, package=package, shipment=shipment
            )
        else:
            if package.status.codename == "problematic":
                promote_status(
                    package,
                    to_status=Status.objects.get(
                        type=Status.PACKAGE_TYPE, codename="foreign"
                    ),
                )
            update_additional_services(additional_services, package=package)

        return package

    @transaction.atomic
    def create(self, validated_data):
        # Shipment related
        oneclick = validated_data.pop("oneclick")
        # destination_user_address = validated_data.pop("destination_user_address", None)
        recipient = validated_data.pop("recipient", None)
        destination_warehouse = validated_data.pop("destination_warehouse", None)
        # payment_method = validated_data.pop("payment_method", None)
        additional_services = validated_data.pop("additional_services", [])

        products_data = validated_data.pop("products", [])
        source_country = validated_data.get("source_country")
        package = Package.objects.create(**validated_data)

        for product_data in products_data:
            price_currency = product_data.pop("price_currency", None)

            if not price_currency:
                price_currency = source_country.currency

            Product.objects.create(
                package=package,
                price_currency=price_currency,
                **product_data,
            )

        if oneclick:
            shipment = self._create_shipment(package, recipient, destination_warehouse)
            update_additional_services(
                additional_services, package=package, shipment=shipment
            )
        else:
            update_additional_services(additional_services, package=package)

        return package

    def _create_shipment(self, package, recipient, destination_warehouse):
        user = self.context["user"]
        user_note = package.user_note

        customer = user.as_customer
        return create_shipment(
            customer,
            [package],
            recipient,
            destination_warehouse,
            user_note=user_note,
            is_oneclick=True,
            # payment_method=payment_method,
        )

    def to_representation(self, instance):
        instance.refresh_from_db(fields=["shipment"])
        if instance.shipment_id:
            return ShipmentReadSerializer(instance.shipment).data
        return PackageReadSerializer(instance).data


class ShipmentReadSerializer(serializers.ModelSerializer):
    status = StatusSerializer(read_only=True)
    source_country = CountryCompactSerializer()
    destination_warehouse = WarehouseReadSerializer(read_only=True)
    # destination_user_address = AddressCompactSerializer(read_only=True)
    declared_price_currency = CurrencySerializer(read_only=True)
    total_price_currency = CurrencySerializer(read_only=True)
    discounted_total_price = serializers.DecimalField(decimal_places=2, max_digits=9)
    discounted_total_price_currency = CurrencySerializer(read_only=True)
    packages = PackageCompactSerializer(read_only=True, many=True)
    actions = serializers.SerializerMethodField()
    recipient = RecipientVeryCompactSerializer(
        read_only=True, source="recipient.real_recipient"
    )
    # payment_method = serializers.CharField(source="get_payment_method_display")
    is_declared_by_user = serializers.SerializerMethodField()
    dimensions = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = [
            "identifier",
            "number",
            "status",
            "is_archived",
            "source_country",
            "recipient",
            "destination_warehouse",
            # "destination_user_address",
            "declared_price",
            "declared_price_currency",
            "is_paid",
            "total_price",
            "total_price_currency",
            "discounted_total_price",
            "discounted_total_price_currency",
            "total_weight",
            "created_at",
            "user_note",
            "is_declared_by_user",
            "is_deleted_from_smart_customs",
            "actions",
            # "payment_method",
            "consolidate",
            "packages",
            "dimensions",
        ]

    def get_dimensions(self, shipment: Shipment):
        def _round(value):
            if value is None:
                return None
            return str(round(value, 2))

        return {
            "is_volume_considered": shipment.is_volume_considered,
            "height": _round(shipment.fixed_height),
            "width": _round(shipment.fixed_width),
            "length": _round(shipment.fixed_length),
            "volume_weight": _round(shipment.volume_weight)
            if shipment.is_volume_considered
            else None,
        }

    def get_is_declared_by_user(self, shipment: Shipment):
        exclude_from_smart_customs = getattr(
            shipment, "exclude_from_smart_customs", None
        )
        if exclude_from_smart_customs is not None:
            return shipment.is_declared_by_user or exclude_from_smart_customs
        return shipment.is_declared_by_user

    def get_actions(self, shipment: Shipment):
        return {
            "can_order_courier": shipment.courier_can_be_ordered,
            "can_pay": shipment.can_be_payed_by_user,
            "can_edit": shipment.can_be_edited_by_user,
            "can_delete": shipment.can_be_deleted_by_user,
            "can_view_bill": shipment.can_user_view_bill,
            "can_archive": shipment.can_user_archive,
        }


class ShipmentDetailedSerializer(ShipmentReadSerializer):
    additional_services = serializers.SerializerMethodField()
    has_additional_services = serializers.SerializerMethodField()
    packages = PackageDetailedSerializer(read_only=True, many=True)

    class Meta(ShipmentReadSerializer.Meta):
        fields = ShipmentReadSerializer.Meta.fields + [
            "has_additional_services",
            "additional_services",
        ]

    def get_has_additional_services(self, shipment):
        return shipment.ordered_services.exists()

    # FIXME: Code in this method and PackageDetailedSerializer are the same!
    def get_additional_services(self, shipment):
        ordered_services = shipment.ordered_services.all()
        all_services = AdditionalServiceSerializer(
            get_additional_services(
                country_id=shipment.source_country_id,
                type=AdditionalService.SHIPMENT_TYPE,
            ).order_by("price"),
            many=True,
        ).data

        for service in all_services:
            service["selected"] = False
            service["note"] = None
            service["attachments"] = []

            for ordered_service in ordered_services:

                if service["id"] == ordered_service.service_id:
                    service["selected"] = True
                    service["is_completed"] = ordered_service.is_completed

                    if service["needs_note"]:
                        service["note"] = ordered_service.note

                    if service["needs_attachment"]:
                        service["attachments"] = [
                            attachment.file.url
                            for attachment in ordered_service.attachments.all()
                        ]

                    break

        return all_services


class ShipmentWriteSerializer(serializers.ModelSerializer):
    packages = serializers.ListField(
        child=serializers.CharField(), allow_empty=False, required=True
    )
    additional_services = serializers.JSONField(required=False)
    recipient = serializers.PrimaryKeyRelatedField(
        queryset=Recipient.objects.filter(is_deleted=False), required=True
    )
    destination_warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.filter(
            Q(country__is_base=True) | Q(city__country__is_base=True)
        ),
        required=True,
    )

    class Meta:
        model = Shipment
        fields = [
            "user_note",
            "packages",
            "recipient",
            "destination_warehouse",
            "additional_services",
        ]

    def validate_recipient(self, recipient):
        customer = self.context["customer"]

        if not recipient.user_id == customer.id:
            raise serializers.ValidationError(msg.RECIPIENT_DOES_NOT_BELONGS_TO_USER)

        return recipient

    def validate_packages(self, packages):
        packages = Package.objects.filter(
            Q(user_tracking_code__in=packages) | Q(admin_tracking_code__in=packages),
            shipment__isnull=True,
        )

        for package in packages:
            if not package.can_be_consolidated_by_user:
                raise serializers.ValidationError(
                    msg.NOT_SERVICED_PACKAGE_CANNOT_BE_SENT_FMT
                    % {"tracking_code": package.trackging_code}
                )

        customer = self.context["customer"]
        invalid_packages = []

        for package in packages:
            if package.user_id != customer.id:
                invalid_packages.append(package.tracking_code)

        if invalid_packages:
            raise serializers.ValidationError(
                msg.PACKAGE_NOT_FOUND_FMT % {"tracking_codes": invalid_packages}
            )

        if len(set(map(lambda p: p.source_country_id, packages))) > 1:
            raise serializers.ValidationError(
                msg.PACKAGES_MUST_HAVE_SAME_SOURCE_COUNTRY_ERROR
            )

        return packages

    @transaction.atomic
    def create(self, validated_data):
        customer = self.context["customer"]
        packages = validated_data["packages"]
        user_note = validated_data.get("user_note", None)
        recipient = validated_data["recipient"]
        destination_warehouse = validated_data["destination_warehouse"]
        additional_services = validated_data.pop("additional_services", None)

        shipment = create_shipment(
            customer,
            packages,
            recipient,
            destination_warehouse,
            user_note=user_note,
        )
        update_additional_services(additional_services, shipment=shipment)

        shipment.refresh_from_db(fields=["number"])
        return shipment

    def to_representation(self, instance):
        return ShipmentReadSerializer(instance).data


class RecipientReadSerializer(serializers.ModelSerializer):
    city = CitySerializer()
    region = CourierRegionSerializer()
    country = CountrySerializer(source="city.country")
    is_billed_recipient = serializers.SerializerMethodField()
    gender_display = serializers.CharField(source="get_gender_display")
    monthly_spendings = serializers.SerializerMethodField()

    class Meta:
        model = Recipient
        fields = [
            "id",
            "title",
            "first_name",
            "last_name",
            "full_name",
            "gender",
            "gender_display",
            "id_pin",
            "phone_number",
            "country",
            "city",
            "region",
            "address",
            "address_extra",
            "monthly_spendings",
            "is_billed_recipient",
        ]

    def get_monthly_spendings(self, recipient):
        monthly_spendings = calculate_monthly_spendings(recipient)

        if monthly_spendings:
            return {
                "amount": monthly_spendings.amount,
                "currency": CurrencySerializer(monthly_spendings.currency).data,
                "status": monthly_spendings.status,
            }

        return None

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
    region = serializers.PrimaryKeyRelatedField(
        queryset=CourierRegion.objects.all(), required=True
    )
    is_billed_recipient = serializers.NullBooleanField(required=False)

    class Meta:
        model = Recipient
        fields = [
            "title",
            "gender",
            "first_name",
            "last_name",
            "id_pin",
            "phone_number",
            "city",
            "address",
            "address_extra",
            "region",
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
        request = self.context.get("request")
        user = request and request.user

        is_billing = self.validated_data.pop("is_billed_recipient", None)

        if is_billing is None:
            is_billing = not user.billed_recipient_id

        recipient = super().save(*args, **kwargs)
        if is_billing is not None and user:
            if is_billing:
                user.billed_recipient = recipient
                recipient._is_billed_recipient = True
                user.save(update_fields=["billed_recipient"])
                fetch_user_data_from_government_resource.delay(user.billed_recipient.id)
            elif user.billed_recipient_id == recipient.id:
                user.billed_recipient = None
                user.save(update_fields=["billed_recipient"])

        return recipient

    def to_representation(self, instance):
        return RecipientReadSerializer(instance, context=self.context).data


# class AddressReadSerializer(serializers.ModelSerializer):
#     country = CountrySerializer(read_only=True)
#     nearby_warehouse = WarehouseReadSerializer(read_only=True)
#     is_billing_address = serializers.SerializerMethodField()

#     class Meta:
#         # model = Address
#         fields = [
#             "id",
#             "country",
#             "title",
#             "nearby_warehouse",
#             "region",
#             "district",
#             "city",
#             "zip_code",
#             "street_name",
#             "house_number",
#             "unit_number",
#             "recipient_first_name",
#             "recipient_last_name",
#             "recipient_phone_number",
#             "is_billing_address",
#         ]

#     def get_is_billing_address(self, address):
#         is_billing_address = getattr(address, "_is_billing_address", None)

#         if is_billing_address is not None:
#             return is_billing_address

#         billing_address_id = self.context.get("billing_address_id")
#         return address.id == billing_address_id


# class AddressWriteSerializer(serializers.ModelSerializer):
#     user = serializers.HiddenField(default=serializers.CurrentUserDefault())
#     is_billing_address = serializers.BooleanField(default=False)

#     class Meta:
#         # model = Address
#         fields = [
#             "id",
#             "user",
#             "country",
#             "title",
#             "nearby_warehouse",
#             "region",
#             "district",
#             "city",
#             "zip_code",
#             "street_name",
#             "house_number",
#             "unit_number",
#             "recipient_first_name",
#             "recipient_last_name",
#             "recipient_phone_number",
#             "is_billing_address",
#         ]
#         extra_kwargs = {"country": {"queryset": Country.objects.filter(is_base=True)}}

#     def validate_recipient_phone_number(self, phone_number):
#         number, _ = validate_phone_number(phone_number, validate_user=False)
#         return number

#     def validate_nearby_warehouse(self, warehouse):
#         country_id = self.initial_data.get("country")

#         if not country_id:
#             current_address = self.context.get("current_address")
#             if current_address:
#                 country_id = str(current_address.country_id)

#         if str(warehouse.country_id) != str(country_id):
#             raise serializers.ValidationError(
#                 msg.INVALID_WAREHOUSE_FOR_SELECTED_COUNTRY
#             )

#         return warehouse

#     def to_representation(self, instance):
#         return AddressReadSerializer(instance).data

#     def save(self, *args, **kwargs):
#         request = self.context.get("request")
#         user = request and request.user

#         is_billing = self.validated_data.pop(
#             "is_billing_address", user.addresses.filter(is_deleted=False).count() == 0
#         )
#         address = super().save(*args, **kwargs)

#         if is_billing:
#             if user:
#                 user.billing_address = address
#                 user.save(update_fields=["billing_address"])
#                 address._is_billing_address = True

#         return address


class PaymentSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()
    purpose = serializers.CharField(source="get_purpose_display")
    type = serializers.SerializerMethodField()
    object = serializers.SerializerMethodField()
    currency = CurrencySerializer(read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "invoice_number",
            "object",
            "purpose",
            "type",
            "created_at",
            "amount",
            "currency",
            "completed",
            "is_archived",
            "actions",
        ]

    def get_type(self, transaction):
        if transaction.is_partial and transaction.from_balance_amount:
            transaction.type = Transaction.BALANCE
            balance_type = transaction.get_type_display()
            transaction.type = Transaction.CARD
            card_type = transaction.get_type_display()
            return "%s/%s" % (card_type, balance_type)

        return transaction.get_type_display()

    def get_amount(self, transaction):
        if transaction.is_partial:
            transaction.amount += Converter.convert(
                transaction.from_balance_amount,
                transaction.from_balance_currency.code,
                transaction.currency.code,
            )

        elif (
            transaction.object_type_id
            and transaction.object_type.model == "courierorder"
        ):
            shipment_transactions = get_courier_order_related_shipment_transactions(
                transaction.related_object
            )
            for shipment_transaction in shipment_transactions:
                transaction.amount += Converter.convert(
                    shipment_transaction.amount,
                    shipment_transaction.currency.code,
                    transaction.currency.code,
                )

        return str(transaction.amount)

    def get_object(self, transaction):
        if transaction.purpose == Transaction.MERGED:
            return {
                "identifier": str(transaction.invoice_number).upper(),
                "type": "payment",
                "title": ", ".join(
                    [
                        str(t.related_object.serialize_for_payment().get("title"))
                        for t in transaction.children.all()
                    ]
                ),
                "weight": None,
                "is_oneclick": False,
            }
        if transaction.related_object:
            return transaction.related_object.serialize_for_payment()
        return None

    def get_actions(self, transaction):
        return {"can_archive": transaction.can_user_archive}


class NotificationCompactSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="web_title")

    class Meta:
        model = Notification
        fields = ["id", "type", "title", "is_seen", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    object = serializers.SerializerMethodField()
    title = serializers.CharField(source="web_title")
    body = serializers.CharField(source="web_text")

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "title",
            "body",
            "is_seen",
            "created_at",
            "object",
        ]

    def get_object(self, notification):
        if notification.related_object:
            return notification.related_object.serialize_for_notification()
        return None


class CommissionPriceCalculatorSerializer(serializers.Serializer):
    price = serializers.DecimalField(max_digits=9, decimal_places=2)
    price_currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.all())


class BalanceAddSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=9, decimal_places=2)
    currency = serializers.SlugRelatedField(
        queryset=Currency.objects.all(),
        slug_field="code",
    )

    # def validate(self, data):
    #     currency = data["currency"]
    #     amount = data["amount"]
    #     if currency.code != "USD":
    #         data["amount"] = Converter.convert(amount, currency.code, "USD")
    #         data["currency"] = Currency.objects.get(code="USD")
    #     return data


class SubscriberWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriber
        fields = ["email"]


class ContactUsMessageWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactUsMessage
        fields = ["full_name", "phone_number", "text"]

    def validate_phone_number(self, number):
        validate_phone_number(number, validate_user=False)
        return number


class TicketCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketCategory
        fields = [
            "id",
            "title",
            "can_select_order",
            "can_select_package",
            "can_select_shipment",
            "can_select_payment",
        ]


class TicketReadSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()
    category = TicketCategorySerializer()
    status = StatusSerializer()
    attachments = serializers.SerializerMethodField()
    object = serializers.SerializerMethodField()
    can_add_comment = serializers.BooleanField(source="can_user_add_comment")

    class Meta:
        model = Ticket
        fields = [
            "id",
            "number",
            "category",
            "status_last_update_time",
            "status",
            "is_archived",
            "object",
            "problem_description",
            "created_at",
            "updated_at",
            "can_add_comment",
            "attachments",
            "actions",
        ]

    def get_object(self, ticket: Ticket):
        if ticket.related_object:
            return ticket.related_object.serialize_for_ticket()
        return None

    def get_attachments(self, ticket: Ticket):
        attachment_links = ticket.ticket_attachments.values_list("file", flat=True)
        request = self.context["request"]

        return [
            request.build_absolute_uri(os.path.join(settings.MEDIA_URL, link))
            for link in attachment_links
        ]

    def get_actions(self, ticket):
        return {"can_archive": ticket.can_user_archive}


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "full_name",
        ]


class TicketCommentReadSerializer(serializers.ModelSerializer):
    author = AuthorSerializer()
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = TicketComment
        fields = [
            "id",
            "author",
            "is_by_customer_service",
            "body",
            "attachments",
            "created_at",
        ]

    def get_attachments(self, comment: TicketComment):
        attachment_links = comment.comment_attachments.values_list("file", flat=True)
        request = self.context["request"]

        return [
            request.build_absolute_uri(os.path.join(settings.MEDIA_URL, link))
            for link in attachment_links
        ]


class TicketDetailedSerializer(TicketReadSerializer):
    comments = serializers.SerializerMethodField()

    class Meta(TicketReadSerializer.Meta):
        fields = TicketReadSerializer.Meta.fields + ["comments"]

    def get_comments(self, ticket: Ticket):
        return TicketCommentReadSerializer(
            ticket.comments.order_by("-id"), many=True, context=self.context
        ).data


class TicketRelatedObjectField(serializers.JSONField):
    PACKAGE_TYPE = "package"
    ORDER_TYPE = "order"
    SHIPMENT_TYPE = "shipment"
    PAYMENT_TYPE = "payment"

    def to_internal_value(self, data):
        data = super().to_internal_value(data)

        object_type = data.get("type")
        object_identifier = data.get("identifier")
        print(object_type, object_identifier)
        if object_type == self.PACKAGE_TYPE:
            return Package.objects.filter(
                Q(user_tracking_code=object_identifier)
                | Q(admin_tracking_code=object_identifier)
            ).first()
        elif object_type == self.ORDER_TYPE:
            return Order.objects.filter(order_code=object_identifier).first()
        elif object_type == self.SHIPMENT_TYPE:
            return Shipment.objects.filter(number=object_identifier).first()
        elif object_type == self.PAYMENT_TYPE:
            return Transaction.objects.filter(invoice_number=object_identifier).first()

        return None


class TicketWriteSerializer(serializers.ModelSerializer):
    related_object = TicketRelatedObjectField(required=False)

    class Meta:
        model = Ticket
        fields = ["id", "category", "problem_description", "related_object"]

    def validate_related_object(
        self,
        related_object: Optional[Union[Shipment, Package, Transaction, Order]],
    ):
        request = self.context["request"]
        user = request.user
        if related_object and related_object.user_id != user.id:
            raise serializers.ValidationError(msg.ID_INVALID_FOR_PROVIDED_TYPE)
        return related_object

    @transaction.atomic
    def save(self, *args, **kwargs):
        request = self.context["request"]
        ticket = super().save(*args, **kwargs)

        if request.FILES:
            for attachment in request.data.getlist("attachments"):
                user_input_file = File(attachment)
                if validate_input_file(user_input_file):
                    TicketAttachment.objects.create(
                        ticket=ticket, file=File(attachment)
                    )

        return ticket

    def to_representation(self, instance):
        return TicketReadSerializer(instance, context=self.context).data


class TicketCommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketComment
        fields = [
            "body",
        ]

    @transaction.atomic
    def save(self, *args, **kwargs):
        comment = super().save(*args, **kwargs)
        request = self.context["request"]

        if request.FILES:
            for attachment in request.data.getlist("attachments"):
                TicketAttachment.objects.create(comment=comment, file=File(attachment))

        comment.ticket.answered_by_admin = False
        comment.ticket.save(update_fields=["answered_by_admin"])

        return comment

    def to_representation(self, instance):
        return TicketCommentReadSerializer(instance, context=self.context).data


class ShipmentCompactSerializer(serializers.ModelSerializer):
    status = StatusSerializer()
    source_country = CountrySerializer()
    total_price_currency = CurrencySerializer()

    class Meta:
        model = Shipment
        fields = [
            "identifier",
            "status",
            "number",
            "source_country",
            "is_paid",
            "total_price",
            "total_price_currency",
        ]


class CourierOrderReadSerializer(serializers.ModelSerializer):
    actions = serializers.SerializerMethodField()
    status = StatusSerializer()
    recipient = RecipientReadSerializer(source="recipient.real_recipient")
    shipments = ShipmentCompactSerializer(many=True)
    region = CourierRegionSerializer()
    total_price_currency = CurrencySerializer()
    tariff = CourierTariffSerializer()
    discounted_total_price = serializers.DecimalField(decimal_places=2, max_digits=9)
    discounted_total_price_currency = CurrencySerializer(read_only=True)

    class Meta:
        model = CourierOrder
        fields = [
            "number",
            "identifier",
            "status",
            "is_archived",
            "region",
            "recipient",
            "tariff",
            "total_price",
            "total_price_currency",
            "discounted_total_price",
            "discounted_total_price_currency",
            "failed_reason",
            "shipments",
            "is_paid",
            "created_at",
            "updated_at",
            "status_last_update_time",
            "additional_note",
            "actions",
        ]

    def get_actions(self, courier_order):
        return {"can_archive": courier_order.can_user_archive}


class CourierOrderWriteSerializer(serializers.Serializer):
    shipments = serializers.ListField(
        child=serializers.SlugRelatedField(
            queryset=Shipment.objects.filter(
                ~Q(
                    status__codename__in=[
                        "done",
                        "deleted",
                    ]
                ),
                confirmed_properties=True,
                total_price__gt=0,
                total_price_currency__isnull=False,
                courier_order__isnull=True,
            ),
            slug_field="number",
        ),
        allow_null=False,
        allow_empty=False,
    )
    tariff = serializers.PrimaryKeyRelatedField(queryset=CourierTariff.objects.all())
    recipient = serializers.PrimaryKeyRelatedField(queryset=Recipient.objects.all())
    additional_note = serializers.CharField(required=False)
    region = serializers.PrimaryKeyRelatedField(queryset=CourierRegion.objects.all())

    def validate_shipments(self, shipments):
        user = self.context["request"].user

        invalid_shipment_numbers = []
        for shipment in shipments:
            if shipment.user_id != user.id:
                invalid_shipment_numbers.append(shipment.number)

        if invalid_shipment_numbers:
            raise serializers.ValidationError(
                msg.SHIPMENTS_DOES_NOT_BELONGS_TO_USER_FMT
                % {"numbers": ", ".join(invalid_shipment_numbers)}
            )

        return shipments

    def validate(self, data):
        recipient = data.get("recipient")
        tariff = data.get("tariff")
        region = data.get("region")

        if not region.area.tariffs.filter(id=tariff.id).exists():
            raise serializers.ValidationError(
                {"tariff": msg.INVALID_TARIFF_FOR_SELECTED_REGION}
            )

        return data

    def validate_recipient(self, recipient):
        user = self.context["request"].user

        if not recipient.user_id == user.id:
            raise serializers.ValidationError(msg.RECIPIENT_DOES_NOT_BELONGS_TO_USER)

        return recipient


class UlduzumIdenticalCodeSerializer(serializers.Serializer):
    identical_code = serializers.CharField(required=True)

    def validate_identical_code(self, code: str):
        if not code.isalnum():
            raise serializers.ValidationError(msg.ULDUZUM_IDENTICAL_CODE_INVALID)

        return code


class UlduzumWithShipmentSerializer(UlduzumIdenticalCodeSerializer):
    shipment = serializers.SlugRelatedField(
        queryset=Shipment.objects.filter(
            total_price__isnull=False, total_price_currency__isnull=False
        ),
        slug_field="number",
    )

    def validate_shipment(self, shipment: Shipment):
        if shipment.user_id and shipment.user_id != self.context["user_id"]:
            raise serializers.ValidationError(
                msg.SHIPMENTS_DOES_NOT_BELONGS_TO_USER_FMT
                % {"numbers": shipment.number}
            )

        return shipment


class ArchiveSerializer(serializers.Serializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = self.initial_data["instance"]

    def validate(self, attrs):
        if self.instance.already_archived():
            raise serializers.ValidationError(msg.ALREADY_ARCHIVED)

        if not self.instance.can_user_archive:
            raise serializers.ValidationError(msg.CANNOT_ARCHIVED)

        return attrs

    def perform_archive(self):
        self.instance.archive()
        self.instance.save()


class BulkArchiveSerializer(serializers.Serializer):
    ARCHIVE_ACTION = "archive"
    UNARCHIVE_ACTION = "unarchive"
    ACTIONS = [ARCHIVE_ACTION, UNARCHIVE_ACTION]

    action = serializers.ChoiceField(
        choices=ACTIONS, allow_null=True, default=ARCHIVE_ACTION
    )
    ids = serializers.ListField(
        child=serializers.CharField(), allow_empty=False, required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def perform_archive(self, queryset):
        action_method_map = {
            self.ARCHIVE_ACTION: self._archive,
            self.UNARCHIVE_ACTION: self._unarchive,
        }
        print(self.validated_data["action"])
        action_executer = action_method_map[self.validated_data["action"]]
        action_executer(queryset)

    def _archive(self, queryset):
        for obj in queryset:
            if not obj.already_archived() and obj.can_user_archive:
                obj.archive()
                obj.save(update_fields=["is_archived"])

    def _unarchive(self, queryset):
        for obj in queryset:
            if obj.already_archived():
                obj.unarchive()
                obj.save(update_fields=["is_archived"])
