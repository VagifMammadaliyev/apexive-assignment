from django.db import models


class Warehouse(models.Model):
    title = models.CharField(max_length=100)
    codename = models.CharField(max_length=100)

    country = models.ForeignKey(
        "core.Country",
        on_delete=models.CASCADE,
        related_name="warehouses",
        related_query_name="warehouse",
    )
    city = models.ForeignKey(
        "core.City", on_delete=models.SET_NULL, null=True, blank=True
    )
    airport_city = models.ForeignKey(
        "core.City", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    address = models.CharField(max_length=500)
    is_consolidation_enabled = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    is_universal = models.BooleanField(default=False)
    does_consider_volume = models.BooleanField(default=False)
    does_serve_dangerous_packages = models.BooleanField(default=False)

    last_queue_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "warehouse"

    def __str__(self):
        return "%s [%s]" % (self.title, self.country)

    def save(self, *args, **kwargs):
        if self.city_id:
            self.country_id = self.city.country_id

        return super().save(*args, **kwargs)
