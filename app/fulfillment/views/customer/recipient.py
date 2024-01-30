from django.shortcuts import get_object_or_404
from django.db import transaction as db_transaction
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import api_view

from customer.models import Recipient
from customer.tasks import fetch_user_data_from_government_resource
from fulfillment.serializers.customer import (
    RecipientReadSerializer,
    RecipientWriteSerializer,
    RecipientCompactSerializer,
)


# TODO: Delete this view
@api_view(["POST"])
def set_billed_recipient_view(request, pk):
    recipient = get_object_or_404(
        Recipient.objects.filter(is_deleted=False, user_id=request.user.id).only("id"),
        pk=pk,
    )
    request.user.billed_recipient_id = recipient.id
    request.user.save(update_fields=["billed_recipient_id"])
    fetch_user_data_from_government_resource.delay(recipient.id)
    return Response({"status": "OK"})


class RecipientViewSet(viewsets.ModelViewSet):
    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_queryset(self):
        return self.request.user.recipients.filter(is_deleted=False)

    @db_transaction.atomic
    def perform_destroy(self, instance):
        instance.is_deleted = True

        # Check if it was user's billing recipient
        if self.request.user.billed_recipient_id == instance.id:
            self.request.user.billed_recipient_id = None
            # Remove that billed recipient
            # Try to select another billed recipient
            self.request.user.billed_recipient_id = self.request.user.recipients.filter(
                is_deleted=False
            ).first()
            self.request.user.save(update_fields=["billed_recipient_id"])

        instance.save(update_fields=["is_deleted"])

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)

        if self.action == "partial_update":
            context["current_recipient"] = self.get_object()

        context["billed_recipient_id"] = self.request.user.billed_recipient_id

        return context

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if "compact" in self.request.query_params:
                return RecipientCompactSerializer
            return RecipientReadSerializer
        return RecipientWriteSerializer


@api_view(["POST"])
@db_transaction.atomic
def bulk_delete_recipients_view(request):
    # Check if user's billing address was in requested id's
    if str(request.user.billed_recipient_id) in map(
        lambda pk: str(pk), request.data.get("recipients", [])
    ):
        # Then remove that billing address
        request.user.billed_recipient = None
        request.user.save(update_fields=["billed_recipient"])

    request.user.recipients.filter(pk__in=request.data.get("recipients", [])).update(
        is_deleted=True
    )
    return Response(status=status.HTTP_204_NO_CONTENT)
