from rest_framework import serializers

from django.contrib.auth import get_user_model

from customer.models import Recipient
from fulfillment.serializers.common import WarehouseReadSerializer
from fulfillment.models import TrackingStatus
from core.serializers.admin import CityCompactSerializer

User = get_user_model()


class UserAutocompleteSerializer(serializers.ModelSerializer):
    display = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "display"]

    def get_display(self, user):
        return "%s [%s]" % (user.full_name, user.full_phone_number)


class WarehouseDetailedSerializer(WarehouseReadSerializer):
    city = CityCompactSerializer(read_only=True)
    airport_city = serializers.SerializerMethodField()

    class Meta(WarehouseReadSerializer.Meta):
        fields = WarehouseReadSerializer.Meta.fields + [
            "city",
            "airport_city",
            "does_serve_dangerous_packages",
            "does_consider_volume",
        ]

    def get_airport_city(self, warehouse):
        city = warehouse.airport_city or warehouse.city
        return CityCompactSerializer(city).data


class TrackingStatusSelectSerializer(serializers.Serializer):
    tracking_status = serializers.PrimaryKeyRelatedField(
        queryset=TrackingStatus.objects.all(), required=False
    )


class TrackingStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingStatus
        fields = [
            "id",
            "tracking_code_description",
            "tracking_code_explanation",
            "tracking_condition_code_description",
            "mandatory_comment",
            "customs_default",
        ]


class RecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipient
        fields = ["id", "full_name", "id_pin", "phone_number"]
