import requests
from django.conf import settings

from core.models import Country
from poctgoyercin.exceptions import CantGetCustomerPhoneError, PoctGoyercinError


class PoctGoyercinClient:
    URL = settings.POCTGOYERCIN_URL
    USER = settings.POCTGOYERCIN_USER
    PASSWORD = settings.POCTGOYERCIN_PASSWORD
    SENDER_NAME = settings.POCTGOYERCIN_SENDER_NAME

    def get_customer_phone_number(self, customer):
        """
        PoctGoyercin is supporting only Azerbaijan phone numbers.
        So we get phone code for azerbaijan and replace it with empty
        string (poctgoyercin needs number in this way).
        """
        return self.normalize_phone_number(customer.full_phone_number)

    def normalize_phone_number(self, phone_number):
        try:
            country = Country.objects.get(code="AZ")
        except Country.DoesNotExist:
            raise CantGetCustomerPhoneError

        return phone_number.replace(country.phone_code, "")

    def get_url_params(self, phone_number, text):
        to_be_replaced = [
            ("ə", "e"),
            ("ü", "u"),
            ("ş", "sh"),
            ("ç", "c"),
            ("ö", "o"),
            ("ğ", "g"),
            ("ı", "i"),
        ]

        for aze, en in to_be_replaced:
            text = text.replace(aze, en)

        return {
            "gsm": phone_number,
            "text": text,
            "user": self.USER,
            "password": self.PASSWORD,
            "from": self.SENDER_NAME,
        }

    def get_request_url(self, url_params):
        return "%s?%s" % (
            self.URL,
            "&".join("%s=%s" % (key, value) for key, value in url_params.items()),
        )

    def handle_response(self, response):
        content = response.content.decode("ISO-8859-1")
        key_value_pairs = content.split("&")

        response_dict = {}
        for key_value_pair in key_value_pairs:
            key, value = key_value_pair.split("=")
            response_dict[key] = value

        if response_dict.get("errno") != "100":
            raise PoctGoyercinError(response_dict.get("errtext"))

    def send_sms(self, message, customer=None, phone_number: str = None, title=None):
        if title is not None:
            text = "%s. %s" % (title, message)
        else:
            text = message

        phone_number = (
            self.normalize_phone_number(phone_number.lstrip("0"))
            if phone_number
            else self.get_customer_phone_number(customer)
        )
        print(self.get_request_url(self.get_url_params(phone_number, text)))
        response = requests.get(
            self.get_request_url(self.get_url_params(phone_number, text))
        )
        print(response.content)

        return self.handle_response(response)
