from django.core.management import CommandError, BaseCommand

from customer.models import Recipient, FrozenRecipient


class Command(BaseCommand):
    def make_name_fields_upper(self, recipient: FrozenRecipient):
        recipient.first_name = recipient.first_name.upper()
        recipient.last_name = recipient.last_name.upper()
        recipient.full_name = recipient.full_name.upper()
        recipient.save(update_fields=["first_name", "last_name", "full_name"])

    def handle(self, *args, **kwargs):
        for r in Recipient.objects.all():
            r.save()  # this is enough for Recipient model
            print(r)

        for r in FrozenRecipient.objects.all():
            self.make_name_fields_upper(r)
            print(r)

        self.stdout.write(self.style.SUCCESS("Done!"))
