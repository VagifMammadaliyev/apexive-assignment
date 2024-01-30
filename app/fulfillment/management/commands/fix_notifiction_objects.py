from django.core.management import CommandError, BaseCommand

from fulfillment.models import Notification, NotificationEvent as EVENTS


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry", action="store_true", default=False, help="Run in a dry mode"
        )

    def handle(self, *args, **options):
        dry = options["dry"]
        reasons = [EVENTS.ON_USER_BALANCE_TOPUP]
        notifications = Notification.objects.filter(event__reason__in=reasons)
        print(f"Found {notifications.count()} for event types {reasons}")
        ids = list(notifications.values_list("id", flat=True))[:5]
        print(f"Here are some IDS to check: {ids}")
        if not dry:
            print("Fixing them...")
            updated_count = notifications.update(
                type=Notification.OTHER,
                related_object_identifier=None,
                object_id=None,
                object_type=None,
            )
            print(f"Fixed {updated_count} notifications!")
        self.stdout.write(self.style.SUCCESS("Completed"))
