from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg
from domain.exceptions.base import OnTimeException


class PoctGoyercinError(OnTimeException):
    error_type = "sms-error"
    human = msg.SMS_CANNOT_BE_SENT


class CantGetCustomerPhoneError(PoctGoyercinError):
    human = msg.SMS_INVALID_OR_OUT_OF_SERVICE_RECIPIENT_NUMBER
