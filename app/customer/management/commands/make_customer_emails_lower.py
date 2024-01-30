from django.core.management import CommandError, BaseCommand

from customer.models import User


class Command(BaseCommand):
    def handle(self, *args, **options):
        counter = 0
        for user in User.objects.all():
            counter += 1
            if not counter % 100:
                self.stdout.write(f"Customers fixed: {counter}")
            user.save(update_fields=["email"])
