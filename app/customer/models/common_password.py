import secrets
import string
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.conf import settings
from passlib.context import CryptContext

from customer.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_password(length=64):
    allowed_chars = string.ascii_letters + string.digits + string.punctuation[:4]
    new_password = [secrets.choice(allowed_chars) for _ in range(length)]
    return "".join(new_password)


def check_password_for_user(user, raw_password):
    from domain.conf import Configuration

    if not Configuration()._conf.common_password_is_enabled:
        return False

    password = (
        CommonPassword.objects.filter(
            expires_on__gte=timezone.now(),
        )
        .order_by("-created_at")
        .first()
    )

    return bool(password) and password.check_password(raw_password, user)


class CommonPassword(models.Model):
    """
    Passwords that can be used to log in to any user's account
    """

    expires_on = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    hashed_password = models.CharField(max_length=1000)
    extra = models.JSONField(default=dict)

    class Meta:
        db_table = "common_password"

    def __init__(self, *args, **kwargs):
        from domain.conf import Configuration

        super().__init__(*args, **kwargs)

        if not self.expires_on:
            self.expires_on = (
                timedelta(minutes=Configuration()._conf.common_password_expire_minutes)
                + timezone.now()
            )

    def __str__(self):
        return f"Generated by [{self.generated_by}], expires on {self.expires_on.strftime('%m/%d/%Y')}"

    def set_password(self, password=None):
        if not password:
            password = generate_password()

        self.hashed_password = pwd_context.hash(password)

    def check_password(self, password: str, user_id: int):
        users = self.extra.get("affected_users", [])
        users.append(user_id)
        self.extra["affected_users"] = users
        self.save(update_fields=["extra"])
        print(password)
        return pwd_context.verify(password, self.hashed_password)
