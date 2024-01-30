from django.core.management import CommandError, BaseCommand

from fulfillment.models import Order, Shipment, Package
from fulfillment.tasks import save_ordered_products_in_shipment


class Command(BaseCommand):
    def handle(self, *args, **options):
        save_ordered_products_in_shipment.delay(
            list(
                Shipment.objects.filter(confirmed_properties=True).values_list(
                    "id", flat=True
                )
            )
        )
        self.stdout.write(self.style.SUCCESS("Scheduled migrating orders..."))
