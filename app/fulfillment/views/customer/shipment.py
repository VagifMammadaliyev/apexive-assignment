from django.shortcuts import get_object_or_404, get_list_or_404
from django.http import Http404
from django.db.models import Q
from django.db import transaction as db_transaction
from django.utils import timezone
from rest_framework import generics
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from domain.conf import Configuration
from domain.services import get_invoice, save_user_country_log
from domain.utils.smart_customs import CustomsClient
from fulfillment.serializers.common import StatusEventSerializer
from fulfillment.serializers.customer import (
    ArchiveSerializer,
    BulkArchiveSerializer,
    ShipmentReadSerializer,
    ShipmentWriteSerializer,
    ShipmentDetailedSerializer,
    ShipmentCompactSerializer,
)
from fulfillment.models import Shipment, StatusEvent
from fulfillment.views.utils import filter_by_archive_status, UserDeclaredFilterMixin


class ShipmentListCreateApiView(generics.ListCreateAPIView, UserDeclaredFilterMixin):
    throttle_scope = "light"

    def get_queryset(self):
        conf = Configuration()
        statuses = self.request.query_params.getlist("status")
        shipments = self.request.user.shipments.all()
        shipments = filter_by_archive_status(shipments, self.request)
        shipments = conf.annotate_by_exlcude_from_smart_customs(shipments)
        shipments = self.filter_by_user_declared(shipments)

        if statuses and all(statuses):
            shipments = shipments.filter(status__in=statuses)

        from_date = self.request.query_params.get("from")
        if from_date:
            try:
                shipments = shipments.filter(created_at__gte=from_date)
            except ValidationError:
                pass

        to_date = self.request.query_params.get("to")
        if to_date:
            try:
                shipments = shipments.filter(created_at__lte=to_date)
            except ValidationError:
                pass

        if "for_courier" in self.request.query_params:
            shipments = shipments.filter(
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
            )
        return (
            shipments.order_by("-updated_at")
            .select_related(
                "recipient",
                "source_country",
                "destination_warehouse",
                "declared_price_currency",
                "total_price_currency",
                "status",
            )
            .prefetch_related("packages__products")
        )

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return ShipmentCompactSerializer
        if self.request.method == "GET":
            return ShipmentReadSerializer
        return ShipmentWriteSerializer

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context["customer"] = self.request.user.as_customer
        return context

    def perform_create(self, serializer):
        shipment = serializer.save()
        save_user_country_log(shipment.user_id, shipment.source_country_id)


class ShipmentRetrieveApiView(generics.RetrieveUpdateAPIView):
    def get_queryset(self, *args, **kwargs):
        conf = Configuration()
        shipments = self.request.user.shipments.all()
        shipments = conf.annotate_by_exlcude_from_smart_customs(shipments)
        return shipments

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return ShipmentDetailedSerializer
        return ShipmentWriteSerializer

    def get_object(self):
        shipment = get_object_or_404(
            self.get_queryset(), number=self.kwargs.get("number")
        )

        if not (self.request.method == "GET" or shipment.can_be_deleted_by_user):
            raise InvalidStatusError

        return shipment

    # def perform_update(self, serializer):
    #     serializer.instance._must_recalculate = True
    #     serializer.save()

    def perform_destroy(self, shipment):
        shipment.delete(soft=True)

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context["customer"] = self.request.user.as_customer
        return context


@api_view(["GET"])
def shipment_timeline_view(request, number):
    events = get_list_or_404(StatusEvent, shipment__number=number)
    return Response(
        StatusEventSerializer(events, many=True).data, status=status.HTTP_200_OK
    )


class ShipmentDeleteView(generics.DestroyAPIView):
    lookup_field = "number"
    lookup_url_kwarg = "number"

    def get_queryset(self):
        shipments = self.request.user.shipments.all()

        return shipments

    def check_object_permissions(self, request, obj):
        super().check_object_permissions(request, obj)
        if not obj.can_be_deleted_by_user:
            raise PermissionDenied()

    @db_transaction.atomic
    def perform_destroy(self, instance: Shipment):
        instance.post_user_delete()
        super().perform_destroy(instance)


@api_view(["GET"])
def shipment_invoice_view(request, number):
    shipment = get_object_or_404(request.user.shipments.all(), number=number)
    invoice = get_invoice(shipment).serialize()

    if not invoice:
        raise Http404

    return Response(invoice)


@api_view(["POST"])
def shipment_archive_view(request, number):
    shipment = get_object_or_404(
        Shipment,
        number=number,
        user=request.user,
    )

    serializer = ArchiveSerializer(data={"instance": shipment})
    serializer.is_valid(raise_exception=True)
    serializer.perform_archive()

    return Response(ShipmentReadSerializer(shipment).data, status=status.HTTP_200_OK)


@api_view(["POST"])
def shipment_bulk_archive_view(request):
    serializer = BulkArchiveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    shipments = get_list_or_404(
        Shipment, user=request.user, number__in=serializer.validated_data["ids"]
    )
    serializer.perform_archive(shipments)

    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def check_smart_customs_declaration(request, number):
    shipment: Shipment = get_object_or_404(
        Shipment.objects.filter(
            is_declared_to_customs=True,
            is_declared_by_user=False,
            declared_to_customs_at__isnull=False,
            is_added_to_box=False,
        ),
        number=number,
    )
    date_from = shipment.declared_to_customs_at
    date_to = timezone.localtime(timezone.now())
    client = CustomsClient()
    # check if declared
    response_declared = client.get_declared_packages(
        date_from, date_to, tracking_code=shipment.number
    )
    client._update_user_declared_packages(response_declared)
    # check if deleted
    response_deleted = client.get_deleted_packages_reg_numbers(
        date_from, date_to, tracking_code=shipment.number
    )
    client._update_user_deleted_packages(response_deleted)
    shipment.refresh_from_db()
    data = ShipmentReadSerializer(shipment).data
    return Response(data)
