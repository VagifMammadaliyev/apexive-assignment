import pytz
from django.utils import timezone as django_timezone
from django.utils import translation


def country_timezone_middleware(get_response):
    def middleware(request):
        # Check for X-Timezone header
        timezone = request.META.get("HTTP_X_TIMEZONE")

        # Try to convert to timezone object
        try:
            tz = pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            tz = None

        if tz:
            django_timezone.activate(tz)

        response = get_response(request)

        if tz:
            django_timezone.deactivate()

        return response

    return middleware


class AdminLocaleMiddleware:
    """
    Forces Django admin app to be displayed only in `_lang`.
    """

    _lang = "en"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin"):
            translation.activate(self._lang)

        response = self.get_response(request)
        return response
