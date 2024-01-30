import json

from django.db import transaction as db_transaction
from django.db.models import Q, Prefetch
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from rest_framework import serializers
from rest_framework import validators
from drf_extra_fields.fields import Base64ImageField

from ontime import messages as msg
from domain.services import (
    map_package_properties_to_shipment,
    promote_status,
    add_shipments_to_box,
    create_shipment,
    create_notification,
    confirm_shipment_properties,
)
from domain.conf import Configuration
from domain.exceptions.logic import BoxWithUnconfirmedShipmentError
from core.converter import Converter
from core.serializers.admin import (
    CurrencyCompactSerializer,
    CountryCompactSerializer,
    CityCompactSerializer,
)
from fulfillment.serializers.common import (
    StatusSerializer,
    ProductCategoryCompactSerializer,
    ProductTypeExtraCompactSerializer,
    WarehouseReadSerializer,
)
from fulfillment.serializers.admin.common import WarehouseDetailedSerializer
from customer.models import Recipient, Customer
from fulfillment.models import (
    PackageAdditionalService,
    AdditionalService,
    ShipmentAdditionalService,
    Package,
    PackagePhoto,
    Product,
    ProductPhoto,
    Shipment,
    Box,
    Transportation,
    Status,
    WarehousemanProfile,
    Warehouse,
    NotificationEvent as EVENTS,
    Transaction,
)


class WarehousemanSerializer(serializers.ModelSerializer):
    warehouse = WarehouseDetailedSerializer(read_only=True)

    class Meta:
        model = WarehousemanProfile
        fields = ["warehouse"]


class AdditionalServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdditionalService
        fields = [
            "id",
            "title",
            "description",
            "needs_attachment",
            "needs_note",
        ]


class ProductReadSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source="normalized_description", read_only=True)
    price_currency = CurrencyCompactSerializer(read_only=True)
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
        return [
            (request and request.build_absolute_uri(photo.file.url) or photo.file.url)
            for photo in product.photos.all()
        ]


class RecipientReadSerializer(serializers.ModelSerializer):
    city = CityCompactSerializer(source="real_recipient.city")
    country = CountryCompactSerializer(source="real_recipient.city.country")
    gender_display = serializers.CharField(source="get_gender_display")

    class Meta:
        model = Recipient
        fields = [
            "id",
            "full_name",
            "gender_display",
            "id_pin",
            "phone_number",
            "country",
            "city",
            "address",
            "address_extra",
        ]


class ShipmentAdditionalServiceReadSerializer(serializers.ModelSerializer):
    service = AdditionalServiceSerializer(read_only=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = PackageAdditionalService
        fields = ["id", "note", "is_completed", "attachments", "service"]

    def get_attachments(self, shipment_service):
        request = self.context.get("request")
        attachment_urls = [
            attachment.file.url for attachment in shipment_service.attachments.all()
        ]
        if not request:
            return attachment_urls
        return map(lambda url: request.build_absolute_uri(url), attachment_urls)


class ShipmentCompactSerializer(serializers.ModelSerializer):
    destination_warehouse = WarehouseReadSerializer(read_only=True)
    recipient = RecipientReadSerializer(
        read_only=True,
    )
    declared_price_currency = CurrencyCompactSerializer(read_only=True)
    total_price_currency = CurrencyCompactSerializer(read_only=True)
    ordered_services = ShipmentAdditionalServiceReadSerializer(
        read_only=True, many=True
    )
    status = StatusSerializer()
    actions = serializers.SerializerMethodField()
    exclude_from_smart_customs = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = [
            "id",
            "total_weight",
            "number",
            "status",
            "destination_warehouse",
            "recipient",
            "declared_price",
            "declared_price_currency",
            "declared_items_title",
            "total_price",
            "total_price_currency",
            "actions",
            "exclude_from_smart_customs",
            "is_declared_by_user",
            "is_serviced",
            "ordered_services",
        ]

    def get_exclude_from_smart_customs(self, shipment):
        return getattr(shipment, "exclude_from_smart_customs", None)

    def get_actions(self, shipment):
        return {"can_mark_as_serviced": shipment.can_be_marked_as_serviced}


class CustomerCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["first_name", "last_name", "client_code", "full_phone_number"]


class PackageReadSerializer(serializers.ModelSerializer):
    customer = CustomerCompactSerializer(read_only=True, source="user")
    status = StatusSerializer(read_only=True)
    source_country = CountryCompactSerializer(read_only=True)
    products = ProductReadSerializer(many=True, read_only=True)
    is_oneclick = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    has_services = serializers.BooleanField(read_only=True)
    attachment = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            "id",
            "tracking_code",
            "status",
            "source_country",
            "seller",
            "customer",
            "is_accepted",
            "is_oneclick",
            "is_by_assistant",
            "weight",
            "is_volume_considered",
            "height",
            "width",
            "length",
            "shelf",
            "warehouseman_description",
            "photos",
            "attachment",
            "arrival_date",
            "created_at",
            "status_last_update_time",
            "has_services",
            "actions",
            "products",
        ]

    def get_attachment(self, package: Package):
        request = self.context.get("request")

        if not package.attachment:
            return None

        if request:
            return request.build_absolute_uri(package.attachment.url)

        return package.attachment.url

    def get_is_oneclick(self, package):
        return bool(package.shipment)

    def get_photos(self, package):
        request = self.context.get("request")

        return [
            (request and request.build_absolute_uri(photo.file.url) or photo.file.url)
            for photo in package.photos.all()
        ]

    def get_actions(self, package):
        return {"can_mark_as_serviced": package.can_be_marked_as_serviced}


