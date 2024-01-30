import requests
from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from django.db.models import Q
from django.http import Http404
from django.utils import functional
from rest_framework import generics, mixins, views, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from domain.services import (
    complete_payments,
    promote_status,
    handover_queued_item,
    # get_service_queue_item,
    mark_queued_customer_as_serviced,
    create_cashier_payment_log_callback,
    make_completed_callback,
    fetch_citizen_data_raw,
)
from domain.utils import QueueClient, QueueManager
from customer.models import Role
from customer.permissions import (
    IsCustomerMonitor,
    IsQueueMonitor,
    IsOntimeAdminUser,
    IsCashier,
    IsWarehouseman,
    IsCustomerService,
)
from fulfillment.models import (
    Shipment,
    Queue,
    QueuedItem,
    Transaction,
    Status,
    Warehouse,
    CustomerServiceLog,
)
from fulfillment.filters import CustomerServiceLogFilter
from fulfillment.serializers.admin import queue as queue_serializers


def get_profile(staff_user):
    """
    Returns profile for cashier or warehouseman user.

    WARNING: This method may cause ambiguity when request.user has Role.ADMIN and
    if that user's warehouseman profile and cashier profile have different
    warehouse_id then the result will vary depending on which 'if' statement executed first.
    """
    return (
        getattr(staff_user, "warehouseman_profile", None)
        or getattr(staff_user, "cashier_profile", None)
        or getattr(staff_user, "customer_service_profile", None)
        or getattr(staff_user, "as_monitor", None)
    )


def get_warehouse_id(staff_user):
    """
    Returns warehouse for staff user. Both cashier and warehouseman have warehouse field.
    """
    profile = get_profile(staff_user)
    return profile and profile.warehouse_id


def get_monitor(auth_model):
    return getattr(auth_model, "as_monitor")


def get_initial_shipment_queryset(monitor):
    if not monitor:
        return Shipment.objects.none()
    return Shipment.objects.filter(
        status__codename="received", current_warehouse_id=monitor.warehouse_id
    )


def get_queue_type(role_type):
    if role_type == Role.CASHIER:
        return Queue.TO_CASHIER
    elif role_type == Role.WAREHOUSEMAN:
        return Queue.TO_WAREHOUSEMAN
    elif role_type == Role.CUSTOMER_SERVICE:
        return Queue.TO_CUSTOMER_SERVICE
    return None  # we must show all queues for admin


def get_queued_item(staff_user, queue_id, queued_item_id):
    """
    Get queued item taking into account to staff_user's role and his warehouse.
    """
    queue_type = get_queue_type(staff_user.role.type)

    return get_object_or_404(
        QueuedItem.objects.filter(
            Q(queue__type=queue_type) if queue_type else Q(),
            queue=queue_id,
            queue__warehouse=get_warehouse_id(staff_user),
        ),
        pk=queued_item_id,
    )


def get_queues(staff_user):
    warehouse_id = get_warehouse_id(staff_user)

    if warehouse_id:
        queue_type = get_queue_type(staff_user.role.type)
        queues = Queue.objects.filter(
            Q(type=queue_type) if queue_type else Q(), warehouse_id=warehouse_id
        )

        return queues.order_by("code")

    return Queue.objects.none()


class CustomerShipmentListApiView(generics.GenericAPIView, mixins.ListModelMixin):
    permission_classes = [IsCustomerMonitor | IsOntimeAdminUser]
    serializer_class = queue_serializers.CustomerShipmentSerializer
    pagination_class = None

    def post(self, request, *args, **kwargs):
        manager = QueueManager(
            get_object_or_404(Warehouse, id=get_warehouse_id(request.user)),
            request.user,
        )
        queued_item = manager.add_shipments_to_queue(
            get_initial_shipment_queryset(get_monitor(request.user)).filter(
                queued_item__isnull=True, number__in=request.data.get("numbers", [])
            )
        )
        return Response({"queue_number": queued_item.code})

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        shipments = get_initial_shipment_queryset(get_monitor(self.request.user))
        return shipments.filter(
            user__client_code=self.request.query_params.get("client_code", ""),
        )


