from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from customer.tasks import fetch_user_data_from_government_resource


class Command(BaseCommand):
    help = "Fix billed recipients for legacy users."

    def add_arguments(self, parser):
        parser.add_argument("--fetch-gov-data", action="store_true")

    def handle(self, *args, **options):
        User = get_user_model()

        fetch_gov_data = options.get("fetch_gov_data", False)

        counter = 0

        for user in User.objects.filter(billed_recipient__isnull=True):
            print(f"Fixing user -> {user}")

            first_recipient = user.recipients.order_by("id").first()

            if first_recipient:
                print(f"\tFound first recipient for this user -> {first_recipient}")
                user.billed_recipient = first_recipient
                user.save(update_fields=["billed_recipient"])
                counter += 1

                if fetch_gov_data:
                    print(f"\tFetching gov data for pin -> {first_recipient.id_pin}")
                    fetch_user_data_from_government_resource.delay(first_recipient.id)
            else:
                print(f"\tCannot find recipient for this user")

            print("-" * 50)

        self.stdout.write(
            self.style.SUCCESS(f"Fixed billed recipients for {counter} users")
        )