class PackageAdditionalServiceReadSerializer(serializers.ModelSerializer):
    service = AdditionalServiceSerializer(read_only=True)
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = PackageAdditionalService
        fields = ["id", "note", "is_completed", "attachments", "service"]

    def get_attachments(self, package_service):
        request = self.context.get("request")
        attachment_urls = [
            attachment.file.url for attachment in package_service.attachments.all()
        ]
        if not request:
            return attachment_urls
        return map(lambda url: request.build_absolute_uri(url), attachment_urls)


class PackageDetailedSerializer(PackageReadSerializer):
    shipment = ShipmentCompactSerializer(read_only=True)
    ordered_services = PackageAdditionalServiceReadSerializer(read_only=True, many=True)

    class Meta(PackageReadSerializer.Meta):
        fields = PackageReadSerializer.Meta.fields + [
            "shipment",
            "is_serviced",
            "ordered_services",
        ]


class PackageWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = [
            "source_country",
            "seller",
            "weight",
            "is_volume_considered",
            "height",
            "width",
            "length",
            "shelf",
        ]

    @db_transaction.atomic
    def save(self, *args, **kwargs):
        package = super().save(*args, **kwargs)
        map_package_properties_to_shipment(package)

    def to_representation(self, instance):
        return PackageReadSerializer(instance).data


class BoxSerializer(serializers.ModelSerializer):
    shipments = serializers.ListField(
        child=serializers.CharField(), write_only=True, allow_null=True, required=False
    )
    real_total_weight = serializers.DecimalField(
        read_only=True, decimal_places=3, max_digits=9
    )
    shipments_count = serializers.IntegerField(read_only=True)
    transportation_number = serializers.CharField(
        source="transportation.number", read_only=True
    )

    class Meta:
        model = Box
        fields = [
            "id",
            "box_number",
            "code",
            "total_weight",
            "real_total_weight",
            "shipments_count",
            "destination_warehouse",
            "transportation_number",
            "shipments",
            "height",
            "width",
            "length",
        ]
        read_only_fields = ["code"]
        extra_kwargs = {"destination_warehouse": {"required": False}}

    def validate_destination_warehouse(self, warehouse):
        current_warehouse_id = self.context.get("current_warehouse_id")

        if current_warehouse_id and str(warehouse.id) == str(current_warehouse_id):
            raise serializers.ValidationError(msg.CANT_SEND_TO_YOUR_WAREHOUSE)

        return warehouse

    @db_transaction.atomic
    def save(self, *args, **kwargs):
        shipment_numbers = self.validated_data.pop("shipments", None)
        box = super().save(*args, **kwargs)

        current_warehouse_id = self.context.get("current_warehouse_id")
        if current_warehouse_id:
            add_shipments_to_box(
                box, current_warehouse_id, shipment_numbers, add=False, force=True
            )


