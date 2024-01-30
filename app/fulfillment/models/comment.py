from django.db import models
from django.utils.translation import ugettext as _

from ontime import messages as msg


class Comment(models.Model):
    author = models.ForeignKey(
        "customer.User", on_delete=models.CASCADE, null=True, blank=True
    )
    order = models.ForeignKey(
        "fulfillment.Order",
        on_delete=models.CASCADE,
        related_name="comments",
        related_query_name="comment",
    )

    body = models.TextField(default=str)
    is_automatic_message = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comment"

    def __str__(self):
        return "%s [%s]" % (self.body[:100], self.title)

    @property
    def title(self):
        if self.is_automatic_message:
            return msg.SYSTEM_MESSAGE
        elif self.author:
            return self.author.full_name
        return None
