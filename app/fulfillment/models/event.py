from django.db import models

from fulfillment.models.abc import SoftDeletionModel


class StatusEvent(SoftDeletionModel):
    """Events for status changes of packages and orders."""

    from_status = models.ForeignKey(
        "fulfillment.Status",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    to_status = models.ForeignKey(
        "fulfillment.Status",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    message = models.CharField(max_length=150, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    order = models.ForeignKey(
        "fulfillment.Order",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="status_events",
        related_query_name="status_event",
    )
    package = models.ForeignKey(
        "fulfillment.Package",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="status_events",
        related_query_name="status_event",
    )
    shipment = models.ForeignKey(
        "fulfillment.Shipment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="status_events",
        related_query_name="status_event",
    )

    class Meta:
        db_table = "status_event"

    @property
    def ref_object(self):
        if self.order_id:
            return self.order
        if self.package_id:
            return self.package
        if self.shipment_id:
            return self.shipment

        return None

    def __str__(self):
        return "[%s -> %s] [%s]" % (
            self.from_status and self.from_status.codename,
            self.to_status and self.to_status.codename,
            self.ref_object,
        )
