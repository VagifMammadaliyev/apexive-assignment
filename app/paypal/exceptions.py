from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg
from domain.exceptions.base import OnTimeException


class PayPalError(OnTimeException):
    error_type = "paypal-payment-error"
    human = msg.PAYPAL_PAYMENT_ERROR

    def __init__(self, *args, error_data=None, **kwargs):
        self.error_data = error_data

    def get_extra_info(self):
        if self.error_data:
            return {"detail": self.error_data}

        return super().get_extra_info()