class ShipmentReadSerializer(serializers.ModelSerializer):
    status = StatusSerializer(read_only=True)
    destination_warehouse = WarehouseReadSerializer(read_only=True)
    recipient = RecipientReadSerializer(
        read_only=True,
    )
    declared_price_currency = CurrencyCompactSerializer(read_only=True)
    total_price_currency = CurrencyCompactSerializer(read_only=True)
    packages = PackageReadSerializer(read_only=True, many=True)
    actions = serializers.SerializerMethodField()
    box = BoxSerializer(read_only=True)
    has_services = serializers.BooleanField(read_only=True)
    exclude_from_smart_customs = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = [
            "id",
            "identifier",
            "number",
            "status",
            "destination_warehouse",
            "recipient",
            "declared_price",
            "declared_price_currency",
            "total_price",
            "total_price_currency",
            "total_weight",
            "is_dangerous",
            "fixed_height",
            "fixed_width",
            "fixed_length",
            "is_volume_considered",
            "confirmed_properties",
            "contains_batteries",
            "created_at",
            "user_note",
            "has_services",
            # "payment_method",
            "is_oneclick",
            "shelf",
            "box",
            "is_declared_by_user",
            "exclude_from_smart_customs",
            "is_deleted_from_smart_customs",
            "actions",
            "packages",
        ]

    def get_exclude_from_smart_customs(self, shipment):
        return getattr(shipment, "exclude_from_smart_customs", None)

    def get_actions(self, shipment: Shipment):
        return {
            "can_confirm": shipment.can_be_confirmed_by_warehouseman,
            "can_edit": shipment.can_be_updated_by_warehouseman,
            "can_mark_as_serviced": shipment.can_be_marked_as_serviced,
            "can_print_our_invoice": shipment.packages.filter(
                is_by_assistant=True
            ).exists(),
            "can_be_placed_in_a_box": shipment.is_declared_by_user,
        }


class AcceptedShipmentReadSerializer(ShipmentReadSerializer):
    other_shipments_shelves = serializers.SerializerMethodField()

    class Meta(ShipmentReadSerializer.Meta):
        fields = ShipmentReadSerializer.Meta.fields + [
            "other_shipments_shelves",
        ]

    def get_other_shipments_shelves(self, shipment: Shipment):
        """Return shelves of other shipments for currency user in the accepted warehouse."""
        user_id = shipment.user_id
        other_shipments = Shipment.objects.filter(
            destination_warehouse_id=shipment.destination_warehouse_id,
            user_id=shipment.user_id,
            status__codename="received",
            shelf__isnull=False,
        )
        return list(other_shipments.values_list("shelf", flat=True))


class ShipmentDetailedSerializer(ShipmentReadSerializer):
    ordered_services = ShipmentAdditionalServiceReadSerializer(
        read_only=True, many=True
    )

    class Meta(ShipmentReadSerializer.Meta):
        fields = ShipmentReadSerializer.Meta.fields + [
            "is_serviced",
            "ordered_services",
        ]


class ShipmentWriteSerializer(serializers.ModelSerializer):
    total_weight = serializers.DecimalField(
        max_digits=9, decimal_places=3, required=True, source="fixed_total_weight"
    )

    class Meta:
        model = Shipment
        fields = [
            "total_weight",
            "is_dangerous",
            "fixed_height",
            "fixed_width",
            "fixed_length",
            "is_volume_considered",
            "contains_batteries",
            "shelf",
            "box",
            "staff_note",
            # "confirmed_properties",
        ]

    @db_transaction.atomic
    def save(self, **kwargs):
        current_shipment = self.instance
        remove_from_box = (
            "box" in self.validated_data and self.validated_data["box"] is None
        )
        box = self.validated_data.pop("box", None)

        # if (
        #     current_shipment
        #     and self.instance.confirmed_properties
        #     and box
        #     and current_shipment.can_be_placed_in_a_box
        # ):
        #     current_shipment.box = box
        #     current_shipment.save(update_fields=["box"])
        #     return current_shipment

        shipment = super().save(**kwargs)

        if shipment.total_price and shipment.total_price_currency_id:
            confirm_shipment_properties(shipment)

        if box and shipment.total_price and shipment.total_price_currency_id:
            # Bypass "confirmed_properties" check
            add_shipments_to_box(box, shipments=[shipment], add=True, force=True)
            shipment.save(update_fields=["confirmed_properties"])

        if remove_from_box:
            shipment.box = None
            shipment.save(update_fields=["box"])

        return shipment

    def to_representation(self, instance):
        return ShipmentReadSerializer(instance, context=self.context).data


