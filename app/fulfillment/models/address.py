from django.db import models


class AddressField(models.Model):
    address = models.ForeignKey(
        "fulfillment.Address",
        on_delete=models.CASCADE,
        related_name="fields",
        related_query_name="field",
    )
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=300, default=str, blank=True)
    display_order = models.IntegerField(default=0)
    append_user_full_name = models.BooleanField(default=False)
    append_client_code = models.BooleanField(default=False)

    class Meta:
        db_table = "address_field"
        ordering = ["display_order"]

    def __str__(self):
        return "%s -> %s" % (self.name, self.value)


class Address(models.Model):
    warehouse = models.OneToOneField(
        "fulfillment.Warehouse",
        on_delete=models.CASCADE,
        related_name="foreign_address",
        null=True,
        blank=True,
    )
    country = models.ForeignKey(
        "core.Country",
        on_delete=models.CASCADE,
        related_name="addresses",
        related_query_name="address",
    )

    class Meta:
        db_table = "address"
        verbose_name_plural = "Addresses"

    def __str__(self):
        return "Address [%s]" % (self.country.name)
