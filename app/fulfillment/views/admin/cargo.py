from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from domain.logging.utils import generic_logging
from customer.permissions import IsOntimeAdminUser, IsOntimeStaffUser
from fulfillment.filters import ProductTypeFilter
from fulfillment.models import (
    Tariff,
    Warehouse,
    Address,
    AddressField,
    ProductCategory,
    ProductType,
)
from fulfillment.serializers.admin import cargo as cargo_serializers


@generic_logging
class TariffViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeAdminUser]
    queryset = Tariff.objects.order_by(
        "source_city", "is_dangerous", "min_weight"
    ).select_related()

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if self.action == "list":
                return cargo_serializers.TariffReadSerializer
            return cargo_serializers.TariffTranslatedReadSerializer
        return cargo_serializers.TariffWriteSerializer


@generic_logging
class WarehouseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeAdminUser]
    queryset = Warehouse.objects.all()

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if "compact" in self.request.query_params:
                return cargo_serializers.WarehouseCompactSerializer
            return cargo_serializers.WarehouseReadSerializer
        return cargo_serializers.WarehouseWriteSerializer


@generic_logging
class AddressViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeAdminUser]
    queryset = Address.objects.order_by("country")

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return cargo_serializers.AddressReadSerializer
        return cargo_serializers.AddressWriteSerializer


@generic_logging
class AddressFieldViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeAdminUser]
    serializer_class = cargo_serializers.AddressFielSerializer
    pagination_class = None

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def get_queryset(self):
        address_pk = self.kwargs.get("address_pk")
        address = get_object_or_404(Address, pk=address_pk)
        return address.fields.all()

    def perform_create(self, serializer):
        serializer.save(address_id=self.kwargs.get("address_pk"))


@generic_logging
class ProductTypeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeStaffUser]
    queryset = ProductType.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_class = ProductTypeFilter

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if "compact" in self.request.query_params:
                return cargo_serializers.ProductTypeCompactSerializer
            if self.action == "retrieve":
                return cargo_serializers.ProductTypeTranslatedReadSerializer
            return cargo_serializers.ProductTypeReadSerializer
        return cargo_serializers.ProductTypeWriteSerializer


@generic_logging
class ProductCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOntimeStaffUser]
    queryset = ProductCategory.objects.all()

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsOntimeStaffUser()]

        return super().get_permissions()

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET" and self.action == "list":
            return cargo_serializers.ProductCategoryCompactSerializer
        return cargo_serializers.ProductCategorySerializer
