from django_filters.rest_framework import FilterSet, OrderingFilter, filters

from customer.filters import CustomerFilter
from fulfillment.models import (
    AdditionalService,
    ProductType,
    Shipment,
    Package,
    Transportation,
    Transaction,
    Notification,
    Warehouse,
    Ticket,
    CourierOrder,
    CourierRegion,
    CustomerServiceLog,
    Order,
    OrderedProduct,
)


class OrderFilter(FilterSet):
    class Meta:
        model = Order
        fields = {"product_category": ["exact"]}


class AdminOrderFilter(FilterSet):
    class Meta:
        model = Order
        fields = {
            "user": ["exact"],
            "external_order_code": ["exact"],
            "order_code": ["exact"],
            "package__admin_tracking_code": ["exact"],
        }


class ProductTypeFilter(FilterSet):
    class Meta:
        model = ProductType
        fields = {"category": ["exact"]}


class ShipmentFilter(FilterSet):
    class Meta:
        model = Shipment
        fields = {
            "user": ["exact"],
            "shelf": ["exact", "istartswith"],
            "box": ["isnull"],
        }


class PackageFilter(FilterSet):
    class Meta:
        model = Package
        fields = {
            "id": ["exact"],
            "user": ["exact"],
            "shelf": ["exact", "icontains", "istartswith"],
            "status": ["exact"],
        }


class ShipmentCashierFilter(FilterSet):
    class Meta:
        model = Shipment
        fields = {"user": ["exact"]}


class TransportationFilter(FilterSet):
    class Meta:
        model = Transportation
        fields = {
            "is_completed": ["exact"],
            "source_city": ["exact"],
            "destination_city": ["exact"],
            "departure_time": [
                "day__exact",
                "day__gte",
                "day__lte",
                "month__exact",
                "month__gte",
                "month__lte",
                "year__exact",
                "year__gte",
                "year__lte",
            ],
            "arrival_time": [
                "day__exact",
                "day__gte",
                "day__lte",
                "month__exact",
                "month__gte",
                "month__lte",
                "year__exact",
                "year__gte",
                "year__lte",
            ],
        }


class PaymentFilter(FilterSet):
    ordering = OrderingFilter(
        fields=[
            ("created_at", "created_at"),
        ]
    )

    class Meta:
        model = Transaction
        fields = {"completed": ["exact"]}


class AdditionalServiceFilter(FilterSet):
    class Meta:
        model = AdditionalService
        fields = {"type": ["exact"]}


class NotificationFilter(FilterSet):
    class Meta:
        model = Notification
        fields = {
            "is_seen": ["exact"],
        }


class WarehouseFilter(FilterSet):
    class Meta:
        model = Warehouse
        fields = {
            "is_universal": ["exact"],
            "country": ["exact"],
            "country__is_base": ["exact"],
        }


class TicketFilter(FilterSet):
    class Meta:
        model = Ticket
        fields = {"status": ["exact"]}


class TicketAdminFilter(FilterSet):
    ordering = OrderingFilter(
        fields=[
            ("created_at", "created_at"),
        ]
    )

    class Meta:
        model = Ticket
        fields = {
            "status": ["exact"],
            "number": ["icontains", "istartswith", "iendswith"],
            "category": ["exact"],
        }


class CourierRegionFilter(FilterSet):
    class Meta:
        model = CourierRegion
        fields = {
            "area__city": ["exact"],
        }


class CustomerServiceLogFilter(FilterSet):
    class Meta:
        model = CustomerServiceLog
        fields = {"user": ["exact"]}


class OrderedProductFilter(FilterSet):
    class Meta:
        model = OrderedProduct
        fields = {"category": ["exact"]}
