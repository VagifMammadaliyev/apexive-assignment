import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from fulfillment.models import TrackingStatus


class Command(BaseCommand):
    help = "Import tracking statuses from provided CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)

    def normalize_boolean(self, value):
        value = value.upper()

        if value == "FALSE":
            return False
        elif value == "TRUE":
            return True

        return None

    @transaction.atomic
    def handle(self, *args, **options):
        with open(options["csv_file"], "r") as csv_file:
            reader = csv.DictReader(
                csv_file,
                fieldnames=[
                    "pl_number",
                    "problem_code",
                    "tracking_code",
                    "tracking_condition_code",
                    "tracking_code_description",
                    "mandatory_comment",
                    "final_status",
                    "delivery_status",
                    "tracking_condition_code_description",
                    "problem_code_description",
                    "tracking_code_explanation",
                ],
            )

            skipped_header = False
            counter_created = 0
            counter_updated = 0

            for row in reader:
                if not skipped_header:
                    skipped_header = True
                    continue

                # Normalize boolean values represented in strings
                row["final_status"] = self.normalize_boolean(row["final_status"])
                row["delivery_status"] = self.normalize_boolean(row["delivery_status"])

                # Convert empty string to None values
                for key in row.keys():
                    if row[key] == "":
                        row[key] = None

                # Usually this command is run in a single thread
                # so race condition does not occur
                existing_tracking_status = TrackingStatus.objects.filter(
                    pl_number=row["pl_number"],
                    problem_code=row["problem_code"],
                    tracking_code=row["tracking_code"],
                ).first()

                if existing_tracking_status:
                    TrackingStatus.objects.filter(
                        id=existing_tracking_status.id
                    ).update(**row)
                    counter_updated += 1
                else:
                    TrackingStatus.objects.create(**row)
                    counter_created += 1

            self.stdout.write(
                self.style.SUCCESS(
                    "Created %d, updated %s tracking statuses"
                    % (counter_created, counter_updated)
                )
            )
