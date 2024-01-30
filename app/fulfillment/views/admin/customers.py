from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend

from domain.logging.utils import generic_logging
from customer.models import Customer
from customer.filters import CustomerFilter
from customer.permissions import IsOntimeAdminUser
from fulfillment.serializers.admin import customers as customer_serializer


@generic_logging
class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_class = CustomerFilter
    permission_classes = [IsOntimeAdminUser]

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if self.action == "retrieve":
                return customer_serializer.CustomerDetailedSerializer
            return customer_serializer.CustomerReadSerializer
        return customer_serializer.CustomerWriteSerializer

    def perform_destroy(self, customer):
        customer.is_active = False
        customer.save(update_fields=["is_active"])

    def perform_create(self, serializer):
        serializer.save(is_created_by_admin=True)
