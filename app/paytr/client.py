import base64
import hashlib
import hmac
import json
from decimal import Decimal

import requests
from django.urls import reverse
from django.conf import settings

from domain.conf import Configuration
from fulfillment.models import Transaction


class PayTR:
    MERCHANT_ID = settings.PAYTR_MERCHANT_SECRET_ID
    MERCHANT_KEY = settings.PAYTR_MERCHANT_KEY
    MERCHANT_SALT = settings.PAYTR_MERCHANT_SECRET_SALT
    MERCHANT_OK_URL = None
    MERCHANT_FAIL_URL = None
    TIMEOUT_LIMIT = "30"
    NO_INSTALLMENT = 1
    MAX_INSTALLMENT = 0
    TOKEN_URL = "https://www.paytr.com/odeme/api/get-token"

    def __init__(self, request=None, transaction=None, *args, **kwargs):
        if not request or not transaction:
            return
        conf = Configuration()
        self.merchant_ok_url = f"{conf.get_payment_completion_redirect_url(Transaction.PAYTR_SERVICE)}/?status=1"
        self.merchant_fail_url = f"{conf.get_payment_completion_redirect_url(Transaction.PAYTR_SERVICE)}/?status=0"
        self.transaction = transaction
        self.user = transaction.user

        user = self.user
        self.email = user.email
        self.payment_amount = int(float(str(transaction.amount * Decimal("100"))))
        self.merchant_oid = str(transaction.id)
        self.user_name = user.full_name
        self.user_address = (
            f"{user.billed_recipient.city.name}"
        )
        self.user_phone = user.full_phone_number.lstrip("+")

        self.currency = transaction.currency.code
        self.user_ip = self.get_client_ip(request=request)

        self.user_basket = self._create_basket()

        # debug_on = 1
        self.debug_on = 1 if settings.DEBUG else 0
        self.test_mode = 1 if settings.DEBUG else 0

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def _get_hash_str(self):
        return (
            "{merchant_id}{user_ip}{merchant_oid}{email}{payment_amount}{user_basket}{no_installment}"
            "{max_installment}{currency}{test_mode}"
            "".format(
                **{
                    "merchant_id": self.MERCHANT_ID,
                    "user_ip": self.user_ip,
                    "merchant_oid": self.merchant_oid,
                    "email": self.email,
                    "payment_amount": self.payment_amount,
                    "user_basket": self.user_basket.decode(),
                    "no_installment": self.NO_INSTALLMENT,
                    "max_installment": self.MAX_INSTALLMENT,
                    "currency": self.currency,
                    "test_mode": self.test_mode,
                }
            )
        )

    def _generate_signature(self, data):
        message = bytes(data, "utf-8")
        secret = bytes(self.MERCHANT_KEY, "utf-8")
        return hmac.new(secret, message, hashlib.sha256)

    @staticmethod
    def _b64encode(data):
        return base64.b64encode(data)

    def _prepare_token_request_values(self, paytr_token):
        return {
            "merchant_id": self.MERCHANT_ID,
            "user_ip": self.user_ip,
            "merchant_oid": self.merchant_oid,
            "email": self.email,
            "payment_amount": self.payment_amount,
            "paytr_token": paytr_token.decode(),
            "user_basket": self.user_basket.decode(),
            "debug_on": self.debug_on,
            "no_installment": self.NO_INSTALLMENT,
            "max_installment": self.MAX_INSTALLMENT,
            "user_name": self.user_name,
            "user_address": self.user_address,
            "user_phone": self.user_phone,
            "merchant_ok_url": self.merchant_ok_url,
            "merchant_fail_url": self.merchant_fail_url,
            "timeout_limit": self.TIMEOUT_LIMIT,
            "currency": self.currency,
            "test_mode": self.test_mode,
        }

    def _create_basket(self):
        basket = [
            [
                "User {email} made a payment".format(email=self.email),
                "{:.2f}".format(int(self.payment_amount) / 100),
                1,
            ]
        ]
        basket_dumps = json.dumps(basket)
        return self._b64encode(basket_dumps.encode())

    def generate_token(self):
        hash_str = self._get_hash_str()
        hashed_signature = self._generate_signature(hash_str + self.MERCHANT_SALT)
        paytr_token = self._b64encode(hashed_signature.digest())
        post_values = self._prepare_token_request_values(paytr_token)

        resp = requests.post(
            self.TOKEN_URL,
            post_values,
            headers={"Cache-Control": "no-cache"},
            timeout=20,
        )
        try:
            return resp.json()
        except json.decoder.JSONDecodeError:
            return resp.text

    def is_valid_hash(self, **kwargs):
        hashed_signature = self._generate_signature(
            kwargs.get("merchant_oid")
            + self.MERCHANT_SALT
            + kwargs.get("status")
            + kwargs.get("total_amount")
        )
        token = self._b64encode(hashed_signature.digest()).decode()
        return token == kwargs.get("hash")
