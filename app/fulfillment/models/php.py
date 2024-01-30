from django.db import models
from django.conf import settings


class ModeratedModel(models.Model):
    created_at = models.DateTimeField(null=True, blank=True, db_index=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        abstract = True


class Airway(ModeratedModel):
    name = models.CharField(max_length=255)
    extra = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "padmin_airway"

    def __str__(self):
        return self.name


class ExpenseType(ModeratedModel):
    name = models.CharField(max_length=255)
    object_type = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    extra = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "padmin_expense_type"

    def __str__(self):
        return self.name


class MultiExpense(ModeratedModel):
    extra = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "padmin_multi_expense"

    def __str__(self):
        return "ID %s" % self.pk


class ExpenseItem(ModeratedModel):
    object_id = models.IntegerField(db_index=True, null=True, blank=True)
    object_type = models.CharField(db_index=True, max_length=255, blank=True, null=True)
    multi_expense = models.ForeignKey(
        "fulfillment.MultiExpense",
        on_delete=models.CASCADE,
    )
    extra = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "padmin_expense_item"

    def __str__(self):
        return "%s - %s" % (self.object_type, self.object_id)


class Cashbox(ModeratedModel):
    name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    currency = models.ForeignKey(
        "core.Currency", related_name="+", on_delete=models.DO_NOTHING
    )
    extra = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "padmin_cashbox"

    def __str__(self):
        return self.name


class Expense(ModeratedModel):
    object_id = models.IntegerField(null=True, blank=True, db_index=True)
    object_type = models.CharField(null=True, blank=True, db_index=True, max_length=255)
    description = models.TextField(null=True, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.ForeignKey(
        "core.Currency", related_name="+", on_delete=models.DO_NOTHING
    )
    cashbox = models.ForeignKey(
        Cashbox,
        related_name="expenses",
        related_query_name="expense",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    expense_type = models.ForeignKey(
        ExpenseType, null=True, blank=True, on_delete=models.SET_NULL
    )
    multi_expense_type = models.CharField(null=True, blank=True, max_length=255)
    extra = models.JSONField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    related_object_identifier = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )

    class Meta:
        db_table = "padmin_expense"

    def __str__(self):
        return "Expense %s%s" % (self.amount, self.currency.symbol)
