from django.shortcuts import get_list_or_404, get_object_or_404
from django.db import transaction as db_transaction
from django.http import Http404
from rest_framework import views, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from domain.services import (
    get_invoice,
    create_courier_order,
    create_uncomplete_transaction_for_courier_order,
)
from fulfillment.models import CourierOrder
from fulfillment.serializers.customer import (
    ArchiveSerializer,
    BulkArchiveSerializer,
    CourierOrderReadSerializer,
    CourierOrderWriteSerializer,
)
from fulfillment.views.utils import filter_by_archive_status


# FIXME: Duplicate get_queryset method, the same used in orders, and in shipments i think
class CourierOrderListApiView(generics.ListAPIView):
    serializer_class = CourierOrderReadSerializer

    def get_queryset(self):
        statuses = self.request.query_params.getlist("status")
        courier_orders = self.request.user.courier_orders.all()
        courier_orders = filter_by_archive_status(courier_orders, self.request)

        if statuses and all(statuses):
            courier_orders = courier_orders.filter(status__in=statuses)

        from_date = self.request.query_params.get("from")
        if from_date:
            try:
                courier_orders = courier_orders.filter(created_at__gte=from_date)
            except ValidationError:
                pass

        to_date = self.request.query_params.get("to")
        if to_date:
            try:
                courier_orders = courier_orders.filter(created_at__lte=to_date)
            except ValidationError:
                pass

        return courier_orders.order_by("-updated_at").select_related()

    def post(self, request, *args, **kwargs):
        serializer = CourierOrderWriteSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        shipments = serializer.validated_data["shipments"]
        recipient = serializer.validated_data["recipient"]
        tariff = serializer.validated_data["tariff"]
        region = serializer.validated_data["region"]
        additional_note = serializer.validated_data.get("additional_note")

        with db_transaction.atomic():
            courier_order = create_courier_order(
                request.user, shipments, recipient, tariff, additional_note, region
            )
            create_uncomplete_transaction_for_courier_order(courier_order)

        return Response(
            CourierOrderReadSerializer(courier_order).data,
            status=status.HTTP_201_CREATED,
        )


class CourierOrderDetailApiView(generics.RetrieveAPIView):
    serializer_class = CourierOrderReadSerializer
    lookup_field = "number"
    lookup_url_kwarg = "number"

    def get_queryset(self):
        return self.request.user.courier_orders.order_by("-updated_at")


@api_view(["GET"])
def courier_order_invoice_view(request, number):
    courier_order = get_object_or_404(request.user.courier_orders.all(), number=number)
    invoice = get_invoice(courier_order).serialize()

    if not invoice:
        raise Http404

    return Response(invoice)


@api_view(["POST"])
def courier_order_archive_view(request, number):
    courier = get_object_or_404(
        CourierOrder,
        number=number,
        user=request.user,
    )

    serializer = ArchiveSerializer(data={"instance": courier})
    serializer.is_valid(raise_exception=True)
    serializer.perform_archive()

    return Response(CourierOrderReadSerializer(courier).data, status=status.HTTP_200_OK)


@api_view(["POST"])
def courier_order_bulk_archive_view(request):
    serializer = BulkArchiveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    courier_orders = get_list_or_404(
        CourierOrder, number__in=serializer.validated_data["ids"], user=request.user
    )
    serializer.perform_archive(courier_orders)

    return Response(status=status.HTTP_204_NO_CONTENT)
