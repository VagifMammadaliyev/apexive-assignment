from rest_framework import viewsets, generics, mixins

from domain.logging.utils import generic_logging
from customer.permissions import IsOntimeAdminUser
from fulfillment.models import ShoppingAssistantProfile
from fulfillment.serializers.admin import staff_users as staff_serializers


@generic_logging
class ShoppingAssistantProfileViewSet(
    viewsets.GenericViewSet,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
):
    permission_classes = [IsOntimeAdminUser]
    queryset = ShoppingAssistantProfile.objects.all()

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return staff_serializers.ShoppingAssistantProfileReadSerializer
        return staff_serializers.ShoppingAssistantProfileWriteSerializer
