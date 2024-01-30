from django.db import models
from django.conf import settings


class UserCountryLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="country_logs",
        related_query_name="country_log",
    )
    country = models.ForeignKey(
        "core.Country", on_delete=models.CASCADE, related_name="+"
    )
    updated_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "user_country_log"
        unique_together = ("user", "country")

    def __str__(self):
        return "%s - %s [%s]" % (self.user, self.country, self.updated_at)