class PlaceShipmentIntoBoxSerializer(serializers.ModelSerializer):
    total_weight = serializers.DecimalField(
        max_digits=9, decimal_places=3, required=True, source="fixed_total_weight"
    )

    class Meta:
        model = Shipment
        fields = [
            "box",
            "shelf",
            "is_dangerous",
            "contains_batteries",
            "staff_note",
            "total_weight",
            "fixed_height",
            "fixed_width",
            "fixed_length",
            "is_volume_considered",
        ]

    @db_transaction.atomic
    def save(self, *args, **kwargs):
        shipment: Shipment = self.instance
        shipment._skip_box_adding = True
        remove_from_box = (
            "box" in self.validated_data and self.validated_data.get("box") is None
        )
        box = self.validated_data.pop("box", None)

        super().save(*args, **kwargs)

        if (
            box
            and shipment
            and shipment.pk
            and shipment.total_price
            and shipment.total_price_currency_id
        ):
            add_shipments_to_box(box, shipments=[shipment], add=True, force=True)

        if remove_from_box:
            shipment.box = None
            shipment.save(update_fields=["box"])

        print(self.validated_data)
        total_weight = self.validated_data.get(
            "fixed_total_weight", shipment.fixed_total_weight
        )
        height = self.validated_data.get("fixed_height", shipment.fixed_height)
        length = self.validated_data.get("fixed_length", shipment.fixed_length)
        width = self.validated_data.get("fixed_width", shipment.fixed_width)
        is_volume_considered = self.validated_data.get(
            "is_volume_considered", shipment.is_volume_considered
        )
        shipment.fixed_total_weight = total_weight
        shipment.fixed_length = length
        shipment.fixed_width = width
        shipment.fixed_height = height
        shipment.is_volume_considered = is_volume_considered
        shipment._must_recalculate = True
        shipment._accepted = False
        shipment._update_declared_price = True
        shipment._skip_box_adding = False
        shipment.save()

        return shipment

    def to_representation(self, instance):
        return ShipmentReadSerializer(instance, context=self.context).data


class ShelfPlaceSerializer(serializers.Serializer):
    shelf = serializers.CharField(max_length=255, required=True)


class BoxDetailedSerializer(BoxSerializer):
    source_warehouse = WarehouseDetailedSerializer(read_only=True)
    destination_warehouse = WarehouseDetailedSerializer(read_only=True)
    shipments = ShipmentCompactSerializer(many=True, read_only=True)

    class Meta(BoxSerializer.Meta):
        fields = BoxSerializer.Meta.fields + [
            "source_warehouse",
            "destination_warehouse",
            "shipments",
        ]


class TransportationReadSerializer(serializers.ModelSerializer):
    source_city = CityCompactSerializer(read_only=True)
    destination_city = CityCompactSerializer(read_only=True)
    boxes_count = serializers.IntegerField(read_only=True)
    type = serializers.CharField(source="get_type_display")

    class Meta:
        model = Transportation
        fields = [
            "id",
            "number",
            "type",
            "is_ar",
            "source_city",
            "destination_city",
            "departure_time",
            "arrival_time",
            "is_completed",
            "boxes_count",
        ]


class TransportationWriteSerializer(serializers.ModelSerializer):
    boxes = serializers.ListField(
        child=serializers.CharField(), allow_empty=True, required=False
    )

    class Meta:
        model = Transportation
        fields = [
            "number",
            "source_city",
            "destination_city",
            "arrival_time",
            "departure_time",
            # "destination_warehouse",
            # "is_completed",
            "is_ar",
            "boxes",
        ]

    def to_representation(self, instance):
        return TransportationDetailedSerializer(instance).data

    @db_transaction.atomic
    def save(self, *args, **kwargs):
        current_warehouse_id = self.context.get("current_warehouse_id")
        box_codes = self.validated_data.pop("boxes", None)
        transportation = super().save(*args, **kwargs)

        if current_warehouse_id:
            boxes = Box.objects.filter(
                Q(transportation=transportation) | Q(transportation__isnull=True),
                code__in=box_codes or [],
                source_warehouse_id=current_warehouse_id,
            ).prefetch_related(Prefetch("shipments", to_attr="prefetched_shipments"))

            if box_codes is not None:
                invalid_shipments = []
                for box in boxes:
                    for shipment in box.prefetched_shipments:
                        if not shipment.confirmed_properties:
                            invalid_shipments.append(shipment)

                if invalid_shipments:
                    raise BoxWithUnconfirmedShipmentError(shipments=invalid_shipments)

                transportation.boxes.set(boxes)

                for box in boxes:
                    for shipment in box.prefetched_shipments:
                        promote_status(
                            shipment,
                            to_status=Status.objects.get(
                                type=Status.SHIPMENT_TYPE, codename="ontheway"
                            ),
                        )

        return transportation