@api_view(["POST"])
@permission_classes([IsCustomerMonitor | IsOntimeAdminUser])
def add_customer_to_service_queue_view(request):
    manager = QueueManager(
        get_object_or_404(Warehouse, id=get_warehouse_id(request.user)), request.user
    )
    item = manager.add_customer_to_queue()
    return Response({"queue_number": item.code})


class QueueListApiView(generics.ListAPIView):
    permission_classes = [
        IsWarehouseman | IsOntimeAdminUser | IsCustomerService | IsCashier
    ]
    pagination_class = None
    serializer_class = queue_serializers.QueueSerializer

    def get_queryset(self):
        return get_queues(self.request.user)


class QueuedItemListApiView(generics.ListAPIView):
    permission_classes = [
        IsWarehouseman | IsOntimeAdminUser | IsCustomerService | IsCashier
    ]
    pagination_class = None
    serializer_class = queue_serializers.QueuedItemSerializer

    def get_queryset(self):
        queue = get_object_or_404(
            get_queues(self.request.user), pk=self.kwargs.get("pk")
        )
        role = self.request.user.role
        extra_filters = {}
        return queue.queued_items.filter(**extra_filters).order_by("id")


@api_view(["POST"])
@permission_classes(
    [IsWarehouseman | IsCashier | IsCustomerService | IsOntimeAdminUser]
)
def complete_queued_item_view(request, queue_pk, item_pk):
    manager = QueueManager(
        get_object_or_404(Warehouse, id=get_warehouse_id(request.user)), request.user
    )
    manager.make_item_ready(get_queued_item(request.user, queue_pk, item_pk))
    return Response({"status": "OK"})


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
def handover_queued_item_view(request, queue_pk, item_pk):
    handover_queued_item(get_queued_item(request.user, queue_pk, item_pk))
    return Response({"status": "OK"})


@api_view(["POST"])
@permission_classes([IsCustomerService | IsCashier | IsOntimeAdminUser])
def mark_queued_customer_as_serviced_view(request, queue_pk, item_pk):
    mark_queued_customer_as_serviced(get_queued_item(request.user, queue_pk, item_pk))
    return Response({"status": "OK"})


@api_view(["POST"])
@permission_classes([IsCashier | IsOntimeAdminUser])
@db_transaction.atomic
def pay_for_shipment_view(request):
    def payment_callback(*args, **kwargs):
        make_completed_callback(*args, **kwargs)
        create_cashier_payment_log_callback(*args, **kwargs)

    cashier = request.user.cashier_profile

    for payment in request.data.get("payments", []):
        invoice_numbers = payment.get("invoice_numbers", [])
        new_payment_type = payment.get("payment_type")
        transactions = Transaction.objects.filter(
            purpose=Transaction.SHIPMENT_PAYMENT,
            completed=False,
            invoice_number__in=invoice_numbers,
        )

        complete_payments(
            transactions=transactions,
            override_type=new_payment_type,
            callback=payment_callback,
            callback_params={
                "staff_user_id": request.user.id,
            },
        )

    return Response({"status": "OK"})


class MonitorApiView(generics.ListAPIView):
    permission_classes = [IsQueueMonitor | IsOntimeAdminUser]
    pagination_class = None
    serializer_class = queue_serializers.MonitorQueuedItemSerializer

    def get_queryset(self):
        monitor = get_monitor(self.request.user)

        if monitor:
            # Exclude queued items with blank codes, because those items
            # are for cashier (empty codes can appear only for warehouseman queue)
            return (
                QueuedItem.objects.filter()
                .exclude(code__isnull=True, queue__monitor__id=monitor.id)
                .order_by("-id")
            )

        return QueuedItem.objects.none()


