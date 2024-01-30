from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import F, Sum
from django.conf import settings

from domain.exceptions.customer import InsufficientBalanceError
from domain.exceptions.logic import InvalidActionError, DifferentPackageSourceError
from core.models import Currency
from core.converter import Converter
from core.serializers.client import CurrencySerializer
from customer.models.user import User
from fulfillment.models import Transaction, Shipment, Warehouse, Status


class Customer(User):
    class Meta:
        proxy = True

    @property
    def active_balance(self):
        currency = Currency.objects.filter(country__is_base=True).first()
        if currency:
            return self.get_balance(currency)
        return None

    def get_balance(self, currency):
        """Will create balance if necessary."""
        balance, created = self.balances.get_or_create(currency=currency)
        return balance

    @db_transaction.atomic
    def increase_balance(self, amount, currency, type):
        """Adds amount to balance and creates transaction."""
        if amount < 0:
            raise ValueError("Amount can't be less than 0 when adding balance")

        balance = self.active_balance
        converted_amount = Converter.convert(
            amount, currency.code, balance.currency.code
        )

        self.transactions.create(
            currency=balance.currency,
            amount=converted_amount,
            purpose=Transaction.BALANCE_INCREASE,
            type=type,
            extra={
                "is_converted": currency.code != balance.currency.code,
                "converted_from": currency.code,
                "real_amount": amount,
            },
        )

        balance = self.get_balance(currency)
        balance.amount = F("amount") + amount
        balance.save(update_fields=["amount"])

        return balance

    @db_transaction.atomic
    def decrease_balance(self, amount, currency):
        """Decreases balance and creates transaction."""
        if amount < 0:
            raise ValueError("Amount can't be less than 0 when decreasing balance")

        balance = self.active_balance
        converted_amount = Converter.convert(
            amount, currency.code, balance.currency.code
        )

        self.transactions.create(
            currency=balance.currency,
            amount=converted_amount,
            purpose=Transaction.BALANCE_DECREASE,
            type=Transaction.BALANCE,
            extra={
                "is_converted": currency.code != balance.currency.code,
                "converted_from": currency.code,
                "real_amount": amount,
            },
        )

        balance = self.get_balance(currency)
        balance.amount = F("amount") - amount
        balance.save(update_fields=["amount"])

        return balance

    def _check_currency(self, currency):
        if currency.code not in settings.DEFAULT_BALANCES:
            raise ValueError("No such balance supported for customers")
