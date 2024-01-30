from django.core.management import CommandError, BaseCommand

from fulfillment.tasks import save_image_link_for_orders


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--async", action="store_true", default=False)

    def handle(self, *args, **options):
        async_ = options.get("async", False)

        if async_:
            save_image_link_for_orders.delay(all_orders=True)
            self.stdout.write(
                self.style.SUCCESS("Scheduled fetching and saving images for orders")
            )
        else:
            save_image_link_for_orders(all_orders=True)
            self.stdout.write(self.style.SUCCESS("Saved images for orders with links"))
