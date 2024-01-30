import csv

from django.core.management import BaseCommand, CommandError

from fulfillment.models import ParentProductCategory, ProductCategory


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--skip-insert", action="store_true", default=False)
        parser.add_argument("--remove-parents", action="store_true", default=False)

    def handle(self, *args, **options):
        if options["remove_parents"]:
            self.stdout.write(self.style.WARNING("Removing parent categories"))
            ParentProductCategory.objects.all().delete()

        self.stdout.write(f"Deactivating old categories")
        count = ProductCategory.objects.filter(needs_description=False).update(
            is_active=False
        )
        self.stdout.write(self.style.SUCCESS(f"Deactivated {count} categories"))

        if not options["skip_insert"] and not ProductCategory.objects.count() > 300:
            categories = []
            with open("misc/new_categories.csv") as categories_file:
                reader = csv.DictReader(
                    categories_file, delimiter=";", fieldnames=["en", "ru", "az"]
                )
                for row in reader:
                    en = row.get("en")
                    ru = row.get("ru")
                    az = row.get("az")
                    # we need only az to insert
                    if az:
                        categories.append(
                            ProductCategory(
                                name_az=az, name_ru=ru, name_en=en, is_active=True
                            )
                        )

            if not categories:
                raise CommandError("Cannot find any categories in a file")
            self.stdout.write(
                self.style.SUCCESS(f"Saving {len(categories)} categories...")
            )
            ProductCategory.objects.bulk_create(categories)
            self.stdout.write(self.style.SUCCESS("Done"))
