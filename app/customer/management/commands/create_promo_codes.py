from django.core.management import BaseCommand

from customer.models import User
from domain.services import generate_promo_code


class Command(BaseCommand):
    def handle(self, *args, **options):
        count = 0

        for user in User.objects.all():
            count += 1
            print(f"Generating for -> {user}")
            generate_promo_code(user)

        self.stdout.write(f"Generated for {count} users")
