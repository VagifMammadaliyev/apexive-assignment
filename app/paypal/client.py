import json
import base64
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from django.urls import reverse
from paypalcheckoutsdk.orders import OrdersCreateRequest, OrdersCaptureRequest
from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment, LiveEnvironment
from paypalhttp.http_error import HttpError

from ontime import messages as msg
from domain.conf import Configuration
from domain.services import complete_payments
from domain.exceptions.payment import PaymentError
from paypal.exceptions import PayPalError
from core.converter import Converter
from core.models import Currency
from fulfillment.models import Transaction


class PayPalClient:
    CLIENT_ID = settings.PAYPAL_CLIENT
    SECRET = settings.PAYPAL_SECRET
    OAUTH_URL = settings.PAYPAL_OAUTH_API
    ORDER_URL = settings.PAYPAL_ORDER_API
    CURRENCY_CODE = settings.PAYPAL_CURRENCY_CODE
    _DEFAULT_HEADERS = {"Accept": "application/json"}

    def __init__(
        self,
        client_id=None,
        secret=None,
        ouath_url=None,
        order_url=None,
        currency_code=None,
    ):
        self.client_id = client_id or self.CLIENT_ID
        self.secret = secret or self.SECRET
        self.ouath_url = ouath_url or self.OAUTH_URL
        self.order_url = order_url or self.ORDER_URL
        self.currency_code = currency_code or self.CURRENCY_CODE

        EnvClass = LiveEnvironment if settings.PROD else SandboxEnvironment
        self.environment = EnvClass(client_id=self.client_id, client_secret=self.secret)
        self._client = PayPalHttpClient(self.environment)

    @db_transaction.atomic
    def create_order(
        self,
        http_request,
        amount=None,
        currency: Currency = None,
        transaction: Transaction = None,
    ):
        user = http_request.user
        request = OrdersCreateRequest()
        request.prefer("return=representation")

        amount = round(Decimal(amount), 2) if amount else transaction.discounted_amount
        currency = currency or transaction.discounted_amount_currency
        # Convert amount to Paypal currency
        converted_amount = Converter.convert(amount, currency.code, self.currency_code)

        transaction = (
            Transaction.objects.create(
                user=user,
                currency=currency,
                amount=amount,
                purpose=Transaction.BALANCE_INCREASE,
                type=Transaction.CARD,
                payment_service=Transaction.PAYPAL_SERVICE,
            )
            if not transaction
            else transaction
        )

        conf = Configuration()

        request.request_body(
            {
                "reference_id": f"AZON{transaction.id}",
                "intent": "CAPTURE",
                "application_context": {
                    "return_url": http_request.build_absolute_uri(
                        reverse("paypal-result")
                    ),
                    "shipping_preference": "SET_PROVIDED_ADDRESS",
                },
                "payer": {
                    "email_address": user.email,  # do not check that email is verified
                    "name": {
                        "given_name": user.first_name,
                        "surname": user.last_name,
                    },
                    "phone": {
                        "phone_type": "MOBILE",
                        "phone_number": {
                            "national_number": user.full_phone_number.lstrip("+"),
                        },
                    },
                },
                "purchase_units": [
                    {
                        "amount": {
                            "currency_code": self.currency_code,
                            "value": str(converted_amount),
                        },
                        "shipping": {
                            "address": {
                                "name": {
                                    "full_name": user.full_name,
                                    "surname": user.last_name,
                                },
                                "address_line_1": "%s, %s"
                                % (
                                    user.billed_recipient.city.name,
                                    user.billed_recipient.region.title,
                                ),
                                "admin_area_1": user.billed_recipient.region.title,
                                "admin_area_2": user.billed_recipient.city.name,
                                "country_code": user.billed_recipient.city.country.code,
                            },
                        },
                    }
                ],
            }
        )
        try:
            response = self._client.execute(request)
        except HttpError as e:
            error_data = json.loads(e.message)
            raise PayPalError(error_data=error_data)
        order_data = response.result.dict()

        errors = order_data.get("error")
        if errors:
            transaction.extra["paypal_create_order_errors"] = errors
            transaction.save(update_fields=["extra"])
            raise PayPalError(order_error_data=errors)

        order_id = order_data.get("id")

        # Save response data to transaction
        transaction.payment_service_response_json["order_id"] = order_id
        transaction.payment_service_response_json["create_response"] = order_data
        transaction.payment_service_responsed_at = timezone.now()
        transaction.save(
            update_fields=[
                "payment_service_response_json",
                "payment_service_responsed_at",
            ]
        )

        return order_id, self._extract_link(order_data, "approve")

    def _extract_link(self, data: dict, type_: str):
        links = data.get("links", [])

        for link in links:
            if isinstance(link, dict) and link.get("rel") == type_:
                return link.get("href")

        return None

    @db_transaction.atomic
    def capture_transaction(self, order_id, payer_id):
        transaction = Transaction.objects.filter(
            type=Transaction.CARD,
            # purpose=Transaction.BALANCE_INCREASE,
            payment_service=Transaction.PAYPAL_SERVICE,
            payment_service_response_json__order_id=order_id,
        ).first()

        if transaction:
            request = OrdersCaptureRequest(order_id)
            error_occured = False

            try:
                response = self._client.execute(request)
            except HttpError as e:
                error_occured = True
                error_data = json.loads(e.message)
                raise PayPalError(error_data=error_data)

            capture_data = response.result.dict()

            errors = capture_data.get("error")  # May be this does not even working
            if errors:
                raise PayPalError(order_error_data=errors)

            transaction.payment_service_response_json["payer_id"] = payer_id
            transaction.payment_service_response_json["capture_response"] = capture_data
            transaction.payment_service_responsed_at = timezone.now()
            transaction.save(
                update_fields=[
                    "payment_service_response_json",
                    "payment_service_responsed_at",
                ]
            )
            complete_payments([transaction], unmake_partial=False)
            return transaction

        raise PaymentError(human=msg.PAYMENT_NOT_FOUND)
