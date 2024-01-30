import base64
from decimal import Decimal

from django.utils.translation import ugettext as _
from django.core.files.base import ContentFile
from django.core.files.images import ImageFile
from rest_framework import serializers

from ontime import messages as msg
from domain.services import get_shipment_payment
from core.serializers.admin import CurrencyCompactSerializer
from core.converter import Converter
from customer.models import Customer
from customer.serializers import BalanceSerializer
from fulfillment.serializers.admin.warehouseman import RecipientReadSerializer
from fulfillment.models import (
    Shipment,
    ShipmentReceiver,
    Package,
    Product,
    Transaction,
    Queue,
    QueuedItem,
    Monitor,
    CustomerServiceLog,
)


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, (str, bytes)) and data.startswith("data:image"):
            fmt, imgstr = data.split(";base64,")  # fmt ~= data:image/X,
            ext = fmt.split("/")[-1]  # guess file extension
            data = ImageFile(ContentFile(base64.b64decode(imgstr)), name="temp." + ext)
            return data
        return super().to_internal_value(data)


class ReceiverInfoSerializer(serializers.ModelSerializer):
    signature = Base64ImageField(required=True)

    class Meta:
        model = ShipmentReceiver
        fields = [
            "first_name",
            "last_name",
            "id_pin",
            "phone_number",
            "signature",
            "is_real_owner",
        ]
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": False},
            "last_name": {"required": False, "allow_blank": False},
            "id_pin": {"required": False, "allow_blank": False},
            "phone_number": {"required": False, "allow_blank": False},
        }

    def validate(self, data):
        is_real_owner = data.get("is_real_owner", True)

        bad_fields = []
        if not is_real_owner:
            for field in ["first_name", "last_name", "id_pin", "phone_number"]:
                if not data.get(field):
                    bad_fields += [field]

        if bad_fields:
            raise serializers.ValidationError(
                {field: msg.REAL_CUSTOMER_WARNING for field in bad_fields}
            )

        return data


class PaymentSerializer(serializers.ModelSerializer):
    purpose = serializers.CharField(source="get_purpose_display")
    type = serializers.CharField(source="get_type_display")
    currency = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "invoice_number",
            "purpose",
            "type",
            "created_at",
            "amount",
            "currency",
            "completed",
        ]

    def get_amount(self, transaction):
        return str(
            Converter.convert(
                transaction.amount,
                transaction.currency.code,
                transaction.related_object.current_warehouse.city.country.currency.code,
            )
        )

    def get_currency(self, transaction):
        return CurrencyCompactSerializer(
            transaction.related_object.current_warehouse.city.country.currency
        ).data


class CustomerSerializer(serializers.ModelSerializer):
    # identifier = serializers.CharField(source="profile.identifier")
    # id_pin = serializers.CharField(source="profile.id_pin")
    active_balance = BalanceSerializer(
        read_only=True, source="as_customer.active_balance"  # WTF
    )
    first_name = serializers.CharField(source="real_name")
    last_name = serializers.CharField(source="real_surname")

    class Meta:
        model = Customer
        fields = [
            "id",
            "first_name",
            "last_name",
            "client_code",
            "id_pin",
            "first_name",
            "last_name",
            # "identifier",
            "active_balance",
        ]


class CustomerProductSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source="normalized_description", read_only=True)

    class Meta:
        model = Product
        fields = [
            "description",
            "quantity",
        ]


class CustomerPackageSerializer(serializers.ModelSerializer):
    products = CustomerProductSerializer(many=True, read_only=True)

    class Meta:
        model = Package
        fields = ["tracking_code", "weight", "products"]


class CustomerShipmentSerializer(serializers.ModelSerializer):
    packages = CustomerPackageSerializer(read_only=True, many=True)
    payment = serializers.SerializerMethodField()
    recipient = RecipientReadSerializer(read_only=True)
    receiver = ReceiverInfoSerializer(read_only=True)
    in_queue = serializers.SerializerMethodField()
    is_checked = serializers.BooleanField(source="is_checked_by_warehouseman")

    class Meta:
        model = Shipment
        fields = [
            "number",
            "is_paid",
            "is_checked",
            "total_weight",
            "in_queue",
            "shelf",
            "status_last_update_time",
            "user_note",
            "payment",
            "recipient",
            "receiver",
            "packages",
        ]

    def get_in_queue(self, shipment):
        return bool(shipment.queued_item_id)

    def get_payment(self, shipment):
        payment = get_shipment_payment(shipment)
        return PaymentSerializer(payment).data if payment else None


class QueueSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source="get_type_display")

    class Meta:
        model = Queue
        fields = [
            "id",
            "code",
            "type",
        ]


class QueuedItemSerializer(serializers.ModelSerializer):
    shipments = CustomerShipmentSerializer(many=True, read_only=True)
    for_cashier = serializers.BooleanField(default=False)
    for_cashier_queue_code = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    customer = CustomerSerializer(read_only=True, source="user")
    total = serializers.SerializerMethodField()
    for_customer_service = serializers.SerializerMethodField()

    class Meta:
        model = QueuedItem
        fields = [
            "id",
            "code",
            "customer",
            "ready",
            "for_cashier",
            "for_cashier_queue_code",
            "for_customer_service",
            "actions",
            "total",
            "shipments",
        ]

    def get_for_cashier_queue_code(self, queued_item):
        if queued_item.dest_queue_id:
            return queued_item.dest_queue.code
        return None

    def get_for_customer_service(self, queued_item):
        return queued_item.user_id is None

    def get_total(self, queued_item):
        """
        Returns dict for total price that customer must pay for his shipment.
        Will return None if queued item is for customer service queue.
        """
        if not queued_item.queue.type == Queue.TO_CUSTOMER_SERVICE:
            total_price_currency = queued_item.queue.warehouse.city.country.currency
            total_price = Decimal("0.00")

            shipments = queued_item.shipments.filter(is_paid=False)

            for shipment in shipments:
                total_price += Converter.convert(
                    shipment.total_price,
                    shipment.total_price_currency.code,
                    total_price_currency.code,
                )

            return {
                "price": total_price,
                "currency": CurrencyCompactSerializer(total_price_currency).data,
            }

        return None

    def get_actions(self, queued_item):
        if (
            queued_item.for_cashier
            and queued_item.queue_id
            and queued_item.queue.type == Queue.TO_WAREHOUSEMAN
        ):
            can_complete = bool(queued_item.dest_queue_id)
        else:
            can_complete = queued_item.ready

        return {"can_make_ready": not queued_item.ready, "can_complete": can_complete}


class MonitorQueuedItemSerializer(serializers.ModelSerializer):
    queue_code = serializers.SerializerMethodField()
    customer_id_pin = serializers.SerializerMethodField()
    customer_first_name = serializers.SerializerMethodField()
    customer_last_name = serializers.SerializerMethodField()

    class Meta:
        model = QueuedItem
        fields = [
            "id",
            "code",
            "ready",
            "queue_code",
            "customer_id_pin",
            "customer_first_name",
            "customer_last_name",
        ]

    def get_customer_last_name(self, item):
        if item.user_id:
            return item.user.real_surname

        return None

    def get_customer_first_name(self, item):
        if item.user_id:
            return item.user.real_name

        return None

    def get_queue_code(self, item):
        if item.queue_id:
            return item.queue.code
        return None

    def get_customer_id_pin(self, item):
        if item.user_id:
            return item.user.id_pin

        return None


class MonitorSerializer(serializers.ModelSerializer):
    warehouse = serializers.SerializerMethodField()

    class Meta:
        model = Monitor
        fields = ["id", "type", "code", "warehouse"]

    def get_warehouse(self, monitor):
        queue = monitor.queues.first()
        return monitor.warehouse_id or (queue and queue.warehouse_id)


class CheckShipmentAsFoundSerializer(serializers.Serializer):
    is_checked = serializers.BooleanField(default=True)


class CustomerServiceLogWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerServiceLog
        fields = [
            "id",
            "created_at",
            "user",
            "person_description",
            "problem_description",
        ]

    def validate(self, data):
        user = data.get("user")
        person = data.get("person_description")

        err_msg = "One of these field is required"
        if not (person or user):
            raise serializers.ValidationError(
                {"user_id": err_msg, "person_description": err_msg}
            )

        return data

    def to_representation(self, instance):
        return CustomerServiceLogReadSerializer(instance, context=self.context).data


class CustomerServiceLogReadSerializer(serializers.ModelSerializer):
    user = CustomerSerializer(read_only=True)

    class Meta:
        model = CustomerServiceLog
        fields = [
            "id",
            "created_at",
            "user",
            "person_description",
            "problem_description",
        ]
