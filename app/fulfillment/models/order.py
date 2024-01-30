import string
import random
from decimal import Decimal

from django.utils import timezone
from django.db import models, transaction
from django.contrib.postgres.fields import JSONField
from django.contrib.contenttypes.fields import GenericRelation

from ontime import messages as msg
from fulfillment.enums.status_codenames import SCN
from fulfillment.models.transaction import Transaction
from fulfillment.models.status import Status
from fulfillment.models.event import StatusEvent
from fulfillment.models.ticket import TicketMixin
from fulfillment.models.abc import (
    ArchivableModel,
    SoftDeletionModel,
    DiscountableModelMixin,
    CashbackableModelMixin,
)
from core.models import Country
from core.converter import Converter


class Order(
    SoftDeletionModel,
    ArchivableModel,
    TicketMixin,
    DiscountableModelMixin,
    CashbackableModelMixin,
):
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
    discounts = GenericRelation(
        "fulfillment.Discount",
        content_type_field="object_type",
        object_id_field="object_id",
    )
    promo_codes = GenericRelation(
        "fulfillment.PromoCode",
        content_type_field="object_type",
        object_id_field="object_id",
    )

    user = models.ForeignKey(
        "customer.User",
        on_delete=models.CASCADE,
        related_name="orders",
        related_query_name="order",
    )
    status = models.ForeignKey(
        "fulfillment.Status",
        on_delete=models.PROTECT,
        related_name="related_orders",
        related_query_name="related_order",
        limit_choices_to={"type": Status.ORDER_TYPE},
    )
    package = models.ForeignKey(
        "fulfillment.Package",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="related_orders",
        related_query_name="related_order",
    )
    source_country = models.ForeignKey(
        "core.Country", on_delete=models.PROTECT, related_name="+"
    )
    order_code = models.CharField(max_length=20, unique=True, db_index=True)
    external_order_code = models.CharField(
        max_length=20, db_index=True, null=True, blank=True
    )
    description = models.TextField()

    # Legacy field
    product_image = models.ImageField(
        upload_to="orders/previews/%Y/%d/%m", null=True, blank=True
    )
    product_image_url = models.CharField(max_length=800, null=True, blank=True)

    # Product fields (these fields is then used to create actual product when creating package)
    product_seller_address = models.CharField(max_length=300, null=True, blank=True)
    product_seller = models.CharField(max_length=300, null=True, blank=True)
    product_url = models.URLField(max_length=3000, null=True, blank=True)
    product_color = models.CharField(max_length=40, blank=True, null=True)
    product_size = models.CharField(max_length=40, blank=True, null=True)
    product_description = models.TextField(blank=True, null=True)
    product_category = models.ForeignKey(
        "fulfillment.ProductCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        related_query_name="orders",
    )
    product_type = models.ForeignKey(
        "fulfillment.ProductType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        related_query_name="order",
    )

    is_oneclick = models.BooleanField(default=True)
    # destination_user_address = models.ForeignKey(
    #     "customer.Address", on_delete=models.SET_NULL, blank=True, null=True
    # )
    destination_warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    recipient = models.ForeignKey(
        "customer.FrozenRecipient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        related_query_name="order",
    )

    # Price fields
    commission_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    real_commission_price = models.DecimalField(
        max_digits=9, decimal_places=2, default=0
    )
    product_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    real_product_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    cargo_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    real_cargo_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    product_quantity = models.PositiveIntegerField(default=1)
    real_product_quantity = models.PositiveIntegerField(default=1)

    # Currency fields
    commission_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    real_commission_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    product_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    real_product_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    cargo_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    real_cargo_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )

    # Total fields
    total_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    real_total_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    total_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    real_total_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    remainder_price = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    remainder_price_currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    # Currency of this field is total price's currency
    paid_amount = models.DecimalField(max_digits=9, decimal_places=2, default=0)

    shop = models.ForeignKey(
        "fulfillment.Shop", on_delete=models.SET_NULL, null=True, blank=True
    )
    show_on_slider = models.BooleanField(default=True)

    user_note = models.TextField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)

    status_last_update_time = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    extra = models.JSONField(default=dict, null=True, blank=True)
    expenses = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "order"

    def __str__(self):
        return "%s [%s]" % (self.order_code, self.status.codename)

    def has_remainder(self, check_transaction=True):
        """
        This method used for client API.
        We must check if any transaction for this order
        exists + if remainder price differs from zero.
        """
        remainder_price_check = self.remainder_price != 0
        if check_transaction:
            has_transaction = Transaction.objects.filter(
                user_id=self.user_id,
                purpose=Transaction.ORDER_REMAINDER_PAYMENT,
                object_id=str(self.id),
                related_object_identifier=self.identifier,
                completed=False,
            ).exists()
        else:
            has_transaction = True  # skip that check
        return self.remainder_price != 0 and has_transaction

    @property
    def identifier(self):
        return self.order_code

    @property
    def can_be_edited_by_user(self):
        return self.status_id and self.status.codename == "created"

    @property
    def can_be_payed_by_user(self):
        return self.status_id and self.status.codename in ["created", "unpaid"]

    @property
    def can_be_deleted_by_user(self):
        return self.status_id and self.status.codename == "created"

    @property
    def can_assistant_edit_order(self):
        return bool(
            self.status_id and self.status.codename not in ["deleted", "ordered"]
        )

    @property
    def can_assistant_reject_order(self):
        return self.status_id and self.status.codename not in ["deleted"]

    @property
    def can_assistant_add_package(self):
        return bool(
            self.status_id
            and self.status.codename in ["processing"]
            and self.product_category_id
            # and self.product_description
        )

    @property
    def can_assistant_start_processing(self):
        return bool(self.status_id and self.status.codename == "paid")

    @property
    def can_assistant_approve_remainder_price(self):
        return self.has_remainder(check_transaction=False)

    @property
    def consolidate(self):
        return not self.is_oneclick

    @property
    def can_user_archive(self):
        return self.status.codename in [SCN.ORDER.ORDERED, SCN.ORDER.DELETED]

    @transaction.atomic
    def save(self, *args, **kwargs):
        if not self.order_code:
            self.order_code = self._generate_new_order_code()

        if not self.status_id:
            self.status = Status.objects.get(codename="created", type=Status.ORDER_TYPE)

        if not self.product_price_currency_id:
            self.product_price_currency = self.source_country.currency
        if not self.cargo_price_currency_id:
            self.cargo_price_currency = self.source_country.currency
        if not self.total_price_currency_id:
            self.total_price_currency = self.source_country.currency

        # whether to trigger total price recalculation
        must_recalculate = getattr(self, "_must_recalculate_total_price", False)

        if not self.total_price or must_recalculate:
            from domain.conf import Configuration

            conf = Configuration()

            # Comission price is calculated here, because we need total price
            # to be able to calculate comission price
            self.total_price = self.calculate_total_price()

            self.commission_price_currency = self.total_price_currency
            self.commission_price = conf.calculate_commission_for_price(
                self.total_price, self.commission_price_currency
            )

            # Add comission price to total
            self.total_price += self.commission_price

        self.initialize_real_price_values_if_necessary()

        super().save(*args, **kwargs)
        from fulfillment.tasks import save_image_link_for_orders
        from domain.services import try_create_promo_code_cashbacks

        try_create_promo_code_cashbacks(self)

    def initialize_real_price_values_if_necessary(self):
        if not (self.is_paid and self.real_commission_price_currency_id):
            self.real_commission_price = self.commission_price
            self.real_commission_price_currency = self.commission_price_currency
        if not (self.is_paid and self.real_product_quantity):
            self.real_product_quantity = self.product_quantity
        if not (self.is_paid and self.real_product_price_currency_id):
            self.real_product_price = self.product_price
            self.real_product_price_currency = self.product_price_currency
        if not (self.is_paid and self.real_cargo_price_currency_id):
            self.real_cargo_price = self.cargo_price
            self.real_cargo_price_currency = self.cargo_price_currency
        if not (self.is_paid and self.real_total_price_currency_id):
            self.real_total_price = self.total_price
            self.real_total_price_currency = self.total_price_currency
        if not (self.is_paid and self.remainder_price_currency_id):
            self.remainder_price_currency = self.real_total_price_currency
            self.remainder_price = Decimal("0.00")

    def calculate_total_price(self):
        total_price = Decimal("0.00")

        if not self.total_price_currency:
            return total_price

        currency_code = self.total_price_currency.code

        # Product price
        product_price = Converter.convert(
            self.product_price, self.product_price_currency.code, currency_code
        )
        total_price += product_price * self.product_quantity

        # Cargo price
        cargo_price = Converter.convert(
            self.cargo_price, self.cargo_price_currency.code, currency_code
        )
        total_price += cargo_price

        return total_price

    def _generate_new_order_code(self):
        prefix = self.source_country.code.ljust(3, "0")
        code = prefix + "".join(random.choice(string.digits) for _ in range(6))

        if Order.objects.filter(order_code=code).exists():
            return self._generate_new_order_code()

        return code

    def serialize_for_payment(self):
        return {
            "identifier": self.identifier,
            "type": "order",
            "title": self.description,
            "weight": None,
            "is_oneclick": False,
        }

    def serialize_for_notification(self):
        return {
            "identifier": self.identifier,
            "type": "order",
            "title": self.description,
            "object": None,
        }

    def serialize_for_ticket(self, for_admin=False):
        data = {
            "identifier": self.identifier,
            "type": "order",
            "title": "%s (%s)"
            % (
                self.identifier,
                msg.ORDER_WORD,
                # self.get_has_ticket_message(prefix=" "),
            ),
        }

        if not for_admin:
            data["has_ticket"] = self.get_has_ticket()

        return data

    def post_soft_delete(self):
        package = getattr(self, "package", None)
        if package:
            package.order = None
            package.save(update_fields=["order"])

    @classmethod
    def post_soft_queryset_delete(cls, qs):
        from fulfillment.models import Package

        Package.objects.filter(order__id=self.id).update(order=None)
