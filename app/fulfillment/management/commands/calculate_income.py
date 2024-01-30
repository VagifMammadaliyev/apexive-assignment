from decimal import Decimal

from django.core.management import CommandError, BaseCommand

from core.converter import Converter
from fulfillment.models import Transaction


class Command(BaseCommand):
    def get_transactions(self):
        return Transaction.objects.filter(
            type=Transaction.CARD, completed=True, is_deleted=False
        )

    def handle(self, *args, **options):
        transactions = self.get_transactions()
        total = Decimal("0")
        for transaction in transactions:
            print(transaction.invoice_number, transaction)
            try:
                total += transaction.get_payment_service_transaction_amount()
            except Exception:
                total += Converter.convert(
                    transaction.amount
                    - Converter.convert(
                        transaction.from_balance_amount,
                        transaction.from_balance_currency.code,
                        transaction.currency.code,
                    ),
                    transaction.currency.code,
                    "USD",
                )

        print("Calculated total amount", total)
