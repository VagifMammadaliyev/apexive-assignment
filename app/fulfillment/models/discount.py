from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from ontime import messages as msg


class Discount(models.Model):
    SIMPLE_DISCOUNT = "sd"
    INVITE_FRIEND_DISCOUNT = "ifd"

    REASONS = (
        (SIMPLE_DISCOUNT, msg.SIMPLE_DISCOUNT_REASON),
        (INVITE_FRIEND_DISCOUNT, msg.INVITE_FRIEND_DISCOUNT_REASON),
    )

    percentage = models.DecimalField(default=0, decimal_places=2, max_digits=9)
    reason = models.CharField(choices=REASONS, default=SIMPLE_DISCOUNT, max_length=3)

    object_id = models.CharField(max_length=15, db_index=True)
    object_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_index=True,
        limit_choices_to={
            "model__in": [
                "shipment",
                "order",
                "courierorder",
            ]
        },
    )
    related_object = GenericForeignKey("object_type", "object_id")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "discount"

    def __str__(self):
        return (
            f"{self.percentage}% - {self.get_reason_display()} - {self.related_object}"
        )
