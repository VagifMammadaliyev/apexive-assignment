from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg
from domain.exceptions.base import OnTimeException


class SecureAcceptanceError(OnTimeException):
    error_type = "secure-payment-error"
    human = msg.PAYMENT_SYSTEM_CONNECTION_ERROR


class InvalidFormDataError(SecureAcceptanceError):
    human = msg.INVALID_OR_MALFORMED_DATA


class InvalidOrMalformedResponseError(SecureAcceptanceError):
    pass
