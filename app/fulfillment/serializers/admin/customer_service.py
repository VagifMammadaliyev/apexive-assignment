from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.files import File
from rest_framework import serializers

from ontime import messages as msg
from domain.services import promote_status
from fulfillment.models import (
    CustomerServiceProfile,
    Ticket,
    TicketCategory,
    TicketComment,
    TicketAttachment,
    Status,
)
from fulfillment.serializers.common import StatusSerializer
from fulfillment.serializers.customer import (
    TicketRelatedObjectField,
    TicketCategorySerializer,
    AuthorSerializer,
)
from fulfillment.serializers.admin.common import WarehouseDetailedSerializer

User = get_user_model()


class CustomerServiceProfileSerializer(serializers.ModelSerializer):
    warehouse = WarehouseDetailedSerializer(read_only=True)

    class Meta:
        model = CustomerServiceProfile
        fields = ["warehouse"]


class CustomerSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source="full_phone_number")

    class Meta:
        model = User
        fields = [
            "id",
            "client_code",
            "first_name",
            "last_name",
            "phone_number",
            "email",
        ]


# class TicketCategorySerializer(serializers.ModelSerializer):
#     class Meta:
#         model = TicketCategory
#         fields = ["id", "title"]


class TicketReadSerializer(serializers.ModelSerializer):
    user = CustomerSerializer()
    category = TicketCategorySerializer()
    object = serializers.SerializerMethodField()
    status = StatusSerializer()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "number",
            "category",
            "status",
            "object",
            "user",
            "created_at",
            "updated_at",
            "status_last_update_time",
            "answered_by_admin",
        ]

    def get_object(self, ticket: Ticket):
        if ticket.related_object:
            return ticket.related_object.serialize_for_ticket(for_admin=True)
        return None


class TicketCommentReadSerializer(serializers.ModelSerializer):
    attachments = serializers.SerializerMethodField()
    author = AuthorSerializer()

    class Meta:
        model = TicketComment
        fields = [
            "id",
            "author",
            "body",
            "attachments",
            "is_by_customer_service",
            "created_at",
        ]

    def get_attachments(self, comment: TicketComment):
        request = self.context["request"]
        attachment_links = comment.comment_attachments.values_list("file", flat=True)

        return [request.build_absolute_uri(link) for link in attachment_links]


class TicketDetailedSerializer(TicketReadSerializer):
    attachments = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()

    class Meta(TicketReadSerializer.Meta):
        fields = TicketReadSerializer.Meta.fields + ["attachments", "comments"]

    def get_comments(self, ticket: Ticket):
        return TicketCommentReadSerializer(
            ticket.comments.order_by("-id"), many=True, context=self.context
        ).data

    def get_attachments(self, ticket: Ticket):
        request = self.context["request"]
        attachment_links = ticket.ticket_attachments.values_list("file", flat=True)

        return [request.build_absolute_uri(link) for link in attachment_links]


class TicketWriteSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True)
    )
    related_object = TicketRelatedObjectField(required=False)

    class Meta:
        model = Ticket
        fields = [
            "user",
            "status",
            "category",
            "related_object",
            "problem_description",
        ]

    def validate(self, data):
        user = data.get("user")
        related_object = data.get("related_object")

        if related_object and related_object.user_id != user.id:
            raise serializers.ValidationError(
                {"related_object": msg.ID_INVALID_FOR_PROVIDED_TYPE}
            )

        return data

    @transaction.atomic
    def save(self, *args, **kwargs):
        status = self.validated_data.pop("status", None)
        request = self.context["request"]

        if self.instance and self.instance.id:
            ticket = super().save(*args, **kwargs)
        else:
            # Create ticket with initial status then change it using
            # promote status, that way we will fire an event if exists
            accepted = Status.objects.get(type=Status.TICKET_TYPE, codename="accepted")
            ticket = super().save(status=accepted, *args, **kwargs)

        if status:
            promote_status(ticket, status)

        if request.FILES:
            for attachment in request.data.getlist("attachments"):
                TicketAttachment.objects.create(ticket=ticket, file=File(attachment))

        return ticket

    def to_representation(self, instance):
        return TicketDetailedSerializer(instance, context=self.context).data


class TicketCommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketComment
        fields = [
            "body",
        ]

    @transaction.atomic
    def save(self, *args, **kwargs):
        request = self.context["request"]
        comment = super().save(*args, **kwargs)

        if request.FILES:
            for attachment in request.data.getlist("attachments"):
                TicketAttachment.objects.create(comment=comment, file=File(attachment))

        comment.ticket.answered_by_admin = True
        comment.ticket.save(update_fields=["answered_by_admin"])

        return comment

    def to_representation(self, instance):
        return TicketCommentReadSerializer(instance, context=self.context).data
