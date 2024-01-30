from django.db import models


# class Address(models.Model):
#     user = models.ForeignKey(
#         "customer.User",
#         on_delete=models.CASCADE,
#         related_name="addresses",
#         related_query_name="address",
#     )
#     country = models.ForeignKey(
#         "core.Country",
#         on_delete=models.PROTECT,
#         related_name="user_addresses",
#         related_query_name="user_address",
#         limit_choices_to={"is_base": True},
#     )
#     nearby_warehouse = models.ForeignKey(
#         "fulfillment.Warehouse",
#         on_delete=models.PROTECT,
#         related_name="user_addresses",
#         related_query_name="user_address",
#     )
#     title = models.CharField(max_length=50)

#     recipient_id_serial_number = models.CharField(max_length=11)
#     recipient_id_pin = models.CharField(max_length=7)

#     region = models.CharField(max_length=100)
#     district = models.CharField(max_length=100, null=True, blank=True)
#     city = models.CharField(max_length=100)
#     zip_code = models.CharField(max_length=15)
#     street_name = models.CharField(max_length=100)
#     house_number = models.CharField(max_length=10)
#     unit_number = models.CharField(max_length=15)
#     recipient_first_name = models.CharField(max_length=30)
#     recipient_last_name = models.CharField(max_length=30)
#     recipient_phone_number = models.CharField(max_length=15)

#     is_deleted = models.BooleanField(default=False)

#     class Meta:
#         db_table = "user_address"
#         verbose_name_plural = "Addresses"

#     def __str__(self):
#         return "%s [%s]" % (self.title, self.user)
