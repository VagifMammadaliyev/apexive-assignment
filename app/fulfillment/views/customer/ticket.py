from django.shortcuts import get_list_or_404, get_object_or_404
from rest_framework import generics, parsers, status, viewsets, views
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from domain.services import promote_status
from fulfillment.models import TicketCategory, Ticket, Status
from fulfillment.serializers.customer import (
    ArchiveSerializer,
    BulkArchiveSerializer,
    TicketCategorySerializer,
    TicketReadSerializer,
    TicketWriteSerializer,
    TicketCommentReadSerializer,
    TicketCommentWriteSerializer,
    TicketDetailedSerializer,
)
from fulfillment.filters import TicketFilter
from fulfillment.views.utils import filter_by_archive_status


class TicketCategoryListApiView(generics.ListAPIView):
    serializer_class = TicketCategorySerializer
    queryset = TicketCategory.objects.all()
    pagination_class = None


class TicketViewSet(viewsets.ModelViewSet):
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TicketFilter
    throttle_scope = "hardcore"

    def get_queryset(self):
        tickets = self.request.user.tickets.exclude(
            status__codename="deleted"
        ).order_by("-id")
        tickets = filter_by_archive_status(tickets, self.request)

        statuses = self.request.query_params.getlist("status")

        if statuses and all(statuses):
            tickets = tickets.filter(status__in=statuses)

        return tickets

    def get_serializer_class(self, *args, **kwargs):
        if self.action == "retrieve":
            return TicketDetailedSerializer

        if self.request.method == "GET":  # not detailed
            return TicketReadSerializer
        return TicketWriteSerializer

    def perform_create(self, serializer):
        accepted = Status.objects.get(type=Status.TICKET_TYPE, codename="accepted")
        serializer.save(status=accepted, user=self.request.user)

    def perform_destroy(self, ticket: Ticket):
        promote_status(
            ticket, Status.objects.get(type=Status.TICKET_TYPE, codename="deleted")
        )


class TicketRelatedObjectListApiView(views.APIView):
    def get_user(self):
        return self.request.user

    def get(self, *args, **kwargs):
        types = self.request.query_params.getlist("types")
        response_data = []
        user = self.get_user()

        if "package" in types:
            for package in user.packages.all():
                response_data.append(package.serialize_for_ticket())
        if "order" in types:
            for package in user.orders.all():
                response_data.append(package.serialize_for_ticket())
        if "shipment" in types:
            for package in user.shipments.all():
                response_data.append(package.serialize_for_ticket())
        if "payment" in types:
            for package in user.transactions.all():
                response_data.append(package.serialize_for_ticket())

        return Response(response_data)


class TicketCommentListCreateApiView(generics.ListCreateAPIView):
    pagination_class = None
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return self.get_ticket().comments.all().order_by("-id")

    def get_ticket(self):
        if self.request.method == "GET":
            tickets = self.request.user.tickets.exclude(status__codename="deleted")
        else:
            tickets = self.request.user.tickets.filter(
                status__codename__in=Ticket.get_can_add_comment_status_codenames(),
            )
        return get_object_or_404(
            tickets,
            pk=self.kwargs.get("ticket_pk"),
        )

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return TicketCommentReadSerializer
        return TicketCommentWriteSerializer

    def perform_create(self, serializer):
        ticket = self.get_ticket()
        serializer.save(ticket=ticket, author=self.request.user)


@api_view(["POST"])
def ticket_archive_view(request, number):
    ticket = get_object_or_404(
        Ticket,
        number=number,
        user=request.user,
    )

    serializer = ArchiveSerializer(data={"instance": ticket})
    serializer.is_valid(raise_exception=True)
    serializer.perform_archive()

    return Response(
        TicketReadSerializer(ticket, context=dict(request=request)).data,
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def ticket_bulk_archive_view(request):
    serializer = BulkArchiveSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    tickets = get_list_or_404(Ticket, number__in=serializer.validated_data["ids"])
    serializer.perform_archive(tickets)

    return Response(status=status.HTTP_204_NO_CONTENT)