class TransportationDetailedSerializer(TransportationReadSerializer):
    boxes = BoxDetailedSerializer(many=True, read_only=True)

    class Meta(TransportationReadSerializer.Meta):
        fields = TransportationReadSerializer.Meta.fields + ["boxes"]


class TransportationCitySerializer(CityCompactSerializer):
    is_default = serializers.BooleanField(read_only=True)

    class Meta(CityCompactSerializer.Meta):
        fields = CityCompactSerializer.Meta.fields + ["is_default"]


class ProductWriteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    photos = serializers.ListField(
        child=Base64ImageField(required=False),
        allow_null=True,
        allow_empty=True,
        required=False,
    )

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
            "warehouseman_description",
            "photos",
        ]
        extra_kwargs = {
            field: {"required": True, "allow_null": False}
            for field in fields
            if not field
            in [
                "type",
                "description",
                "url",
                "warehouseman_description",
                # "photos",
            ]
        }
        extra_kwargs["quantity"]["min_value"] = 1

    def validate(self, data):
        category = data.get("category")
        type = data.get("type")
        description = data.get("description")

        # if category and not category.needs_description and not type:
        #     raise serializers.ValidationError({"type": msg.MISSING_PRODUCT_TYPE})

        if category and type and type.category_id != category.id:
            raise serializers.ValidationError({"type": msg.INVALID_PRODUCT_TYPE})

        if category and category.needs_description and not description:
            raise serializers.ValidationError({"description": msg.CUSTOMS_DESCRIPTION})

        return data


class Base64ImageListField(serializers.ListField):
    def to_internal_value(self, data):
        real_input = None
        fixed_data = None

        if isinstance(data, list) and data:
            real_input = data[0]

        if real_input and isinstance(real_input, (str)):
            try:
                fixed_data = json.loads(real_input)
            except json.JSONDecodeError:
                pass

        if not fixed_data:
            fixed_data = data

        return super().to_internal_value(fixed_data)


