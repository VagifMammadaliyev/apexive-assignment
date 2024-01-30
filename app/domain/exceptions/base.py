from django.utils.translation import gettext_lazy as _

from ontime import messages as msg


class OnTimeException(Exception):
    status_code = 400
    human = msg.ERROR_OCCURRED
    error_type = "error"
    extra_info = {}

    def __init__(self, human=None, **kwargs):
        super().__init__(**kwargs)
        self.human = human or self.__class__.human

    def __repr__(self):
        return "<%s human=%s>" % (self.__class__.__name__, self.human)

    def __str__(self):
        return str(self.human)

    def get_humanized(self):
        return self.human

    def get_status_code(self):
        return str(self.status_code)

    def get_error_type(self):
        return self.error_type

    def get_extra_info(self):
        return self.extra_info

    def serialize(self):
        return {
            "type": self.get_error_type(),
            "status": self.get_status_code(),
            "human": self.get_humanized(),
            **self.get_extra_info(),
        }
