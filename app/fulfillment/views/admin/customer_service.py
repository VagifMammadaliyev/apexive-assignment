from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, views, status, viewsets, parsers
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from domain.logging.utils import generic_logging, log_generic_method
from customer.permissions import IsCustomerService, IsOntimeAdminUser, IsCashier
from fulfillment.models import Ticket, TicketCategory, Status
from fulfillment.filters import TicketAdminFilter
from fulfillment.serializers.common import StatusSerializer
from fulfillment.serializers.admin import customer_service as cs_serializers
from fulfillment.views.customer.ticket import TicketRelatedObjectListApiView

User = get_user_model()
customer_service_permission = [IsCustomerService | IsOntimeAdminUser | IsCashier]


class TicketCategoryListApiView(generics.ListAPIView):
    permission_classes = customer_service_permission
    serializer_class = cs_serializers.TicketCategorySerializer
    pagination_class = None

    def get_queryset(self):
        return TicketCategory.objects.order_by("id")


@generic_logging
class TicketViewSet(viewsets.ModelViewSet):
    permission_classes = customer_service_permission
    filter_backends = [DjangoFilterBackend]
    filterset_class = TicketAdminFilter
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_serializer_class(self, *args, **kwargs):
        if self.action == "retrieve":
            return cs_serializers.TicketDetailedSerializer
        elif self.action == "list":
            return cs_serializers.TicketReadSerializer
        return cs_serializers.TicketWriteSerializer

    def get_queryset(self):
        queryset = Ticket.objects.all()

        user_id = self.request.query_params.get("user")
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset.select_related("category", "user")


class TicketCommentListCreateApiView(generics.ListCreateAPIView):
    permission_classes = customer_service_permission
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    pagination_class = None

    def get_queryset(self):
        return self.get_ticket().comments.order_by("-id")

    def get_ticket(self):
        return get_object_or_404(Ticket, pk=self.kwargs.get("ticket_pk"))

    @log_generic_method
    def perform_create(self, serializer):
        serializer.save(
            ticket=self.get_ticket(),
            author=self.request.user,
            is_by_customer_service=True,
        )

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "POST":
            return cs_serializers.TicketCommentWriteSerializer
        return cs_serializers.TicketCommentReadSerializer


class TicketStatusListApiView(generics.ListAPIView):
    permission_classes = customer_service_permission
    serializer_class = StatusSerializer
    queryset = Status.objects.filter(type=Status.TICKET_TYPE)
    pagination_class = None


class AdminTicketRelatedObjectListApiView(TicketRelatedObjectListApiView):
    permission_classes = customer_service_permission

    def get_user(self):
        return get_object_or_404(User, pk=self.kwargs.get("user_pk"))
