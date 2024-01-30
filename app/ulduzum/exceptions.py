from domain.exceptions.base import OnTimeException


class UlduzumException(OnTimeException):
    def __init__(self, *args, ulduzum_exception_message: str, **kwargs):
        self.ulduzum_exception_message = ulduzum_exception_message

    def get_extra_info(self):
        return {"original_error": self.ulduzum_exception_message}
