import string
import random

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from ontime import messages as msg
from fulfillment.enums.status_codenames import SCN
from fulfillment.models.abc import ArchivableModel
from fulfillment.models.status import Status


class TicketMixin:
    def get_has_ticket(self):
        return (
            self.user.tickets.filter(
                related_object_identifier=self.identifier,
            )
            .exclude(status__codename__in=["closed", "deleted"])
            .exists()
        )

    def get_has_ticket_message(self, prefix=""):
        has_ticket = self.get_has_ticket()

        if has_ticket:
            return "%s(%s)" % (prefix, msg.ALREADY_HAS_TICKET)
        return ""


class TicketCategory(models.Model):
    title = models.CharField(max_length=255)

    can_select_order = models.BooleanField(default=False)
    can_select_package = models.BooleanField(default=False)
    can_select_shipment = models.BooleanField(default=False)
    can_select_payment = models.BooleanField(default=False)

    class Meta:
        db_table = "ticket_category"
        verbose_name_plural = "Ticket categories"

    def __str__(self):
        return self.title


class Ticket(ArchivableModel, models.Model):
    number = models.CharField(max_length=20, unique=True)
    category = models.ForeignKey(
        "fulfillment.TicketCategory",
        on_delete=models.PROTECT,
        related_name="tickets",
        related_query_name="ticket",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tickets",
        related_query_name="ticket",
    )
    status = models.ForeignKey(
        "fulfillment.Status",
        on_delete=models.PROTECT,
        related_name="related_tickets",
        related_query_name="related_ticket",
        limit_choices_to={"type": Status.TICKET_TYPE},
    )

    # Related object fields
    object_id = models.CharField(max_length=15, db_index=True, null=True, blank=True)
    object_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_index=True,
        null=True,
        blank=True,
        limit_choices_to={"model__in": ["shipment", "order", "transaction", "package"]},
    )
    related_object = GenericForeignKey("object_type", "object_id")
    related_object_identifier = models.CharField(
        max_length=50, db_index=True, null=True, blank=True
    )

    problem_description = models.TextField()

    answered_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    status_last_update_time = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ticket"

    def __str__(self):
        return "Ticket [%s user=%s]" % (self.number, self.user)

    @classmethod
    def get_can_add_comment_status_codenames(cls):
        return ["accepted", "investigating"]

    @property
    def can_user_add_comment(self):
        return (
            self.status_id
            and self.status.codename in Ticket.get_can_add_comment_status_codenames()
        )

    @property
    def can_user_archive(self):
        return self.status.codename in [SCN.TICKET.CLOSED, SCN.TICKET.DELETED]

    def save(self, *arsg, **kwargs):
        if not self.number:
            self.number = self._generate_new_ticket_number()

        if self.object_id and self.object_type_id:
            self.related_object_identifier = self.related_object.identifier

        return super().save(*arsg, **kwargs)

    def _generate_new_ticket_number(self):
        digits = list(string.digits)
        new_number = "".join(random.choice(digits) for i in range(6))

        if Ticket.objects.filter(number=new_number).exists():
            return self._generate_new_ticket_number()

        return new_number


class TicketComment(models.Model):
    ticket = models.ForeignKey(
        "fulfillment.Ticket",
        on_delete=models.CASCADE,
        related_name="comments",
        related_query_name="comment",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_comments",
        related_query_name="ticket_comment",
    )
    is_by_customer_service = models.BooleanField(default=False)
    body = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ticket_comment"

    def __str__(self):
        return "Ticket comment [%s author=%s]" % (self.ticket, self.author)


def get_ticket_attachment_upload_path(instance, filename):
    now = timezone.now().strftime("%Y/%m/%d")
    ts = str(timezone.now().timestamp()).replace(".", "_")

    if instance.ticket_id:
        return "tickets/%s/attachments/%s/%s" % (now, ts, filename)

    elif instance.comment_id:
        return "tickets/%s/comments/%s/attachments/%s/%s/%s" % (
            instance.comment.ticket_id,
            instance.comment_id,
            now,
            ts,
            filename,
        )

    return "tickets/attachments/%s/%s/%s" % (now, ts, filename)


class TicketAttachment(models.Model):
    ticket = models.ForeignKey(
        "fulfillment.Ticket",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ticket_attachments",
        related_query_name="ticket_attachment",
    )
    comment = models.ForeignKey(
        "fulfillment.TicketComment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comment_attachments",
        related_query_name="comment_attachment",
    )
    file = models.FileField(upload_to=get_ticket_attachment_upload_path)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ticket_attachment"

    def __str__(self):
        return "Ticket attachment [ticket=%s comment=%s]" % (self.ticket, self.comment)
