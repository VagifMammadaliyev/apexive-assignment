from django.db import models
from django.contrib.postgres.fields import JSONField


class Balance(models.Model):
    user = models.ForeignKey(
        "customer.User",
        on_delete=models.CASCADE,
        related_name="balances",
        related_query_name="balance",
    )
    currency = models.ForeignKey(
        "core.Currency", on_delete=models.PROTECT, related_name="+"
    )
    amount = models.DecimalField(max_digits=9, decimal_places=2, default=0)

    update_at = models.DateTimeField(auto_now=True)
    extra = models.JSONField(default=dict, null=True, blank=True)

    class Meta:
        db_table = "balance"
        unique_together = ["user", "currency"]

    def __str__(self):
        return "%s %s [%s]" % (
            self.amount,
            self.currency.code,
            self.user.full_phone_number,
        )
