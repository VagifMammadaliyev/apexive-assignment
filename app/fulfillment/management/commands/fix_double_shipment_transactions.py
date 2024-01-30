from django.core.management import BaseCommand, CommandError
from django.db import transaction as dbt
from django.db.models import Count, OuterRef, Subquery

from fulfillment.models import Shipment, Transaction


class Command(BaseCommand):
    @dbt.atomic
    def handle(self, *args, **kwargs):
        related_trans = Transaction.objects.filter(
            is_deleted=False,
            deleted_at__isnull=True,
            related_object_identifier=OuterRef("number"),
            purpose=Transaction.SHIPMENT_PAYMENT,
        ).values("id")
        shipment_with_two_trans = Shipment.objects.annotate(
            related_trans_count=Subquery(
                related_trans.values("related_object_identifier")
                .annotate(count=Count("pk"))
                .values("count")
            )
        ).filter(related_trans_count__gte=2)
        print(shipment_with_two_trans.count())
        print(shipment_with_two_trans)
        input("Continue?...")

        for shipment in shipment_with_two_trans:
            print(shipment)
            ts = shipment.transactions.filter(
                purpose=Transaction.SHIPMENT_PAYMENT,
                is_deleted=False,
                deleted_at__isnull=True,
            )
            nts = shipment.transactions.filter(
                purpose=Transaction.SHIPMENT_PAYMENT,
                is_deleted=False,
                deleted_at__isnull=True,
                completed=False,
            )
            cts = shipment.transactions.filter(
                purpose=Transaction.SHIPMENT_PAYMENT,
                is_deleted=False,
                deleted_at__isnull=True,
                completed=True,
            )

            if cts.exists():
                for nt in nts:
                    print("deleting %s" % nt)
                    nt.delete()
            else:
                if nts.count() >= 2:
                    for t in nts[1:]:
                        print("deleting %s" % t)
                        t.delete()
