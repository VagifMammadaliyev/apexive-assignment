from rest_framework import serializers

from domain.services import get_shipment_payment
from core.serializers.admin import CurrencyCompactSerializer
from fulfillment.serializers.admin.common import WarehouseDetailedSerializer
from fulfillment.models import Shipment, Transaction, CashierProfile


class PaymentSerializer(serializers.ModelSerializer):
    purpose = serializers.CharField(source="get_purpose_display")
    type = serializers.CharField(source="get_type_display")
    currency = CurrencyCompactSerializer(read_only=True)

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


class ShipmentSerializer(serializers.ModelSerializer):
    payment = serializers.SerializerMethodField()
    # total_price_currency = CurrencyCompactSerializer(read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "number",
            "shelf",
            # "total_price",
            # "total_price_currency",
            "payment",
        ]

    def get_payment(self, shipment):
        payment = get_shipment_payment(shipment)
        return PaymentSerializer(payment).data if payment else None


class CashierProfileSerializer(serializers.ModelSerializer):
    warehouse = WarehouseDetailedSerializer(read_only=True)

    class Meta:
        model = CashierProfile
        fields = ["warehouse"]
