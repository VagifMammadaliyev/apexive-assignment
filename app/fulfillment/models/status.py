from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg


class Status(models.Model):
    ORDER_TYPE = "order_statuses"
    PACKAGE_TYPE = "package_statuses"
    SHIPMENT_TYPE = "shipment_statuses"
    COURIER_ORDER_TYPE = "courier_order_statuses"
    TICKET_TYPE = "ticket_statuses"

    TYPES = (
        (ORDER_TYPE, msg.ORDER_TYPE),
        (PACKAGE_TYPE, msg.PACKAGE_TYPE),
        (SHIPMENT_TYPE, msg.SHIPMENT_TYPE),
        (COURIER_ORDER_TYPE, msg.COURIER_ORDER_TYPE),
        (TICKET_TYPE, msg.TICKET_TYPE),
    )

    codename = models.CharField(max_length=20)
    display_name = models.CharField(max_length=40)
    type = models.CharField(max_length=30, choices=TYPES)
    order = models.PositiveIntegerField(default=0)

    extra = models.JSONField(default=dict, null=True, blank=True)

    class Meta:
        db_table = "status"
        unique_together = ["codename", "type"]
        ordering = ["order"]
        verbose_name_plural = "Statuses"

    def save(self, *args, **kwargs):
        self.codename = self.codename.lower()
        super().save(*args, **kwargs)

    def natural_key(self):
        return (self.type, self.codename)

    @property
    def next(self):
        if self.extra.get("next"):
            return Status.objects.get(type=self.type, codename=self.extra.get("next"))
        return Status.objects.filter(type=self.type, order__gt=self.order).first()

    @property
    def prev(self):
        return Status.objects.filter(type=self.type, order__lt=self.order).last()

    @property
    def is_final(self):
        return self.extra.get("is_final", False)

    def __str__(self):
        return "%s [codename=%s type=%s]" % (
            self.display_name,
            self.codename,
            self.type,
        )


class TrackingStatus(models.Model):
    pl_number = models.CharField(max_length=5)
    problem_code = models.CharField(max_length=3, null=True, blank=True)
    problem_code_description = models.TextField(null=True, blank=True)
    tracking_code = models.CharField(max_length=4)
    tracking_code_description = models.TextField(null=True, blank=True)
    tracking_code_explanation = models.TextField(null=True, blank=True)
    tracking_condition_code = models.CharField(max_length=4, null=True, blank=True)
    tracking_condition_code_description = models.TextField(null=True, blank=True)
    mandatory_comment = models.TextField(null=True, blank=True)
    final_status = models.BooleanField(default=False)
    delivery_status = models.BooleanField(default=False)

    customs_default = models.BooleanField(default=False)

    class Meta:
        db_table = "tracking_status"
        verbose_name_plural = "Tracking statuses"

    def __str__(self):
        return "[%s] %s" % (self.tracking_code, self.tracking_code_description)
