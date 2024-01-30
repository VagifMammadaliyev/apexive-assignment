from decimal import Decimal
from core.models import Currency


class Converter:
    @classmethod
    def convert(cls, value, from_, to, rounding=2, ignore_missing_currency=False):
        """
        Converts `value` from `from_` currency to `to` currency.

        You can pass value as int, float or Decimal instance,
        in any case precious calculations are guaranteed.

        Params:
            - `from_` and `to` are strings represeting currency codes.
            - `value` is amount of money with currency `from_` that
                needs to be converted to `to`.

        Parameters are currency codes instead of currency instances
        because it is more convenient to do following:
            converted = Converter.convert(100, 'USD', 'AZN')
        Than:
            azn = Currency.objects.get(code='AZN')
            usd = Currency.objects.get(code='USD')
            converted = Converter.convert(100, azn, usd)

        Note: if you want to pass `value` as string then
        convert it to int, float, or Decimal manually.
        Although usually you will not pass value as string.
        """
        value = round(Decimal(value), 2)

        try:
            currency_from = Currency.objects.get(code=from_)
            currency_to = Currency.objects.get(code=to)
            base_currency = Currency.objects.filter(rate=1).first()
        except Currency.DoesNotExist:
            if ignore_missing_currency:
                return None
            raise

        if from_ == to:
            result = value
        elif currency_to == base_currency:
            result = value * currency_from.rate
        elif currency_from == base_currency:
            result = value / currency_to.rate
        else:
            result = cls.convert(
                value * currency_from.rate, base_currency.code, currency_to.code
            )

        return round(result, rounding)
