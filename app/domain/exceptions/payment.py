from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg
from domain.exceptions.base import OnTimeException


class PaymentError(OnTimeException):
    error_type = "payment-error"
    human = msg.PAYMENT_DID_NOT_SUCCESS_ERROR
