"""
Newsletter subscriber related models here.
"""
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Subscriber(models.Model):
    user = models.OneToOneField(
        "customer.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    email = models.EmailField(unique=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "newsletter_subscriber"

    def __str__(self):
        return "Subscriber [%s]" % (self.email)
