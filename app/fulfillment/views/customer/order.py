from datetime import datetime

from django.http import Http404
from django.db import transaction
from django.shortcuts import get_list_or_404, get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from domain.conf import Configuration
from domain.services import (
    create_uncomplete_transactions_for_orders,
    promote_status,
    get_invoice,
    complete_payments,
    create_virtual_invoice,
    save_user_country_log,
)
from domain.exceptions.customer import UncompleteProfileError
from domain.exceptions.logic import InvalidActionError
from fulfillment.filters import OrderFilter
from fulfillment.models import StatusEvent, Status, Order
from fulfillment.serializers.common import StatusEventSerializer
from fulfillment.pagination import DynamicPagination
from fulfillment.serializers.customer import (
    ArchiveSerializer,
    BulkArchiveSerializer,
    OrderReadSerializer,
    OrderWriteSerializer,
    OrderDetailedSerializer,
    CommentReadSerializer,
    CommentWriteSerializer,
    CommissionPriceCalculatorSerializer,
)
from fulfillment.views.utils import filter_by_archive_status


class OrderListCreateApiView(generics.ListCreateAPIView):
    throttle_scope = "light"

    def post(self, request, *args, **kwargs):
        # if not request.user.has_complete_profile:
        #     raise UncompleteProfileError

        return super().post(request, *args, **kwargs)

    def get_queryset(self):
        statuses = self.request.query_params.getlist("status")
        orders = self.request.user.orders.all()
        orders = filter_by_archive_status(orders, self.request)

        if statuses and all(statuses):
            orders = orders.filter(status__in=statuses)

        from_date = self.request.query_params.get("from")
        if from_date:
            try:
                orders = orders.filter(created_at__gte=from_date)
            except ValidationError:
                pass

        to_date = self.request.query_params.get("to")
        if to_date:
            try:
                orders = orders.filter(created_at__lte=to_date)
            except ValidationError:
                pass

        return orders.order_by("-updated_at").select_related()

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return OrderReadSerializer
        return OrderWriteSerializer

    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        kwargs["context"] = self.get_serializer_context()
        kwargs.pop("many", None)
        return serializer_class(many=True, *args, **kwargs)

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context["user"] = self.request.user
        return context

    @transaction.atomic
    def perform_create(self, serializer):
        orders = serializer.save()
        transactions = create_uncomplete_transactions_for_orders(
            orders, instant_payment=False
        )

        if orders:
            order = orders[0]
            save_user_country_log(order.user_id, order.source_country_id)
        # complete_payments(transactions)


class OrderRetrieveUpdateDestroyApiView(generics.RetrieveUpdateDestroyAPIView):
    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        context["user"] = self.request.user
        return context

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return OrderDetailedSerializer
        return OrderWriteSerializer

    def get_object(self):
        order = get_object_or_404(
            self.request.user.orders, order_code=self.kwargs.get("order_code")
        )

        if not (self.request.method == "GET" or order.can_be_deleted_by_user):
            raise InvalidActionError

        return order

    def perform_update(self, serializer):
        serializer.instance._must_recalculate_total_price = True
        serializer.save()

    def perform_destroy(self, order):
        promote_status(
            order, Status.objects.get(type=Status.ORDER_TYPE, codename="deleted")
        )


@api_view(["POST"])
def order_archive_view(request, order_code):
    order = get_object_or_404(Order, order_code=order_code, user=request.user)

    serializer = ArchiveSerializer(data={"instance": order})
    serializer.is_valid(raise_exception=True)
    serializer.perform_archive()

    return Response(OrderReadSerializer(order).data, status=status.HTTP_200_OK)


@api_view(["POST"])
def order_bulk_archive_view(request):
    serializer = BulkArchiveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    orders = get_list_or_404(
        Order, user=request.user, order_code__in=serializer.validated_data["ids"]
    )
    serializer.perform_archive(orders)

    return Response(status=status.HTTP_204_NO_CONTENT)


class CommentListCreateApiView(generics.ListCreateAPIView):
    pagination_class = None

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return CommentReadSerializer
        return CommentWriteSerializer

    def get_order(self):
        order = get_object_or_404(
            self.request.user.orders, order_code=self.kwargs.get("order_code")
        )

        return order

    def get_queryset(self):
        return self.get_order().comments.order_by("created_at")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, order=self.get_order())


@api_view(["GET"])
def order_timeline_view(request, order_code):
    events = get_list_or_404(StatusEvent, order__order_code=order_code)
    return Response(
        StatusEventSerializer(events, many=True).data, status=status.HTTP_200_OK
    )


@api_view(["GET"])
def order_invoice_view(request, order_code):
    order = get_object_or_404(request.user.orders.all(), order_code=order_code)
    invoice = get_invoice(order).serialize()

    if not invoice:
        raise Http404

    return Response(invoice)


@api_view(["GET"])
def calculate_commission_price_view(request):
    data = {
        "price": request.query_params.get("price"),
        "price_currency": request.query_params.get("price_currency_id"),
    }
    serializer = CommissionPriceCalculatorSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    price = serializer.validated_data.get("price")
    price_currency = serializer.validated_data.get("price_currency")
    conf = Configuration()

    return Response(
        {"commission_price": conf.calculate_commission_for_price(price, price_currency)}
    )


@api_view(["POST"])
def create_virtual_invoice_view(request):
    serializer = OrderWriteSerializer(
        data=request.data, context={"request": request, "user": request.user}, many=True
    )
    serializer.is_valid(raise_exception=True)
    invoices = [
        create_virtual_invoice(order_data) for order_data in serializer.validated_data
    ]
    return Response([invoice.serialize() for invoice in invoices if invoice])
