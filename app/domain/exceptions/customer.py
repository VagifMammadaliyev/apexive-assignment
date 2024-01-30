from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg
from domain.exceptions.base import OnTimeException


class ProfileError(OnTimeException):
    human = msg.PROFILE_ERROR_OCCURRED
    error_type = "profile-error"


class UncompleteProfileError(ProfileError):
    human = msg.PROFILE_INCOMPLETE_ERROR


class VerificationError(OnTimeException):
    status_code = 400
    human = msg.INVALID_CONFIRMATION_CODE_ERROR
    error_type = "verification-error"


class AlreadyVerifiedError(VerificationError):
    human = msg.ALREADY_CONFIRMED_ERROR


class EmailConfirmationError(OnTimeException):
    status_code = 400
    error_type = "confirmation-error"
    human = msg.EMAIL_CANNOT_BE_VERIFIED_ERROR


class BalanceError(OnTimeException):
    human = msg.BALANCE_OPERATION_ERROR
    error_type = "balance-error"


class InsufficientBalanceError(BalanceError):
    human = msg.BALANCE_HAS_INSUFFICIENT_AMOUNT_ERROR

    def __init__(self, *args, currency_code=None, missing_amount=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.currency_code = currency_code
        self.missing_amount = missing_amount

    def get_extra_info(self):
        return {"missing": str(self.missing_amount), "balance": self.currency_code}


class CantTopUpBalanceError(BalanceError):
    human = msg.USER_DATA_INCOMPLETE_ERROR


class PasswordResetCodeInvalidError(OnTimeException):
    error_type = "invalid-code"
    human = msg.INVALID_RESET_CODE


class InvalidPromoCode(OnTimeException):
    human = msg.INVITE_FRIEND_INVALID_PROMO_CODE
    error_type = "invalid-code"
