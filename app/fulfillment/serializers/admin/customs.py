from rest_framework import serializers

from fulfillment.serializers.admin.common import TrackingStatusSerializer
from fulfillment.serializers.admin.warehouseman import ShipmentReadSerializer


class ShipmentWithTrackingStatusSerializer(ShipmentReadSerializer):
    tracking_status = TrackingStatusSerializer(read_only=True)

    class Meta(ShipmentReadSerializer.Meta):
        fields = ShipmentReadSerializer.Meta.fields + ["tracking_status"]
