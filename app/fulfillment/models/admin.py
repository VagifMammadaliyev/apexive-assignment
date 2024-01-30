from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import JSONField

from customer.models import User
from fulfillment.models.abc import SoftDeletionModel


class ShoppingAssistantProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="assistant_profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_staff": True},
    )
    countries = models.ManyToManyField(
        "core.Country",
        related_name="assitant_profiles",
        related_query_name="assistant_profile",
    )
    assigned_orders = models.ManyToManyField("fulfillment.Order", through="Assignment")
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "shopping_assistant"

    def __str__(self):
        return "Assistant [%s]" % (self.user.full_name)


class Assignment(SoftDeletionModel):
    assistant_profile = models.ForeignKey(
        "fulfillment.ShoppingAssistantProfile",
        related_name="assignments",
        related_query_name="assignment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    order = models.OneToOneField(
        "fulfillment.Order",
        related_name="as_assignment",
        on_delete=models.CASCADE,
    )

    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "assignment"

    def __str__(self):
        return "%s [%s]" % (self.order, self.assistant_profile)


class WarehousemanProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="warehouseman_profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_staff": True},
    )
    warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehousemen",
        related_query_name="warehouseman",
    )

    extra = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "warehouseman_profile"

    def __str__(self):
        return "Warehouseman [%s]" % (self.user.full_name)


class CashierProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="cashier_profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_staff": True},
    )
    warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cashiers",
        related_query_name="cashier",
    )

    class Meta:
        db_table = "cashier_profile"
        unique_together = ["user", "warehouse"]

    def __str__(self):
        return "Cashier [%s]" % (self.user.full_name)


class CustomerServiceProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="customer_service_profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_staff": True},
    )
    warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_service_workers",
        related_query_name="customer_service_worker",
    )

    class Meta:
        db_table = "customer_service"
        unique_together = ["user", "warehouse"]

    def __str__(self):
        return "Customer service [%s]" % (self.user.full_name)


class CourierProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="courier_profile",
        on_delete=models.CASCADE,
        limit_choices_to={"is_staff": True},
    )
    city = models.ForeignKey(
        "core.City",
        on_delete=models.PROTECT,
        related_name="couriers",
        related_query_name="courier",
    )

    class Meta:
        db_table = "courier_profile"

    def __str__(self):
        return "Courier [%s]" % (self.user.full_name)
