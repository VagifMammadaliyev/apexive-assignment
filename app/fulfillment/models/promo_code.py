import string
import random
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from fulfillment.models.abc import SoftDeletionModel
from core.converter import Converter
from core.models import Currency

User = get_user_model()


class PromoCode(models.Model):
    value = models.CharField(max_length=20, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="promo_code", on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "promo_code"

    def __str__(self):
        return f"{self.value} - {self.user}"

    @classmethod
    def generate_new_promo_code_value(cls):
        print("generating promo code value")
        length = 7
        new_value = "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(length)
        )

        if cls.objects.filter(value=new_value).exists():
            return cls.generate_new_promo_code_value()

        print("generated promo code value")
        return new_value

    def save(self, *args, **kwargs):
        if not self.value:
            self.value = PromoCode.generate_new_promo_code_value()

        return super().save(*args, **kwargs)

    def register(self, user: User):
        from domain.exceptions.customer import InvalidPromoCode

        if not self.user.is_active:
            raise InvalidPromoCode

        if user.registered_promo_code_id:
            return False
        user.registered_promo_code = self
        user.save(update_fields=["registered_promo_code"])
        return True

    def get_next_cashback(self):
        from domain.conf import Configuration
        from domain.utils.cashback import Cashback

        conf = Configuration()

        # How many people used this promocode
        usable_benefit = PromoCodeBenefit.objects.filter(
            promo_code=self, used_by_owner=False, used_by_consumer=True
        ).first()

        if usable_benefit:
            related_transaction = (
                usable_benefit.related_object.transactions.filter(
                    completed=True, is_deleted=False, deleted_at__isnull=True
                )
                .order_by("id")
                .first()
            )

            if related_transaction:
                amount = (
                    related_transaction.discounted_amount
                    * conf.invite_friend_cashback_percentage
                    / Decimal("100")
                )
                currency = related_transaction.discounted_amount_currency
                # Convert amount to USD for easier calculation
                converted_amount = Converter.convert(
                    amount, currency, "USD", ignore_missing_currency=True
                )
                usd_currency_id = (
                    Currency.objects.filter(code="USD")
                    .values_list("id", flat=True)
                    .first()
                )
                usable_benefit.used_by_owner = True
                usable_benefit.cashback_amount = amount
                usable_benefit.cashback_amount_currency_id = usd_currency_id
                usable_benefit.save(
                    update_fields=[
                        "used_by_owner",
                        "cashback_amount",
                        "cashback_amount_currency_id",
                    ]
                )
                return Cashback(
                    amount=amount,
                    currency_code=currency.code,
                )
                # return conf.get_invite_friend_cashback()

        return None


class PromoCodeBenefit(SoftDeletionModel):
    promo_code = models.ForeignKey(
        "fulfillment.PromoCode",
        related_name="used_benefits",
        related_query_name="used_benefit",
        on_delete=models.CASCADE,
    )
    consumer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="consumed_benefits",
        related_query_name="consumed_benefit",
        on_delete=models.CASCADE,
    )
    used_by_owner = models.BooleanField(default=False)
    used_by_consumer = models.BooleanField(default=False)

    object_id = models.CharField(max_length=15, db_index=True)
    object_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_index=True,
        limit_choices_to={"model__in": ["shipment", "order", "courierorder"]},
    )
    related_object = GenericForeignKey("object_type", "object_id")
    related_object_identifier = models.CharField(max_length=50, db_index=True)

    cashback_amount = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True
    )
    cashback_amount_currency = models.ForeignKey(
        "core.Currency",
        related_name="+",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "promo_code_benefit"
        unique_together = ["object_type", "object_id"]

    def __str__(self):
        return f"Benefit from [{self.promo_code}] for [{self.consumer}]"

    def save(self, *args, **kwargs):
        if not self.related_object_identifier:
            self.related_object_identifier = self.related_object.identifier

        return super().save(*args, **kwargs)
