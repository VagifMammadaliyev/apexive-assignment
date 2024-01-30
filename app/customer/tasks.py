from __future__ import absolute_import, unicode_literals

from celery import shared_task
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import send_mail

from poctgoyercin.utils import send_sms_to_customer
from domain.conf import Configuration


@shared_task
def send_sms_with_random_code(user_id, activation_code):
    if not Configuration().are_notifications_enabled:
        print("Not sending activation code: %s" % (activation_code))
        return
    User = get_user_model()
    send_sms_to_customer(User.objects.get(id=user_id), activation_code)


# TODO: Remove this task, now activation email is sent using notification event
@shared_task
def send_verification_email(user_id, uid, token):
    """
    Sends a mail to user email address for verifying validity of
    provided email address
    """
    User = get_user_model()
    user = User.objects.get(id=user_id)

    conf = Configuration()
    link = conf.get_activation_email_link(uid, token)
    text = "Activate your email: %s" % (link)
    send_mail(
        "Verify your email address",
        text,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


@shared_task
def send_reset_password_email(user_id, reset_token):
    User = get_user_model()
    user = User.objects.get(id=user_id)

    conf = Configuration()
    link = conf.get_reset_password_link(reset_token)
    send_mail(
        "Reset your password",
        "To reset your password click here: %s" % link,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


@shared_task
def fetch_user_data_from_government_resource(recipient_id):
    from domain.services import fetch_citizen_data

    fetch_citizen_data(recipient_id, save_to_user=True)
