from django.conf import settings
from django.utils import timezone, translation

from fulfillment.models import Transaction
from cybersource.security import Security
from cybersource.exceptions import InvalidOrMalformedResponseError


class SecureAcceptanceClient:
    PROFILE_ID = settings.CYBERSOURCE_PROFILE_ID
    ACCESS_KEY = settings.CYBERSOURCE_ACCESS_KEY
    URL = settings.CYBERSOURCE_URL

    def __init__(
        self,
        *,
        transaction_uuid=None,
        reference_number=None,
        amount=None,
        currency_code=None,
        bill_address=None,
        bill_city=None,
        bill_country=None,
        customer_email=None,
        customer_first_name=None,
        customer_last_name=None,
        response_data=None,
    ):
        self.transaction_uuid = transaction_uuid
        self.reference_number = reference_number
        self.amount = amount
        self.currency_code = currency_code
        self.response_data = response_data
        self.bill_address = bill_address
        self.bill_city = bill_city
        self.bill_country = bill_country
        self.customer_email = customer_email
        self.customer_first_name = customer_first_name
        self.customer_last_name = customer_last_name

    def get_form_parameters(self):
        """
        Get form data that must be posted to Cybersource URL
        """
        params = {
            "access_key": self.ACCESS_KEY,
            "profile_id": self.PROFILE_ID,
            "transaction_uuid": str(self.transaction_uuid),
            "locale": "en",
            "transaction_type": "sale",
            "reference_number": f"AZON{str(self.reference_number)}",
            "amount": str(self.amount),
            "bill_to_address_line1": self.bill_address,
            "bill_to_address_city": self.bill_city,
            "bill_to_address_country": self.bill_country,
            "bill_to_email": self.customer_email,
            "bill_to_forename": self.customer_first_name,
            "bill_to_surname": self.customer_last_name,
            "ship_to_address_city": self.bill_city,
            "ship_to_address_country": self.bill_country,
            "ship_to_address_line1": self.bill_address,
            "ship_to_forename": self.customer_first_name,
            "ship_to_surname": self.customer_last_name,
            "currency": str(self.currency_code),
        }

        params["signature"] = Security().sign(params)
        return params

    def get_form_data(self):
        # Serialize input
        inputs = [
            {"name": name, "value": value, "type": "hidden"}
            for name, value in self.get_form_parameters().items()
        ]
        return {"url": self.URL, "method": "post", "inputs": inputs}

    def is_response_valid(self):
        return Security().check(self.response_data)

    def save_response_data_to_transcation(self):
        """
        After calling this method transaction will be in a state that can be fulfilled
        by a function used to complete payments. Returns a transaction.
        """
        try:
            transaction_id = self.response_data.get("req_reference_number")
            if transaction_id and transaction_id.startswith("AZON"):
                transaction_id = transaction_id[4:]
            transaction = Transaction.objects.filter(
                payment_service=Transaction.CYBERSOURCE_SERVICE,
                # payment_service_responsed_at__isnull=True,
                id=transaction_id,
                invoice_number=self.response_data.get("req_transaction_uuid"),
            ).first()

            if not transaction:
                raise Transaction.DoesNotExist

            if transaction.completed:
                return transaction

        except Transaction.DoesNotExist:
            raise InvalidOrMalformedResponseError

        transaction.payment_service_responsed_at = timezone.now()
        transaction.payment_service_response_json = self.response_data
        transaction.save(
            update_fields=[
                "payment_service_responsed_at",
                "payment_service_response_json",
            ]
        )

        return transaction
