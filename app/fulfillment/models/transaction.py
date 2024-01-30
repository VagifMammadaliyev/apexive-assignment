import uuid
from decimal import Decimal

from django.db import models, transaction as db_transaction
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _
from django.contrib.postgres.fields import JSONField
from django.contrib.contenttypes.fields import GenericRelation
from django.utils import timezone
from django.utils.functional import cached_property

from ontime import messages as msg
from core.converter import Converter
from fulfillment.models.abc import ArchivableModel, SoftDeletionModel
from fulfillment.models.ticket import TicketMixin


class Transaction(SoftDeletionModel, TicketMixin, ArchivableModel):
    ORDER_PAYMENT = "order_payment"
    SHIPMENT_PAYMENT = "shipment_payment"
    COURIER_ORDER_PAYMENT = "courier_order_payment"
    ORDER_REMAINDER_PAYMENT = "order_remainder_payment"
    ORDER_REMAINDER_REFUND = "order_remainder_refund"
    ORDER_REFUND = "order_refund"
    SHIPMENT_REFUND = "shipment_refund"
    BALANCE_INCREASE = "balance_increase"
    BALANCE_DECREASE = "balance_decrease"
    CASHBACK = "cashback"
    MERGED = "merged"

    PURPOSES = (
        (ORDER_PAYMENT, msg.ORDER_PAYMENT),
        (SHIPMENT_PAYMENT, msg.SHIPMENT_PAYMENT),
        (ORDER_REMAINDER_PAYMENT, msg.ORDER_REMAINDER_PAYMENT),
        (COURIER_ORDER_PAYMENT, msg.COURIER_ORDER_PAYMENT),
        (ORDER_REFUND, msg.ORDER_REFUND),
        (ORDER_REMAINDER_REFUND, msg.ORDER_REMAINDER_REFUND),
        (SHIPMENT_REFUND, msg.SHIPMENT_REFUND),
        (BALANCE_INCREASE, msg.BALANCE_INCREASE),
        (BALANCE_DECREASE, msg.BALANCE_DECREASE),
        (CASHBACK, msg.CASHBACK),
        (MERGED, msg.MERGED),
    )

    CYBERSOURCE_SERVICE = "cybersource"
    PAYPAL_SERVICE = "paypal"
    PAYTR_SERVICE = "paytr"
    PAYMENT_SERVICES = (
        (CYBERSOURCE_SERVICE, "Cybersource"),
        (PAYPAL_SERVICE, "PayPal"),
        (PAYTR_SERVICE, "PayTR"),
    )
    FLAT_PAYMENT_SERVICES = [s[0] for s in PAYMENT_SERVICES]

    CARD = "card"
    CASH = "cash"
    BALANCE = "balance"
    TERMINAL = "terminal"

    TYPES = (
        (CARD, msg.CARD),
        (CASH, msg.CASH),
        (BALANCE, msg.BALANCE),
        (TERMINAL, msg.TERMINAL),
    )
    FLAT_TYPES = (CARD, CASH, BALANCE)

    notifications = GenericRelation(
        "fulfillment.Notification",
        content_type_field="object_type",
        object_id_field="object_id",
    )

    invoice_number = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    user = models.ForeignKey(
        "customer.User",
        on_delete=models.CASCADE,
        related_name="transactions",
        related_query_name="transaction",
    )
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        related_query_name="child",
        null=True,
        blank=True,
    )

    amount = models.DecimalField(max_digits=9, decimal_places=2, default=0)
    purpose = models.CharField(max_length=30, choices=PURPOSES)
    type = models.CharField(max_length=10, choices=TYPES, default=CASH)

    object_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_index=True,
        null=True,
        blank=True,
        limit_choices_to={"model__in": ["shipment", "order", "courierorder"]},
    )
    object_id = models.CharField(max_length=15, db_index=True, null=True, blank=True)
    related_object = GenericForeignKey("object_type", "object_id")
    related_object_identifier = models.CharField(
        max_length=50, db_index=True, null=True, blank=True
    )

    completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    payment_service = models.CharField(
        choices=PAYMENT_SERVICES, null=True, blank=True, max_length=30
    )
    payment_service_responsed_at = models.DateTimeField(null=True, blank=True)
    payment_service_response_json = models.JSONField(default=dict, blank=True)

    # When transactions are normalized, store original values in these fields.
    original_amount = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True, default=None
    )
    original_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    # When customer has not enough balance and he pays by Card/PayPal, and another part by balance
    is_partial = models.BooleanField(default=False)
    from_balance_amount = models.DecimalField(
        max_digits=9, decimal_places=2, null=True, blank=True, default=None
    )
    from_balance_currency = models.ForeignKey(
        "core.Currency",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    cashback_to = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="cashbacks",
        related_query_name="cashback",
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(null=True, blank=True)
    completed_manually = models.BooleanField(default=False)

    is_deleted = models.BooleanField(default=False)

    extra = models.JSONField(default=dict, null=True, blank=True)
    expenses = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "transaction"

    def __str__(self):
        return "%s %s [user=%s purpose=%s type=%s]" % (
            self.amount,
            self.currency.code,
            self.user.full_phone_number,
            self.purpose,
            self.type,
        )

    @cached_property
    def old_amount(self):
        pk = self.pk
        if pk:
            old_trans = Transaction.objects.filter(pk=pk).values("amount").first()
            if old_trans:
                return old_trans["amount"]
        return None

    @cached_property
    def old_currency_id(self):
        pk = self.pk
        if pk:
            old_trans = Transaction.objects.filter(pk=pk).values("currency_id").first()
            if old_trans:
                return old_trans["currency_id"]
        return None

    @property
    def identifier(self):
        return self.invoice_number

    @property
    def is_amount_changed(self):
        return (
            self.old_amount != self.amount or self.old_currency_id != self.currency_id
        )

    @property
    def can_user_archive(self):
        return True

    @db_transaction.atomic
    def save(self, *args, **kwargs):
        if self.original_amount is None and not self.original_currency_id:
            self.original_amount = self.amount
            self.original_currency = self.currency

        if not self.related_object_identifier:
            self.related_object_identifier = (
                self.related_object and self.related_object.identifier
            )

        super().save(*args, **kwargs)

        # update existing cashbacks (promo code)
        if self.is_amount_changed:
            self.update_related_cashbacks()

        # create cashbacks if related object has some
        from domain.utils.cashback import Cashback

        if self.related_object:
            cashbacks = self.related_object.get_appliable_cashbacks(mark_used=True)
            for cashback in cashbacks:
                real_transaction = cashback.create_transaction(cashback_to=self)

    @db_transaction.atomic
    def update_related_cashbacks(self):
        cashbacks = self.cashbacks.filter(
            extra__invite_friend_cashback=True, completed=False
        )
        for cashback in cashbacks:
            # calculate percentage of this cashback
            perc = cashback.amount / self.old_amount
            new_cashback_amount = self.amount * perc
            cashback.amount = new_cashback_amount
            cashback.original_amount = new_cashback_amount
            cashback.save()

    def serialize_for_notification(self):
        return {
            "identifier": self.identifier,
            "type": "payment",
            "title": "%s%s - %s"
            % (self.amount, self.currency.symbol, self.get_purpose_display()),
            "object": self.related_object
            and self.related_object.serialize_for_payment(),
        }

    def serialize_for_ticket(self, for_admin=False):
        data = {
            "identifier": self.identifier,
            "type": "payment",
            "title": "%s (%s)"
            % (
                self.identifier and str(self.identifier).upper(),
                msg.PAYMENT_WORD,
                # self.get_has_ticket_message(prefix=" "),
            ),
        }

        if not for_admin:
            data["has_ticket"] = self.get_has_ticket()

        return data

    def check_payment_service_confirmation(self):
        """
        Check that payment service confirmed our transaction.
        """
        if self.payment_service == self.CYBERSOURCE_SERVICE:
            return self.payment_service_response_json.get("decision") == "ACCEPT"
        elif self.payment_service == self.PAYPAL_SERVICE:
            capture_response = self.payment_service_response_json.get(
                "capture_response"
            )
            return (
                bool(capture_response) and capture_response.get("status") == "COMPLETED"
            )
        elif self.payment_service == self.PAYTR_SERVICE:
            return self.payment_service_response_json.get("status") == "success"
        return False

    def get_payment_service_transaction_amount(self):
        """
        Gets amount of payment service transaction (currency of this transaction is used).
        """
        amount = Decimal("0.00")

        if not self.payment_service_response_json:
            return amount

        if self.payment_service == self.PAYPAL_SERVICE:
            capture_response = self.payment_service_response_json.get(
                "capture_response"
            )

            if capture_response:
                purchase_units = capture_response.get("purchase_units", [])

                for purchase_unit in purchase_units:
                    payments = purchase_unit.get("payments", {})
                    captures = payments.get("captures", [])

                    for capture in captures:
                        amount_data = capture.get("amount", {})

                        if amount_data:
                            amount += Converter.convert(
                                amount_data.get("value", 0),
                                amount_data.get(
                                    "currency_code", settings.PAYPAL_CURRENCY_CODE
                                ),
                                self.currency.code,
                            )

        elif self.payment_service == self.CYBERSOURCE_SERVICE:
            amount += Converter.convert(
                self.payment_service_response_json.get("req_amount"),
                self.payment_service_response_json.get(
                    "req_currency", settings.CYBERSOURCE_CURRENCY_CODE
                ),
                self.currency.code,
            )

        elif self.payment_service == self.PAYTR_SERVICE:
            original_amount = Decimal(
                self.payment_service_response_json["payment_amount"]
            ) / Decimal("100")
            amount += Converter.convert(original_amount, "TRY", self.currency.code)

        return amount

    def get_refundable_amount(self):
        if self.is_partial:
            return self.amount + Converter.convert(
                self.from_balance_amount,
                self.from_balance_currency.code,
                self.currency.code,
            )

        return self.amount

    @property
    def discounted_amount(self):
        amount = self.amount

        # Fetch discounts from related model
        if self.related_object and hasattr(self.related_object, "discounts"):
            discounts = self.related_object.discounts.all()

            for discount in discounts:
                amount -= amount * discount.percentage / 100

        return amount

    @property
    def discounted_amount_currency(self):
        return self.currency

    @property
    def discounted_amount_currency_id(self):
        return self.currency_id

    @property
    def cashbackable_amount(self):
        """Returns amount in self.discounted_amount_currency"""
        cashbacks = self.cashbacks.filter(purpose=Transaction.CASHBACK).values_list(
            "amount", "currency__code"
        )

        amount = self.discounted_amount

        for camount, ccurency in cashbacks:
            amount -= Converter.convert(
                camount, ccurency, self.discounted_amount_currency.code
            )

        return amount

    def get_cashback_amount(self, complete_cashbacks=True):
        amount = self.dry_cashback_amount
        self.get_unapplied_cashbacks().update(
            completed=True, completed_at=timezone.now()
        )
        return amount

    def get_unapplied_cashbacks(self):
        return self.cashbacks.filter(purpose=Transaction.CASHBACK, completed=False)

    @property
    def dry_cashback_amount(self):
        cashbacks = self.get_unapplied_cashbacks().values_list(
            "amount", "currency__code"
        )

        amount = 0
        for camount, ccurency in cashbacks:
            amount += Converter.convert(camount, ccurency, self.currency.code)

        return amount

    def post_soft_delete(self):
        from domain.services import remove_from_parent

        if not self.completed:
            remove_from_parent(self)

    @db_transaction.atomic
    def delete(self):
        if not self.completed:
            super().delete()
