import typing
from decimal import Decimal

from django.db import models
from django.db.models.deletion import Collector
from django.utils import timezone
from django.db import transaction

__all__ = [
    "SoftDeletionModel",
    "CashbackableModelMixin",
    "DiscountableModelMixin",
    "SoftDeletionManager",
]


class SoftDeletionQueryset(models.QuerySet):
    def delete(self):
        for obj in self:
            obj.delete()
        self.model.post_soft_queryset_delete(self)

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted_at=None)

    def dead(self):
        return self.exclude(deleted_at=None)


class SoftDeletionManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.alive_only = kwargs.pop("alive_only", True)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        if self.alive_only:
            return (
                SoftDeletionQueryset(self.model, using=self._db)
                .filter(deleted_at=None)
                .all()
            )
        return SoftDeletionQueryset(self.model, using=self._db).all()


class SoftDeletionModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeletionManager()
    all_objects = SoftDeletionManager(alive_only=False)

    class Meta:
        abstract = True

    def post_soft_delete(self):
        pass

    @classmethod
    def post_soft_queryset_delete(cls, qs):
        pass

    @classmethod
    def do_delete(cls, instance):
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])

        instance.post_soft_delete()

    @transaction.atomic
    def delete(self):
        SoftDeletionModel.do_delete(self)

        collector = Collector(using="default")
        collector.collect([self], keep_parents=False)

        # HACK
        for klass in collector.data.keys():
            if issubclass(klass, SoftDeletionModel):
                items = collector.data[klass]
                collector.data[klass] = set()
                for item in items:
                    SoftDeletionModel.do_delete(item)

        hard_fast_deletes = []
        for qs in collector.fast_deletes:
            if qs and isinstance(qs[0], SoftDeletionModel):
                for item in qs:
                    SoftDeletionModel.do_delete(item)
            else:
                hard_fast_deletes.append(qs)

        collector.fast_deletes = hard_fast_deletes
        collector.delete()

    def hard_delete(self):
        super().delete()


class DiscountableModelMixin:
    """
    Mixin provides methods to calculate dicsounted price
    based on provided total price.
    """

    total_price_field_name = "total_price"
    total_price_currency_field_name = "total_price_currency"
    discounts_field_name = "discounts"
    prefetched_discounts_field_name = "prefetched_discounts"

    def _get_discounts(self):
        from fulfillment.models.discount import Discount

        discounts: typing.List[Discount] = getattr(
            self, self.prefetched_discounts_field_name, None
        )

        if discounts is None:
            discounts = getattr(
                self, self.discounts_field_name, Discount.objects.none()
            )
            discounts = discounts.all()

        return discounts

    @property
    def discounted_total_price(self):
        # Must raise attribute error when invalid field name is provided
        discounted_amount = getattr(self, self.total_price_field_name)

        if discounted_amount is None:
            return discounted_amount

        discounted_amount = Decimal(discounted_amount)
        return self.apply_discounts_to_price(discounted_amount)

    @property
    def discounted_total_price_currency(self):
        return getattr(self, self.total_price_currency_field_name)

    @property
    def discounted_total_price_currency_id(self):
        return getattr(self, f"{self.total_price_currency_field_name}_id")

    def apply_discounts_to_price(self, amount):
        discounts = self._get_discounts()

        discounted_amount = Decimal(str(amount))

        for discount in discounts:
            discounted_amount -= discounted_amount * discount.percentage / 100

        return max(round(discounted_amount, 2), Decimal("0.00"))

    @property
    def serialized_discounted_total_price_currency(self):
        from core.serializers.client import CurrencySerializer

        return CurrencySerializer(self).data


class CashbackableModelMixin:
    def get_appliable_cashbacks(self, mark_used=False):
        from domain.utils.cashback import Cashback

        return Cashback.build_from_extra(self, mark_used=mark_used)
