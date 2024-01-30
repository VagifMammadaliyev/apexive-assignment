from decimal import Decimal

from django.db import models
from django.db.models import Q
from core.converter import Converter
from fulfillment.models.abc import SoftDeletionModel, SoftDeletionManager


class TariffQueryset(models.QuerySet):
    def get_fixed(
        self, source_id, destination_id, is_dangerous=False, is_by_country=False
    ):

        source_query = (
            Q(source_city__country_id=source_id)
            if is_by_country
            else Q(source_city__id=source_id)
        )
        destination_query = (
            Q(destination_city__country_id=destination_id)
            if is_by_country
            else Q(destination_city__id=destination_id)
        )

        return self.filter(
            source_query,
            destination_query,
            is_dangerous=is_dangerous,
            is_fixed_price=True,
        ).first()

    def get_for_weight(
        self, weight, source_id, destination_id, is_dangerous=False, is_by_country=False
    ):
        if weight is None:
            weight = -1

        source_query = (
            Q(source_city__country_id=source_id)
            if is_by_country
            else Q(source_city__id=source_id)
        )
        destination_query = (
            Q(destination_city__country_id=destination_id)
            if is_by_country
            else Q(destination_city__id=destination_id)
        )
        candidate = (
            self.filter(
                source_query,
                destination_query,
                min_weight__lt=weight,
                is_dangerous=is_dangerous,
            )
            .order_by("min_weight")
            .last()
        )

        if candidate and candidate.max_weight:
            if weight <= candidate.max_weight:
                return candidate
            return None
        return candidate


class Tariff(SoftDeletionModel):
    title = models.CharField(max_length=50)

    source_city = models.ForeignKey(
        "core.City",
        on_delete=models.CASCADE,
        related_name="source_tariffs",
        related_query_name="source_tariff",
    )

    destination_city = models.ForeignKey(
        "core.City",
        on_delete=models.CASCADE,
        related_name="destination_tariffs",
        related_query_name="destination_tariff",
    )

    price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    discounted_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.CASCADE, related_name="+"
    )

    min_weight = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    max_weight = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True
    )

    is_fixed_price = models.BooleanField(default=False)
    is_per_kg = models.BooleanField(default=False)
    is_dangerous = models.BooleanField(
        default=False, verbose_name="Is for liquid products"
    )

    soft_objects = SoftDeletionManager()
    objects = TariffQueryset.as_manager()

    class Meta:
        db_table = "tariff"

    def __str__(self):
        return "%s (%s - %s]" % (self.title, self.min_weight, self.max_weight or "INF")

    @property
    def active_price(self):
        return self.discounted_price if self.discounted_price >= 0 else self.price

    def calculate_price_for_weight(self, weight):
        fixed_price = Decimal("0.00")
        if not self.is_fixed_price:
            # Then we must add the fixed price
            fixed_price_tariff = Tariff.objects.get_fixed(
                self.source_city_id,
                self.destination_city_id,
                is_dangerous=self.is_dangerous,
                is_by_country=False,
            )
            if fixed_price_tariff:
                fixed_price = Converter.convert(
                    fixed_price_tariff.active_price,
                    fixed_price_tariff.price_currency.code,
                    self.price_currency.code,
                )

        return round(
            Decimal(
                (self.active_price * weight if self.is_per_kg else self.active_price)
                + fixed_price
            ),
            2,
        )
