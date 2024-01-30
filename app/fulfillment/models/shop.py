from django.db import models


class Shop(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=500)
    logo = models.ImageField(upload_to="shop-logos/%Y/%m/%d")
    url = models.URLField(max_length=600, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    display_order = models.IntegerField(default=0)

    class Meta:
        db_table = "shop"
        ordering = ["display_order"]

    def __str__(self):
        return self.name
