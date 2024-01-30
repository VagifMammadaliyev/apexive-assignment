from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from ontime import messages as msg
from core.models import MobileOperator

User = get_user_model()


def validate_phone_number(number, validate_user=True):
    old_user = None
    number = number.strip()

    if validate_user:
        try:
            old_user = User.objects.get(full_phone_number=number)

            if old_user.is_active:
                raise serializers.ValidationError(msg.NUMBER_ALREADY_IN_USE)

        except User.DoesNotExist:
            pass

    if not number.startswith("+"):
        raise serializers.ValidationError(msg.FULL_PHONE_NUMBER_MUST_BE_PROVIDED)

    phone_operators = MobileOperator.objects.select_related("country")
    nice_phone_prefix = False

    for phone_operator in phone_operators:
        if number.startswith(phone_operator.full_prefix):
            nice_phone_prefix = True
            break

    if not nice_phone_prefix:
        raise serializers.ValidationError(msg.UNSUPPORTED_PHONE_NUMBER)

    return number, old_user
