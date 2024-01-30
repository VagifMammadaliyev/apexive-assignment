from django.core.management import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, F
from django.db import transaction as dbt


from core.converter import Converter
from domain.services import update_or_create_transaction_for_shipment
from fulfillment.models import Shipment, Transaction


class Command(BaseCommand):
    @dbt.atomic
    def handle(self, *args, **options):
        transactions = Transaction.objects.filter(
            related_object_identifier=OuterRef("number")
        )
        paid_shipments_with_no_transaction = Shipment.objects.annotate(
            payment_exists=Exists(transactions)
        ).filter(is_paid=True, payment_exists=False)
        _count = paid_shipments_with_no_transaction.count()
        print(f"There are {_count} shipments", end=" ")
        print("which are paid but related transaction does not exists!")
        if _count:
            latest = paid_shipments_with_no_transaction.latest("created_at")
            oldest = paid_shipments_with_no_transaction.earliest("created_at")
            other = (
                paid_shipments_with_no_transaction.exclude(
                    number__in=[latest.number, oldest.number]
                )
                .order_by("-created_at")
                .values_list("number", flat=True)[:3]
            )
            print(
                "Examples from newest to oldest: %s"
                % ([latest.number] + list(other) + [oldest.number])
            )

            print("\nFixings this problem... May take a while")
            for shipment in paid_shipments_with_no_transaction:
                print("\tFixing for %s" % self.style.NOTICE(shipment.number))
                if not (shipment.total_price and shipment.total_price_currency_id):
                    print(
                        "\tTransaction cannot be created now because total price missing"
                    )
                    print("\tTrying to calculate total price and fix this issue")
                    if shipment.fixed_total_weight:
                        shipment._must_recalculate = True
                        shipment.save()
                        self.stdout.write(self.style.SUCCESS("Done!"))
                    else:
                        print(
                            self.style.WARNING(
                                "\tThis shipment does not have weight too. Skipping"
                            )
                        )
                else:
                    update_or_create_transaction_for_shipment(shipment)
                    self.stdout.write(self.style.SUCCESS("Done!"))

                print()

        shipments_with_total_price_but_different_payment = (
            Shipment.objects.filter(
                total_price__gt=0,
                total_price_currency_id__isnull=False,
            )
            .order_by("-created_at")
            .select_related("total_price_currency")
        )
        _count = 0
        _shipments = []
        for shipment in shipments_with_total_price_but_different_payment:
            related_trans = (
                shipment.transactions.filter(
                    is_deleted=False,
                    purpose=Transaction.SHIPMENT_PAYMENT,
                )
                .select_related("currency")
                .first()
            )
            if related_trans:
                if (
                    Converter.convert(
                        related_trans.amount,
                        related_trans.currency.code,
                        shipment.total_price_currency.code,
                    )
                    != shipment.total_price
                ):
                    _count += 1
                    _shipments.append(shipment)

        print(f"There are {_count} shipments", end=" ")
        print("which have different amount than their related payment!")
        examples = _shipments[:1] + _shipments[1:5] + _shipments[-1:]
        print("Examples from newest to oders %s" % examples)

        print("Fixing them")
        for shipment in _shipments:
            print("\tFixing for %s" % self.style.NOTICE(shipment.number))
            update_or_create_transaction_for_shipment(shipment)
            print(self.style.SUCCESS("\tDone!"))