@api_view(["POST"])
@permission_classes(
    [IsWarehouseman | IsCashier | IsCustomerService | IsOntimeAdminUser]
)
def accept_next_queued_item_view(request, queue_pk):
    warehouse_id = get_warehouse_id(request.user)
    queue = get_object_or_404(get_queues(request.user), pk=queue_pk)
    manager = QueueManager(get_object_or_404(Warehouse, id=warehouse_id), request.user)
    item = manager.accept_next_item(queue)
    return Response(queue_serializers.QueuedItemSerializer(item).data)


@api_view(["GET"])
@permission_classes(
    [IsWarehouseman | IsCashier | IsCustomerService | IsOntimeAdminUser]
)
def can_get_next_item_view(request, queue_pk):
    warehouse_id = get_warehouse_id(request.user)
    queue = get_object_or_404(get_queues(request.user), pk=queue_pk)
    manager = QueueManager(get_object_or_404(Warehouse, id=warehouse_id), request.user)
    next_item = manager.get_next_queued_item(queue)
    return Response({"can_get": bool(next_item)})


@api_view(["POST"])
@permission_classes([IsWarehouseman | IsOntimeAdminUser])
def check_shipment_as_found_view(request, queue_pk, item_pk, shipment_number):
    serializer = queue_serializers.CheckShipmentAsFoundSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    queued_item: QueuedItem = get_queued_item(request.user, queue_pk, item_pk)
    shipment: Shipment = get_object_or_404(
        queued_item.shipments, number=shipment_number
    )
    shipment.is_checked_by_warehouseman = serializer.validated_data["is_checked"]
    shipment.save(update_fields=["is_checked_by_warehouseman"])
    return Response({"status": "OK"})


class ReceiverInfoApiView(generics.CreateAPIView):
    """
    Gets the signature of receiving person.
    If no other data is passed - save the shipment.user as
    receiver, else if personal data was passed use that data
    and mark shipment's receiver as not the real owner.
    """

    permission_classes = [IsWarehouseman | IsCashier | IsOntimeAdminUser]
    serializer_class = queue_serializers.ReceiverInfoSerializer

    def get_shipments(self, profile, queued_item):
        return get_initial_shipment_queryset(profile).filter(
            receiver__isnull=True, queued_item=queued_item
        )

    def perform_create(self, serializer):
        profile = get_profile(self.request.user)
        queued_item = get_queued_item(
            self.request.user, self.kwargs.get("queue_pk"), self.kwargs.get("item_pk")
        )
        shipments = self.get_shipments(profile, queued_item)
        if not shipments:
            raise Http404

        data = {}
        shipment = shipments[0]
        if serializer.validated_data.get("is_real_owner", True):
            # Copy data from shipment.user
            data = {
                "first_name": shipment.recipient.first_name,
                "last_name": shipment.recipient.last_name,
                "id_pin": shipment.recipient.id_pin,
                "phone_number": shipment.recipient.phone_number,
            }

        for shipment in shipments:
            serializer.save(shipment=shipment, **data)
            serializer.instance = (
                None  # clear instance to save using this serializer object again
            )


@api_view(["GET"])
@permission_classes(
    [
        IsWarehouseman
        | IsCashier
        | IsCustomerService
        | IsOntimeAdminUser
        | IsQueueMonitor
        | IsCustomerMonitor
    ]
)
def fetch_customer_data_using_pin(request):
    response = fetch_citizen_data_raw(request.query_params.get("id_pin"))
    if response.status_code == 200:
        return Response(response.json())
    return Response({}, status=status.HTTP_404_NOT_FOUND)


class CustomerServiceLogListCreateApiView(generics.ListCreateAPIView):
    permission_classes = [IsWarehouseman | IsCashier | IsOntimeAdminUser]
    filter_backends = [DjangoFilterBackend]
    queryset = CustomerServiceLog.objects.all().order_by("-id")
    filterset_class = CustomerServiceLogFilter

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "POST":
            return queue_serializers.CustomerServiceLogWriteSerializer
        return queue_serializers.CustomerServiceLogReadSerializer