class ProblematicPackageWriteSerializer(serializers.ModelSerializer):
    # We must set user_tracking_code because we are simulating that
    # this package was declared by user.
    tracking_code = serializers.CharField(
        source="user_tracking_code",
        max_length=40,
        validators=[validators.UniqueValidator(queryset=Package.objects.all())],
    )
    # products = ProductWriteSerializer(many=True, required=False)
    products = serializers.JSONField(required=False)
    recipient = serializers.PrimaryKeyRelatedField(
        queryset=Recipient.objects.all(), required=False
    )
    box = serializers.PrimaryKeyRelatedField(queryset=Box.objects.all(), required=False)
    photos = Base64ImageListField(
        child=Base64ImageField(required=False),
        allow_null=True,
        allow_empty=True,
        required=False,
    )
    is_dangerous = serializers.BooleanField(default=False)

    class Meta:
        model = Package
        fields = [
            "user",
            "tracking_code",
            "seller",
            "weight",
            "is_volume_considered",
            "height",
            "width",
            "length",
            "shelf",
            "recipient",
            "products",
            "box",
            "attachment",
            "warehouseman_description",
            "photos",
            "is_dangerous",
        ]
        extra_kwargs = {"weight": {"required": True}}

    def validate(self, data):
        products_data = data.get("products")
        recipient_data = data.get("recipient")
        seller = data.get("seller")

        if not (products_data and recipient_data and seller):
            self.must_create_shipment = False
        else:
            self.must_create_shipment = True

        shelf = data.get("shelf")
        box = data.get("box")

        if not (box or shelf):
            raise serializers.ValidationError(
                {"box": (msg.ONE_IS_REQUIRED), "shelf": (msg.ONE_IS_REQUIRED)}
            )

        return data

    def validate_products(self, products):
        serializer = ProductWriteSerializer(data=products, many=True)

        if not serializer.is_valid():
            raise serializers.ValidationError(serializer.errors)

        return serializer.validated_data

    @db_transaction.atomic
    def create(self, validated_data):
        box = validated_data.pop("box", None)
        products_data = validated_data.pop("products", [])
        recipient = validated_data.pop("recipient", None)
        current_warehouse = self.context["current_warehouse"]
        source_country = current_warehouse.city.country
        provided_package_photos = validated_data.pop("photos", [])
        is_dangerous = validated_data.pop("is_dangerous", False)

        if not self.must_create_shipment:
            status = Status.objects.get(
                type=Status.PACKAGE_TYPE,
                codename="problematic",
            )
        else:
            status = Status.objects.get(type=Status.PACKAGE_TYPE, codename="foreign")

        validated_data["status"] = status
        validated_data["is_serviced"] = True

        package = Package.objects.create(**validated_data)
        package_photos = []

        for provided_package_photo in provided_package_photos:
            package_photos.append(
                PackagePhoto(
                    file=provided_package_photo,
                    created_at=timezone.now(),
                    package=package,
                )
            )

        if package_photos:
            PackagePhoto.objects.bulk_create(package_photos)

        if products_data:
            for product_data in products_data:
                photos = product_data.pop("photos", [])
                product = Product.objects.create(package=package, **product_data)

                photo_instances = []
                for photo in photos:
                    photo_instances.append(
                        ProductPhoto(
                            file=photo, product=product, created_at=timezone.now()
                        )
                    )
                if photo_instances:
                    ProductPhoto.objects.bulk_create(photo_instances)

        if self.must_create_shipment:
            destination_warehouse = (
                package.user.prefered_warehouse
                or Warehouse.objects.filter(
                    country__id=recipient.city.country_id, is_universal=True
                ).first()
            )
            shipment: Shipment = create_shipment(
                package.user,
                [package],
                recipient,
                destination_warehouse,
                is_oneclick=True,
                is_serviced=True,
                _accepted=True,
                is_dangerous=is_dangerous,
                skip_comitting=True,
            )
            shipment.fixed_total_weight = validated_data.get("weight")
            shipment._must_recalculate = True
            shipment.save()
            map_package_properties_to_shipment(package, only_dimensions=True)
            shipment._skip_commiting = True

            if box and shipment.total_price and shipment.total_price_currency_id:
                # Bypass "confirmed_properties" check
                add_shipments_to_box(box, shipments=[shipment], add=True, force=True)
            elif shipment.total_price and shipment.total_price_currency_id:
                confirm_shipment_properties(shipment)
        else:
            create_notification(
                package, EVENTS.ON_PACKAGE_STATUS_PROBLEMATIC, [package, package.user]
            )

        if package.shipment_id:
            package.shipment.refresh_from_db(fields=["number"])
        return package

    def to_representation(self, instance):
        return PackageDetailedSerializer(instance, context=self.context).data


class AirwayBillSerializer(serializers.ModelSerializer):
    source_city = serializers.SerializerMethodField()
    dimensions = serializers.SerializerMethodField()
    recipient = RecipientReadSerializer()
    customer = CustomerCompactSerializer(source="user")
    products = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    warehouse = WarehouseDetailedSerializer(source="source_warehouse")
    volume_weight = serializers.SerializerMethodField()
    shipping_price = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    declared_price = serializers.SerializerMethodField()
    destination_warehouse = WarehouseReadSerializer()
    package_ids = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = [
            "identifier",
            "source_city",
            "dimensions",
            "custom_total_weight",
            "fixed_total_weight",
            "products",
            "recipient",
            "customer",
            "created_at",
            "number",
            "seller",
            "is_paid",
            "warehouse",
            "fixed_total_weight",
            "volume_weight",
            "shipping_price",
            "declared_price",
            "total_price",
            "destination_warehouse",
            "reg_number",
            "package_ids",
        ]

    def get_package_ids(self, shipment: Shipment):
        return list(shipment.packages.values_list("id", flat=True))

    def get_volume_weight(self, shipment: Shipment):
        return str(round(shipment.chargable_volume_weight, 3))

    def get_seller(self, shipment: Shipment):
        return ", ".join(shipment.packages.values_list("seller", flat=True))

    def get_source_city(self, shipment):
        city = shipment.source_warehouse.airport_city or shipment.source_warehouse.city
        return CityCompactSerializer(city).data

    def get_dimensions(self, shipment: Shipment):
        return {
            "height": shipment.fixed_height,
            "width": shipment.fixed_width,
            "length": shipment.fixed_length,
        }

    def get_products(self, shipment: Shipment):
        titles = []

        for package in shipment.packages.all():
            for product in package.products.all():
                if product.category.needs_description:
                    titles.append(product.description)
                else:
                    titles.append(product.category.name)

        return titles

    def get_shipping_price(self, shipment: Shipment):
        return {
            "amount": str(shipment.total_price),
            "currency": CurrencyCompactSerializer(shipment.total_price_currency).data,
        }

    def get_declared_price(self, shipment: Shipment):
        return {
            "amount": str(
                shipment.declared_price
                - Converter.convert(
                    shipment.total_price,
                    shipment.total_price_currency.code,
                    shipment.declared_price_currency.code,
                )
            ),
            "currency": CurrencyCompactSerializer(
                shipment.declared_price_currency
            ).data,
        }

    def get_total_price(self, shipment: Shipment):
        return {
            "amount": str(shipment.declared_price),
            "currency": CurrencyCompactSerializer(
                shipment.declared_price_currency
            ).data,
        }


