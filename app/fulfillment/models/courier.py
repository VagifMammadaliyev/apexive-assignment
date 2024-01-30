import string
import random

from django.db import models, transaction
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.utils import timezone

from ontime import messages as msg
from fulfillment.enums.status_codenames import SCN
from fulfillment.models.abc import (
    ArchivableModel,
    DiscountableModelMixin,
    CashbackableModelMixin,
)
from fulfillment.models.status import Status


class CourierArea(models.Model):
    city = models.ForeignKey(
        "core.City",
        related_name="courier_areas",
        related_query_name="courier_area",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255)
    warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.PROTECT,
        related_name="courier_areas",
        related_query_name="courier_area",
    )

    class Meta:
        db_table = "courier_area"

    def __str__(self):
        return "%s" % (self.title)


class CourierTariff(models.Model):
    title = models.CharField(max_length=255)
    area = models.ForeignKey(
        "fulfillment.CourierArea",
        on_delete=models.CASCADE,
        related_name="tariffs",
        related_query_name="tariff",
    )

    price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    discounted_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )

    @property
    def active_price(self):
        return self.discounted_price if self.discounted_price >= 0 else self.price

    class Meta:
        db_table = "courier_tariff"

    def __str__(self):
        return "%s - %s%s" % (self.title, self.active_price, self.price_currency.symbol)


class CourierRegion(models.Model):
    title = models.CharField(max_length=255)
    area = models.ForeignKey(
        "fulfillment.CourierArea",
        on_delete=models.CASCADE,
        related_name="courier_regions",
        related_query_name="courier_region",
    )

    class Meta:
        db_table = "courier_region"

    def __str__(self):
        return "%s [%s]" % (self.title, self.area)


class CourierOrder(
    ArchivableModel, models.Model, DiscountableModelMixin, CashbackableModelMixin
):
    discounts = GenericRelation(
        "fulfillment.Discount",
        content_type_field="object_type",
        object_id_field="object_id",
    )
    promo_codes = GenericRelation(
        "fulfillment.PromoCodeBenefit",
        content_type_field="object_type",
        object_id_field="object_id",
    )

    number = models.CharField(unique=True, max_length=20)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="courier_orders",
        related_query_name="courier_order",
    )
    status = models.ForeignKey(
        "fulfillment.Status",
        on_delete=models.PROTECT,
        related_name="courier_orders",
        related_query_name="courier_order",
        limit_choices_to={"type": Status.COURIER_ORDER_TYPE},
    )
    courier = models.ForeignKey(
        "fulfillment.CourierProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        related_query_name="order",
    )
    region = models.ForeignKey(
        "fulfillment.CourierRegion",
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    tariff = models.ForeignKey(
        "fulfillment.CourierTariff",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )
    # destination_address = models.ForeignKey(
    #     "customer.Address", on_delete=models.CASCADE, related_name="+"
    # )
    recipient = models.ForeignKey(
        "customer.FrozenRecipient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courier_orders",
        related_query_name="courier_order",
    )
    total_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    total_price_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    is_paid = models.BooleanField(default=False)
    additional_note = models.TextField(null=True, blank=True)

    failed_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status_last_update_time = models.DateTimeField(null=True, blank=True)
    expenses = models.JSONField(null=True, blank=True)
    extra = models.JSONField(default=dict, null=True, blank=True)

    class Meta:
        db_table = "courier_order"

    def __str__(self):
        return "%s - [%s %s] [%s]" % (
            self.courier,
            self.region,
            self.tariff,
            self.status,
        )

    @property
    def identifier(self):
        return self.number

    @property
    def can_user_archive(self):
        return self.status.codename in [SCN.COURIER.FAILED, SCN.COURIER.SUCCEED]

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._generate_courier_order_number()

        # if self.region_id and self.region.area_id:
        #    self.total_price_currency = self.region.area.price_currency
        #    self.total_price = self.region.area.active_price

        must_recalculate = getattr(self, "_must_recalculate", False)
        if not self.total_price_currency_id or must_recalculate:
            self.total_price, self.total_price_currency = self.calculate_total_price()
        self.status_last_update_time = timezone.now()

        super().save(*args, **kwargs)

        from domain.services import try_create_promo_code_cashbacks

        try_create_promo_code_cashbacks(self)

    def calculate_total_price(self):
        from domain.utils import CourierCalculator

        calculator = CourierCalculator()
        return calculator.calculate(self.region_id, self.tariff_id)

    def _generate_courier_order_number(self):
        digits = list(string.digits)
        new_number = str(self.region_id or random.choice(digits)) + "".join(
            random.choice(digits) for i in range(5)
        )

        if CourierOrder.objects.filter(number=new_number).exists():
            return self._generate_courier_order_number()

        return new_number

    def serialize_for_payment(self):
        return {
            "identifier": self.identifier,
            "type": "courier",
            "title": msg.COURIER_ORDER_PAYMENT_TITLE_FMT
            % {"count": self.shipments.count()},
            "weight": None,
            "is_oneclick": False,
        }
