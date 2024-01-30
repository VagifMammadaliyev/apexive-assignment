from django.core.management import BaseCommand, CommandError
from django.db import transaction

from fulfillment.models import Shipment


class Command(BaseCommand):
    def handle(self, *args, **options):
        with transaction.atomic():
            counter = 0

            for shipment in Shipment.objects.filter(
                declared_price__isnull=False, declared_price__gt=0
            ):
                shipment.declared_items_title = shipment.generate_declared_items_title()
                print(
                    f"Shipment -> Will save declared items title == {shipment.declared_items_title}"
                )
                shipment.save(update_fields=["declared_items_title"])
                counter += 1

        return self.stdout.write(
            self.style.SUCCESS(f"Fixed description for {counter} shipments")
        )
