import math
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.conf import settings
from django.db import models, transaction
from django.contrib.postgres.fields import JSONField
from django.contrib.contenttypes.fields import GenericRelation

from ontime import messages as msg
from core.converter import Converter
from fulfillment.enums.status_codenames import SCN
from fulfillment.models.abc import ArchivableModel, SoftDeletionModel
from fulfillment.models.status import Status
from fulfillment.models.event import StatusEvent
from fulfillment.models.tariff import Tariff
from fulfillment.models.ticket import TicketMixin


def get_package_attachment_path(instance, filename):
    return "cargo/packages/%s/%s" % (
        timezone.localdate().strftime("%Y/%m/%d"),
        filename,
    )


class Package(SoftDeletionModel, TicketMixin, ArchivableModel, models.Model):
    notifications = GenericRelation(
        "fulfillment.Notification",
        content_type_field="object_type",
        object_id_field="object_id",
    )
    transactions = GenericRelation(
        "fulfillment.Transaction",
        content_type_field="object_type",
        object_id_field="object_id",
    )

    user = models.ForeignKey(
        "customer.User",
        on_delete=models.CASCADE,
        related_name="packages",
        related_query_name="package",
    )
    shipment = models.ForeignKey(
        "fulfillment.Shipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="packages",
        related_query_name="package",
    )
    order = models.OneToOneField(
        "fulfillment.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    status = models.ForeignKey(
        "fulfillment.Status",
        on_delete=models.PROTECT,
        related_name="related_packages",
        related_query_name="related_package",
        limit_choices_to={"type": Status.PACKAGE_TYPE},
    )
    current_warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="packages",
        related_query_name="package",
    )
    is_problematic = models.BooleanField(
        default=False
    )  # user has not declared from his/her dashboard
    is_serviced = models.BooleanField(default=False)  # fulfilled ordered services
    is_accepted = models.BooleanField(default=False)
    is_by_assistant = models.BooleanField(default=False)
    source_country = models.ForeignKey(
        "core.Country", on_delete=models.PROTECT, related_name="+"
    )
    # Tracking code that is added by user and must be unique
    user_tracking_code = models.CharField(
        max_length=100, db_index=True, null=True, blank=True
    )
    # Tracking code that is added by user and must not be unique
    admin_tracking_code = models.CharField(
        max_length=100, db_index=True, null=True, blank=True
    )
    arrival_date = models.DateField(null=True, blank=True)
    real_arrival_date = models.DateField(null=True, blank=True)

    seller = models.CharField(max_length=300, null=True, blank=True)
    seller_address = models.CharField(max_length=300, null=True, blank=True)

    weight = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True)
    is_volume_considered = models.BooleanField(default=False)
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    shelf = models.CharField(max_length=255, null=True, blank=True)

    attachment = models.FileField(
        upload_to=get_package_attachment_path, null=True, blank=True
    )
    user_note = models.TextField(null=True, blank=True)

    status_last_update_time = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    extra = models.JSONField(default=dict, null=True, blank=True)

    warehouseman_description = models.TextField(null=True, blank=True)
    expenses = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "package"
        constraints = [
            models.UniqueConstraint(
                fields=["user_tracking_code"],
                name="unique_tracking_code_when_not_deleted",
                condition=models.Q(deleted_at__isnull=True),
            )
        ]

    def __str__(self):
        return "%s [%s]" % (self.tracking_code, self.status.codename)

    @property
    def consolidate(self):
        return not bool(self.shipment_id)

    @property
    def tracking_code(self):
        return self.admin_tracking_code or self.user_tracking_code

    @property
    def can_be_edited_by_user(self):
        return not bool(self.order_id or self.shipment_id) and (
            self.status_id and self.status.codename not in ["foreign", "deleted"]
        )

    @property
    def can_be_payed_by_user(self):
        return False  # package cannot be payed

    @property
    def can_be_deleted_by_user(self):
        correct_status = self.status_id and self.status.codename in ["awaiting"]
        no_order = not self.order_id
        return bool(correct_status and no_order)

    @property
    def can_be_consolidated_by_user(self):
        # Package is assumed as serviced if:
        #   1. It has not any ordered serviced
        #   2. It has ordered services, but already received by warehouseman
        #      and marked as serviced

        # In no other circumstances package must be marked as serviced!
        return not self.shipment_id and self.is_serviced

    @property
    def can_be_marked_as_serviced(self):
        return not self.is_serviced

    @property
    def delay_days(self):
        """
        Return delay in days. Delays are started calculating
        after arrival date has been passed.
        """
        if self.arrival_date and not self.is_accepted:
            today = timezone.now().date()
            delta = today - self.arrival_date
            return delta.days if delta.days > 0 else 0

        return 0

    @property
    def can_user_archive(self):
        return self.status.codename == SCN.PACKAGE.DELETED

    def save(self, *args, **kwargs):
        if not self.status_id:
            self.status = Status.objects.get(
                codename="awaiting", type=Status.PACKAGE_TYPE
            )

        super().save(*args, **kwargs)

    @property
    def identifier(self):
        return self.tracking_code

    def serialize_for_notification(self):
        return {
            "identifier": self.identifier,
            "type": "package",
            "title": self.tracking_code,
            "object": self.shipment_id and self.shipment.serialize_for_notification(),
        }

    def serialize_for_ticket(self, for_admin=False):
        data = {
            "identifier": self.identifier,
            "type": "package",
            "title": "%s (%s)"
            % (
                self.identifier,
                msg.PACKAGE_WORD,
                # self.get_has_ticket_message(prefix=" "),
            ),
        }

        if not for_admin:
            data["has_ticket"] = self.get_has_ticket()

        return data


class PackagePhoto(models.Model):
    package = models.ForeignKey(
        "fulfillment.Package",
        related_name="photos",
        related_query_name="photo",
        on_delete=models.CASCADE,
    )
    file = models.ImageField(upload_to="package/photos/%Y/%m/%d")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "package_photo"

    def __str__(self):
        return f"Photo of [{self.package}]"
