from django.core.management import CommandError, BaseCommand
from django.db.models import F
from django.db import transaction as dbt

from fulfillment.models import Transaction


class Command(BaseCommand):
    @dbt.atomic
    def handle(self, *args, **options):
        cb_p = Transaction.CASHBACK
        bad_cashbacks = Transaction.objects.filter(completed=False, purpose=cb_p)
        count = 0
        completed_count = 0
        for bad_cashback in bad_cashbacks:
            self.stdout.write(
                self.style.NOTICE(
                    f"Checking {bad_cashback.invoice_number}".center(60, "=")
                )
            )
            cb_to: Transaction = bad_cashback.cashback_to
            if cb_to.completed:
                self.stderr.write(
                    self.style.ERROR(
                        "WTF? %s is completed but cashback not!" % cb_to.invoice_number
                    )
                )
            if cb_to:
                rel_obj = cb_to.related_object
                if rel_obj.is_paid:
                    print("This item is paid: %s" % rel_obj)
                    print(
                        "But its related payment is uncomplete: %s"
                        % cb_to.invoice_number
                    )

                if cb_to.is_deleted:
                    count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            "This is because cashback was tied to deleted transaction"
                        )
                    )

                    nice_cb_to = rel_obj.transactions.filter(
                        purpose=Transaction.SHIPMENT_PAYMENT,
                        is_deleted=False,
                        completed=True,
                    ).first()
                    self.stdout.write(
                        "But it must be tied to this one %s" % nice_cb_to.invoice_number
                    )
                    print("Tying...")
                    bad_cashback.cashback_to = nice_cb_to
                    bad_cashback.extra["old_cb_to_id"] = cb_to.id
                    bad_cashback.extra["bad_cb_completed"] = rel_obj.is_paid
                    if rel_obj.is_paid:
                        completed_count += 1
                        print("Completing cashback, because related object is paid")
                        bad_cashback.completed = True
                        user = bad_cashback.user
                        balance = user.active_balance
                        old = balance.amount
                        print("User's old balance is %s" % old)
                        balance.amount = F("amount") + bad_cashback.amount
                        balance.save()
                        balance.refresh_from_db()
                        new = balance.amount
                        print("User's new balance is %s" % new)
                        if new <= old:
                            raise Command("balance is not increased")

                    bad_cashback.save(
                        update_fields=["cashback_to", "completed", "extra"]
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING("Some bad things is going on there!")
                    )

            print()
        print("Problems count = %s" % count)
        print("Completed count = %s" % completed_count)
