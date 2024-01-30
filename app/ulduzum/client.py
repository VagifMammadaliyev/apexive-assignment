from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction as db_transaction

from core.converter import Converter
from core.models import Currency
from fulfillment.models import Transaction
from ulduzum.exceptions import UlduzumException


class UlduzumClient:
    CALC_URL = "https://portal.emobile.az/externals/loyalty/calculate"
    COMPLETE_URL = "https://portal.emobile.az/externals/loyalty/complete"
    CANCEL_URL = "https://portal.emobile.az/externals/loyalty/cancel"
    AUTH_KEY = "b97499f6dd2e53169cc1c5e9385378d9"
    TERMINAL_CODE = "3335"
    NICE_IDENTICAL_CODE = "1111"  # for testing purposes, works only when test_mode=True
    MAX_DISCOUNT_PERCENTAGE = 10

    def __init__(self, identical_code, test_mode=settings.DEBUG):
        self.identical_code = identical_code
        self.test_mode = test_mode

    def build_request_data(self, data):
        """Adds auth data to payload."""
        data.update(
            **self.get_auth_data(), **self.get_identical_code_data(), **{"campaign": ""}
        )
        return data

    def get_identical_code_data(self):
        return {"identicalCode": self.identical_code}

    def get_auth_data(self):
        """Auth data required for all requsts"""
        return {
            "authKey": self.AUTH_KEY,
            "terminalCode": self.TERMINAL_CODE,
        }

    def parse_response_data(self, data):
        """Parses response data and checks for any error too."""
        try:
            result = data.get("result")
        except Exception as e:
            raise Exception(
                (
                    "Cannot get 'result' from ulduzum data (test_mode is %s). "
                    "Original exception was %s."
                    "Data is: %s"
                )
                % (self.test_mode, str(e), data)
            )

        if result == "success":
            return data.get("data", {})

        elif result == "error":
            raise UlduzumException(ulduzum_exception_message=data.get("errormess"))

        raise Exception("Invalid response from Ulduzum: %s", (data))

    def post(self, url, data):
        data = self.build_request_data(data)
        response = requests.post(url, json=data)
        response_data = self.parse_response_data(response.json())
        return response_data

    def __get_test_success_response(self, amount):
        """Simulates 25% discount"""
        quarter = round(float(amount / 4), 2)
        return self.parse_response_data(
            {
                "result": "success",
                "data": {
                    "amount": amount,
                    "discount_percent": 25,
                    "discounted_amount": amount - quarter,
                    "discount_amount": quarter,
                },
            }
        )

    def __get_test_error_response(self):
        return self.parse_response_data(
            {"result": "error", "errormess": "IdenticalCode-Notfound"}
        )

    def calculate(
        self,
        amount,
    ):
        amount = float(amount)

        if self.test_mode:
            if self.identical_code == self.NICE_IDENTICAL_CODE:
                return self.__get_test_success_response(amount)

            return self.__get_test_error_response()

        url = self.CALC_URL
        data = self.post(url, {"amount": amount})
        return data

    def calculate_for_shipment(self, shipment):
        # If shipment already has identical_code then cancel last applied identical code
        ulduzum_data = shipment.extra.get("ulduzum_data", {})
        last_identical_code = ulduzum_data.get("identical_code")

        if last_identical_code:
            try:
                self.cancel(identical_code=last_identical_code)
            except UlduzumException:
                pass

        data = self.calculate(
            Converter.convert(
                shipment.total_price, shipment.total_price_currency.code, "AZN"
            )
        )

        original_discount_data = data.copy()

        fixed_amount = Converter.convert(
            shipment.total_price, shipment.total_price_currency.code, "AZN"
        )
        original_discount_percent = original_discount_data.get("discount_percent", 0)
        fixed_discount_percent = Decimal(
            str(
                min(
                    original_discount_percent,
                    self.MAX_DISCOUNT_PERCENTAGE
                    if self.MAX_DISCOUNT_PERCENTAGE is not None
                    else original_discount_percent,
                )
            )
        )
        print(f"{original_discount_percent=}, {self.MAX_DISCOUNT_PERCENTAGE=}")
        fixed_discount_amount = fixed_amount * (fixed_discount_percent / 100)
        fixed_discounted_amount = fixed_amount - fixed_discount_amount

        fixed_discount_data = {
            "amount": float(round(fixed_amount, 2)),
            "discount_percent": float(round(fixed_discount_percent, 2)),
            "discounted_amount": float(round(fixed_discounted_amount, 2)),
            "discount_amount": float(round(fixed_discount_amount, 2)),
        }

        shipment.extra["ulduzum_data"] = original_discount_data
        shipment.extra["ulduzum_data"]["applied"] = False
        shipment.extra["ulduzum_data"]["identical_code"] = self.identical_code
        shipment.extra["ulduzum_data"]["test_mode"] = self.test_mode
        shipment.extra["ulduzum_data"]["fixed_data"] = fixed_discount_data
        shipment.save(update_fields=["extra"])

        return data

    @db_transaction.atomic
    def complete_for_shipment(self, shipment):
        data = self.complete(
            fake_amount=shipment.extra.get("ulduzum_data", {})
            .get("fixed_data", {})
            .get("amount", 0)
        )

        if "ulduzum_data" not in shipment.extra:
            return data

        shipment.extra["ulduzum_data"]["applied"] = True
        shipment.extra["ulduzum_data"]["identical_code"] = self.identical_code
        shipment.extra["ulduzum_data"]["test_mode"] = self.test_mode
        shipment.save(update_fields=["extra"])

        transaction = Transaction.objects.filter(
            purpose=Transaction.SHIPMENT_PAYMENT,
            related_object_identifier=shipment.number,
            is_deleted=False,
        ).first()

        if not transaction:
            raise ValueError("Cannot find related transaction for %s" % shipment)

        Transaction.objects.create(
            user=transaction.user,
            purpose=Transaction.CASHBACK,
            cashback_to=transaction,
            type=transaction.type,
            currency=Currency.objects.get(code="AZN"),
            amount=shipment.extra["ulduzum_data"]["fixed_data"]["discount_amount"],
            extra={"ulduzum_data": shipment.extra["ulduzum_data"]},
        )

        return data

    def complete(self, payment_type="CREDIT_CARD", fake_amount=None):
        if self.test_mode:
            if self.identical_code == self.NICE_IDENTICAL_CODE:
                return self.__get_test_success_response(fake_amount or 100)

            return self.__get_test_error_response()

        url = self.COMPLETE_URL
        data = self.post(url, {"paymentType": payment_type})
        return data

    def cancel_for_shipment(self, shipment):
        data = self.cancel()

        if "ulduzum_data" in shipment.extra:
            del shipment.extra["ulduzum_data"]
            shipment.save(update_fields=["extra"])

    def cancel(self, identical_code=None, payment_type="CREDIT_CARD"):
        if self.test_mode:
            if self.identical_code == self.NICE_IDENTICAL_CODE:
                return {"result": "success"}

            return self.__get_test_error_response()

        old_identical_code = self.identical_code
        self.identical_code = identical_code or self.identical_code
        url = self.CANCEL_URL
        data = self.post(url, {"paymentType": payment_type})
        self.identical_code = old_identical_code
        return data
