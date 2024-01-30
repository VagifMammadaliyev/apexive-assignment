from django.db import models
from django.conf import settings


class ContactUsMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    full_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=20)
    text = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "contact_us_message"

    def __str__(self):
        return "Contact us message from %s [%s]" % (self.full_name, self.phone_number)
