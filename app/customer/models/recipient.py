from django.db import models
from django.conf import settings

from ontime import messages as msg


class RecipientMixin:
    def get_phone_number_for_customs(self):
        return self.phone_number.strip("+")


class Recipient(models.Model, RecipientMixin):
    MALE = "M"
    FEMALE = "F"

    GENDERS = ((MALE, msg.MALE_SEX), (FEMALE, msg.FEMALE_SEX))

    title = models.CharField(max_length=255)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recipients",
        related_query_name="recipient",
    )

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=1, choices=GENDERS)

    full_name = models.CharField(max_length=510)  # ...saved automatically
    phone_number = models.CharField(max_length=20)

    id_pin = models.CharField(max_length=10, db_index=True)

    city = models.ForeignKey("core.City", on_delete=models.PROTECT, related_name="+")
    address = models.TextField()
    address_extra = models.TextField(null=True, blank=True)

    region = models.ForeignKey(
        "fulfillment.CourierRegion",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "customer_recipient"

    def __str__(self):
        return "Recipient [%s]" % (self.full_name)

    def save(self, *args, **kwargs):
        self.first_name = self.first_name.upper()
        self.last_name = self.last_name.upper()

        self.full_name = "%s %s" % (self.first_name.strip(), self.last_name.strip())
        self.full_name = self.full_name.strip()

        if self.region_id and self.region.area_id and self.region.area.city_id:
            self.city_id = self.region.area.city_id

        return super().save(*args, **kwargs)

    def freeze(self, commit=True):
        frozen_recipient = FrozenRecipient(
            user_id=self.user_id,
            first_name=self.first_name,
            last_name=self.last_name,
            full_name=self.full_name,
            phone_number=self.phone_number,
            id_pin=self.id_pin,
            gender=self.gender,
            real_recipient=self,
            address=self.address,
            address_extra=self.address_extra,
        )

        if commit:
            frozen_recipient.save()

        return frozen_recipient

    @property
    def is_frozen(self):
        return False


class FrozenRecipient(models.Model, RecipientMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="frozen_recipients",
        related_query_name="frozen_recipient",
    )
    real_recipient = models.ForeignKey(
        "customer.Recipient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="frozen_copies",
        related_query_name="frozen_copy",
    )

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    gender = models.CharField(max_length=1, choices=Recipient.GENDERS)

    full_name = models.CharField(max_length=510)
    phone_number = models.CharField(max_length=20)

    address = models.TextField()
    address_extra = models.TextField(null=True, blank=True)

    id_pin = models.CharField(max_length=10, db_index=True)

    class Meta:
        db_table = "frozen_customer_recipient"

    def __str__(self):
        return "Frozen Recipient [%s]" % (self.full_name)

    @property
    def is_frozen(self):
        return True

    def freeze(self):
        return self
