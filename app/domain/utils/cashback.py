from typing import Optional, Dict, Any, List, Union
from decimal import Decimal

from django.utils import timezone

from core.models import Currency
from fulfillment.models import Transaction, CourierOrder, Shipment, Order


class Cashback(object):
    """
    Class that is used to generate cashback transactions
    at some point in the future. Can store cashback amount in
    concrete amount (with currency) or in pecentages. If in percentages,
    then concrete amount is calculated when base amount is ready.

    Note: Base amount is the amount of "cashback_to" transaction that
          can be used to calculate concrete cashback amount.
          See `fulfillment.models.Transacion.cashbackable_amount`.

    Typically cashback percentage will always be equal to that defined in
    application configuration. See `domain.conf.Configuration`.

    Note: Cashback is not saved into the database like Discount model.
          This is due to how cashbacks was designed the first time.
          This class actually means nothing, the real cashback to user's
          balance is done using related cashback transactions of transaction
          being paid by user.
    """

    def __init__(
        self,
        amount: Optional[Decimal] = None,
        currency_code: Optional[str] = None,
        percentage: Optional[Decimal] = None,
    ):
        """
        Using currency_code as a string to reduce database hits.
        """
        self.amount = amount
        self.currency_code = currency_code
        self.percentage = percentage
        self.real_transaction: Optional[Transaction] = None

    @property
    def currency(self) -> Currency:
        """Get the currency from database using self.currency_code."""
        try:
            return self.cached_currency
        except AttributeError:
            self.cached_currency = Currency.objects.get(code=self.currency_code)
            return self.cached_currency

    def get_fresh_currency(self) -> Currency:
        """Gets fresh currency, ignoring cached one."""
        try:
            del self.cached_currency
        except AttributeError:
            pass

        return self.currency

    def __eq__(self, other: "Cashback"):
        if self.amount and self.currency_code and other.amount and other.currency_code:
            return (
                self.amount == other.amount
                and self.currency_code == other.currency_code
            )
        elif self.percentage and other.percentage:
            return self.percentage == other.percentage
        return False

    @classmethod
    def build_from_extra(
        cls,
        instance: Union[Shipment, Order, CourierOrder],
        key: Optional[str] = "cashback_data",
        mark_used: Optional[bool] = False,
    ) -> List["Cashback"]:
        """
        Build from JSON data saved in some model's extra.
        Returns build cashbacks in the same order they were saved.
        """
        instance_extra = getattr(
            instance, "extra", {}
        )  # more tolerant way of getting extra field
        dumped_cashbacks: List[Dict[Any, Any]] = instance.extra.get(key, [])
        built_cashbacks = []

        for i in range(len(dumped_cashbacks)):
            dumped_cashback = dumped_cashbacks[i]

            if dumped_cashback.get("used", False):
                continue

            amount = dumped_cashback.get("amount", None)
            currency_code = dumped_cashback.get("currency_code", None)
            percentage = dumped_cashback.get("percentage", None)

            if amount and currency_code:
                amount = round(Decimal(str(amount)), 2)
                built_cashbacks.append(cls(amount=amount, currency_code=currency_code))
            elif percentage:
                percentage = round(Decimal(str(percentage)), 2)
                built_cashbacks.append(cls(percentage=percentage))

            if mark_used:
                dumped_cashback["used"] = True

        if mark_used:
            instance.extra[key] = dumped_cashbacks
            instance.__class__.objects.filter(id=instance.id).update(
                extra=instance.extra
            )

        return built_cashbacks

    def dump(self) -> Dict[str, str]:
        """Return JSON serializable representation of cashback."""
        return {
            "amount": str(self.amount) if self.amount else None,
            "currency_code": self.currency_code if self.currency_code else None,
            "percentage": str(self.percentage) if self.percentage else None,
        }

    def create_transaction(self, cashback_to: Transaction) -> Transaction:
        """
        Creates cashback transaction. Also takes care of percentage cashbacks.
        """

        if not self.amount:
            base_amount: Decimal = cashback_to.cashbackable_amount
            base_amount_currency_code: str = cashback_to.discounted_amount_currency.code
            self.amount = base_amount * (self.percentage / Decimal("100"))
            self.currency_code = base_amount_currency_code

        self.real_transaction = Transaction.objects.create(
            user_id=cashback_to.user_id,
            amount=self.amount,
            currency=self.currency,
            purpose=Transaction.CASHBACK,
            type=Transaction.BALANCE,
            completed=False,
            cashback_to=cashback_to,
            extra={"invite_friend_cashback": True},
        )
        return self.real_transaction
