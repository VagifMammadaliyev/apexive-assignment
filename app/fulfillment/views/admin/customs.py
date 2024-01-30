from django.shortcuts import get_object_or_404
from django.db.models import Sum, Q

from rest_framework import views, generics
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

from domain.services import accept_box_at_customs, accept_shipment_at_customs
from customer.permissions import IsCustomsAgent, IsOntimeAdminUser
from fulfillment.models import Box, TrackingStatus, Shipment
from fulfillment.serializers.admin.warehouseman import (
    BoxDetailedSerializer,
    ShipmentReadSerializer,
)
from fulfillment.serializers.admin.common import (
    TrackingStatusSelectSerializer,
    TrackingStatusSerializer,
)
from fulfillment.serializers.admin.customs import (
    ShipmentWithTrackingStatusSerializer as ShipmentReadSerializer,
)


class BoxRetrieveApiView(generics.RetrieveAPIView):
    lookup_field = "code"
    lookup_url_kwarg = "box_code"
    serializer_class = BoxDetailedSerializer
    queryset = Box.objects.filter(
        transportation__isnull=False, transportation__is_completed=False
    )

    def get_object(self):
        box = super().get_object()
        box.shipments_count = box.shipments.count()
        box.real_total_weight = box.shipments.aggregate(
            weight_sum=Sum("fixed_total_weight")
        )["weight_sum"]
        return box


class ShipmentRetrieveApiView(generics.RetrieveAPIView):
    lookup_field = "number"
    lookup_url_kwarg = "number"
    serializer_class = ShipmentReadSerializer
    queryset = Shipment.objects.filter(
        box__isnull=False, box__transportation__is_completed=False
    )


@api_view(["POST"])
@permission_classes([IsCustomsAgent | IsOntimeAdminUser])
def accept_box_view(request, box_code):
    box = get_object_or_404(
        Box.objects.filter(
            transportation__is_completed=False, transportation__isnull=False
        ),
        code=box_code,
    )
    serializer = TrackingStatusSelectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    tracking_status = serializer.validated_data.get("tracking_status")
    accepted_shipment_count = accept_box_at_customs(box, tracking_status)

    return Response(
        {
            "updated_shipments_count": accepted_shipment_count,
        }
    )


@api_view(["POST"])
@permission_classes([IsCustomsAgent | IsOntimeAdminUser])
def accept_shipment_view(request, number):
    shipment = get_object_or_404(
        Shipment.objects.filter(
            box__isnull=False, box__transportation__is_completed=False
        ),
        number=number,
    )
    serializer = TrackingStatusSelectSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    tracking_status = serializer.validated_data.get("tracking_status")
    accept_shipment_at_customs(shipment, tracking_status)

    return Response(ShipmentReadSerializer(shipment).data)


class TrackingStatusListApiView(generics.ListAPIView):
    serializer_class = TrackingStatusSerializer
    permission_classes = [IsCustomsAgent | IsOntimeAdminUser]
    pagination_class = None

    def get_queryset(self):
        q = self.request.query_params.get("q")

        if q:
            return TrackingStatus.objects.filter(
                Q(tracking_code_description__icontains=q)
                | Q(tracking_code_explanation__icontains=q)
                | Q(tracking_condition_code_description__icontains=q)
                | Q(mandatory_comment__icontains=q)
            ).order_by("pl_number")

        return TrackingStatus.objects.order_by("pl_number")