class PackageInvoiceSerializer(serializers.ModelSerializer):
    """Invoice serializer used for those packages who has order -> are ordered by assistant"""

    order_number = serializers.CharField(source="order.order_code", required=False)
    warehouse = WarehouseDetailedSerializer(source="current_warehouse")
    customer = CustomerCompactSerializer(source="user")
    recipient = RecipientReadSerializer(source="order.recipient", required=False)
    date = serializers.SerializerMethodField()
    due_date = serializers.SerializerMethodField()
    payment_terms = serializers.SerializerMethodField()
    item = serializers.SerializerMethodField()
    company_info = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            "seller",
            "order_number",
            "warehouse",
            "customer",
            "recipient",
            "date",
            "due_date",
            "payment_terms",
            "item",
            "company_info",
        ]

    def get_payment_terms(self, package):
        return "100% PIA"

    def get_date(self, package: Package):
        order = self.context["earliest_order"]
        if order:
            return timezone.localdate(order.created_at)
        return None

    def get_due_date(self, package: Package):
        # Find related order transaction
        order = self.context["earliest_order"]
        payment = None
        if order:
            payment = Transaction.objects.filter(
                purpose=Transaction.ORDER_PAYMENT,
                completed=True,
                related_object_identifier=order.order_code,
            ).first()
        if payment:
            return timezone.localdate(payment.completed_at)

        return None

    def get_item(self, package: Package):
        order = self.context["earliest_order"]
        package.order = order
        if package.order:
            return {
                "title": package.order.product_description,
                "quantity": package.order.product_quantity,
                "price": {
                    "amount": str(
                        Converter.convert(
                            package.order.real_product_price,
                            package.order.real_product_price_currency.code,
                            package.user.as_customer.active_balance.currency.code,
                        )
                    ),
                    "currency": CurrencyCompactSerializer(
                        package.user.as_customer.active_balance.currency
                    ).data,
                },
                "cargo": {
                    "amount": str(
                        Converter.convert(
                            package.order.real_cargo_price,
                            package.order.real_cargo_price_currency.code,
                            package.user.as_customer.active_balance.currency.code,
                        )
                    ),
                    "currency": CurrencyCompactSerializer(
                        package.user.as_customer.active_balance.currency
                    ).data,
                },
                "commission": {
                    "amount": str(
                        Converter.convert(
                            package.order.real_commission_price,
                            package.order.real_commission_price_currency.code,
                            package.user.as_customer.active_balance.currency.code,
                        )
                    ),
                    "currency": CurrencyCompactSerializer(
                        package.user.as_customer.active_balance.currency
                    ).data,
                },
                "total": {
                    "amount": str(
                        Converter.convert(
                            package.order.real_total_price,
                            package.order.real_total_price_currency.code,
                            package.user.as_customer.active_balance.currency.code,
                        )
                    ),
                    "currency": CurrencyCompactSerializer(
                        package.user.as_customer.active_balance.currency
                    ).data,
                },
            }
        return None

    def get_company_info(self, package):
        conf = Configuration()
        return {
            "email_address": conf._conf.email_address_on_invoice,
            "address": conf._conf.address_on_invoice,
        }


class InvoiceProductSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    seller = serializers.CharField(source="package.seller")
    total = serializers.SerializerMethodField()
    cargo = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()
    commission = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "title",
            "seller",
            "quantity",
            "price",
            "cargo",
            "commission",
            "total",
        ]

    def get_title(self, product: Product):
        description = None
        if product.package_id and product.package.order_id:
            description = product.package.order.product_description

        if not description:
            description = product.normalized_description

        return description

    def get_quantity(self, product: Product):
        if product.package_id and product.package.order_id:
            return product.package.order.real_product_quantity
        return product.quantity

    def get_price(self, product: Product):
        amount = product.price
        currency = product.price_currency

        return {
            "amount": str(
                Converter.convert(
                    amount,
                    currency.code,
                    product.package.user.as_customer.active_balance.currency.code,
                )
            ),
            "currency": CurrencyCompactSerializer(
                product.package.user.as_customer.active_balance.currency,
            ).data,
        }

    def get_cargo(self, product: Product):
        amount = product.cargo_price
        currency = product.cargo_price_currency_id and product.cargo_price_currency

        if amount and currency:
            return {
                "amount": str(
                    Converter.convert(
                        amount,
                        currency.code,
                        product.package.user.as_customer.active_balance.currency.code,
                    )
                ),
                "currency": CurrencyCompactSerializer(
                    product.package.user.as_customer.active_balance.currency,
                ).data,
            }

        return {
            "amount": "0.00",
            "currency": CurrencyCompactSerializer(
                product.package.user.as_customer.active_balance.currency,
            ).data,
        }

    def get_commission(self, product: Product):
        if product.commission_price_currency_id and product.commission_price:
            return {
                "amount": str(
                    Converter.convert(
                        product.commission_price,
                        product.commission_price_currency.code,
                        product.package.user.as_customer.active_balance.currency.code,
                    )
                ),
                "currency": CurrencyCompactSerializer(
                    product.package.user.as_customer.active_balance.currency,
                ).data,
            }

        return {
            "amount": "0.00",
            "currency": CurrencyCompactSerializer(
                product.package.user.as_customer.active_balance.currency,
            ).data,
        }

    def get_total(self, product: Product):
        return {
            "amount": str(
                Converter.convert(
                    product.price * product.quantity,
                    product.price_currency.code,
                    product.package.user.as_customer.active_balance.currency.code,
                )
                + (
                    Converter.convert(
                        product.cargo_price,
                        product.cargo_price_currency.code,
                        product.package.user.as_customer.active_balance.currency.code,
                    )
                    if product.cargo_price_currency_id
                    else 0
                )
                + (
                    Converter.convert(
                        product.commission_price,
                        product.commission_price_currency.code,
                        product.package.user.as_customer.active_balance.currency.code,
                    )
                    if product.commission_price_currency_id
                    else 0
                )
            ),
            "currency": CurrencyCompactSerializer(
                product.package.user.as_customer.active_balance.currency,
            ).data,
        }


class ShipmentInvoiceSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="number")
    warehouse = WarehouseDetailedSerializer(source="current_warehouse")
    customer = CustomerCompactSerializer(source="user")
    recipient = RecipientReadSerializer()
    date = serializers.SerializerMethodField()
    payment_terms = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()
    company_info = serializers.SerializerMethodField()

    class Meta:
        model = Shipment
        fields = [
            "order_number",
            "warehouse",
            "customer",
            "recipient",
            "date",
            "payment_terms",
            "items",
            "company_info",
        ]

    def get_payment_terms(self, shipment):
        return "100% PIA"

    def get_date(self, shipment):
        return timezone.localdate(shipment.created_at)

    def get_items(self, shipment: Shipment):
        items = [
            product
            for package in shipment.packages.all()
            for product in package.products.all()
        ]
        return InvoiceProductSerializer(items, many=True, context=self.context).data

    def get_company_info(self, package):
        conf = Configuration()
        return {
            "email_address": conf._conf.email_address_on_invoice,
            "address": conf._conf.address_on_invoice,
        }


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "first_name", "last_name", "client_code"]


class AcceptedShipmentDetailedReadSerializer(AcceptedShipmentReadSerializer):
    user = UserSerializer(read_only=True)

    class Meta(AcceptedShipmentReadSerializer.Meta):
        fields = AcceptedShipmentReadSerializer.Meta.fields[:]
        fields.append("user")
