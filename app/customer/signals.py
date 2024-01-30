from django.dispatch import receiver
from django_rest_resetpassword.signals import reset_password_token_created

from customer.tasks import send_reset_password_email


@receiver(reset_password_token_created)
def password_reset_token_created(
    sender, instance, reset_password_token, *args, **kwargs
):
    from domain.conf import Configuration

    send_reset_password_email.delay(
        reset_password_token.user.id, reset_password_token.key
    )
