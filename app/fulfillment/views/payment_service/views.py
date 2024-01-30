from django.views import View
from django.shortcuts import redirect
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)

from paytr.client import PayTR
from paypal.client import PayPalClient
from cybersource.secure_acceptance import SecureAcceptanceClient
from cybersource.exceptions import InvalidOrMalformedResponseError
from domain.conf import Configuration
from domain.services import complete_payments
from domain.exceptions.payment import PaymentError
from fulfillment.models import Transaction


def get_redirect(payment_service, transaction=None, success=True):
    redirect_url = Configuration().get_payment_completion_redirect_url(payment_service)

    return redirect(
        "%s/?status=%s&invoice=%s&payment_service=%s"
        % (
            redirect_url.rstrip("/"),
            "1" if success else "0",
            transaction.invoice_number if transaction else "",
            payment_service,
        )
    )


def process_transaction(data, api_response=True):
    # This method must not be run in atomic context, because if we fail
    # to complete the payment, we must at least save the response from CyberSource
    secure_acceptance_client = SecureAcceptanceClient(response_data=data)

    if secure_acceptance_client.is_response_valid():
        try:
            transaction = secure_acceptance_client.save_response_data_to_transcation()
        except InvalidOrMalformedResponseError:
            if api_response:
                raise
            else:
                return HttpResponse("MALFORMED", status=400)

        if transaction.completed:  # check if already completed
            return get_redirect(
                Transaction.CYBERSOURCE_SERVICE, transaction=transaction, success=True
            )

        # Selecting for update
        transactions = Transaction.objects.select_for_update().filter(id=transaction.id)
        try:
            transaction = complete_payments(transactions, unmake_partial=False)
        except PaymentError:
            return get_redirect(Transaction.CYBERSOURCE_SERVICE, success=False)

        if api_response:
            return Response({"status": "OK"})

        return get_redirect(
            Transaction.CYBERSOURCE_SERVICE, transaction=transaction, success=True
        )

    if api_response:
        return Response({"status": "FAIL"}, status=400)

    return get_redirect(Transaction.CYBERSOURCE_SERVICE, success=False)


class CybersourceAutoResultNotificationView(View):
    """
    Cybersource will notify the merchant (us) here.
    This may be cancellation or success notification.
    This view is publicly available.
    """

    def post(self, *args, **kwargs):
        return process_transaction(self.request.POST.dict(), api_response=False)


class CybersourceResultNotificationView(APIView):
    """
    The same as previous view, but is used by our front
    application, not cybersource. This view is for authenticated
    request only.
    """

    def post(self, *args, **kwargs):
        return process_transaction(self.request.data.dict(), api_response=True)


class PayPalAutoNotificationView(View):
    """
    PayPal will notify the merchant (us) here.
    This is not a webhook handler from PayPal! (just a little hack :D)
    """

    def get(self, *args, **kwargs):
        order_id = self.request.GET.get("token", None)
        payer_id = self.request.GET.get("PayerID", None)
        try:
            transaction = PayPalClient().capture_transaction(order_id, payer_id)
        except PaymentError:
            return get_redirect(Transaction.PAYPAL_SERVICE, success=False)
        return get_redirect(
            Transaction.PAYPAL_SERVICE, transaction=transaction, success=True
        )


class PayTRSuccessView(View):
    def post(self, request):
        print("accepting PayTR payment")
        if all(
            k in request.POST
            for k in ("status", "total_amount", "merchant_oid", "hash")
        ):
            payment = PayTR()
            if payment.is_valid_hash(
                status=request.POST["status"],
                total_amount=request.POST["total_amount"],
                merchant_oid=request.POST["merchant_oid"],
                hash=request.POST["hash"],
            ):
                print("- valid hash provided")
                post_params = dict(request.POST.dict())
                print("- ", post_params)
                transaction = Transaction.objects.filter(
                    id=request.POST["merchant_oid"]
                ).first()
                print(
                    f"- found transaction with id {request.POST['merchant_oid']} -> {transaction or 'not found...'}"
                )
                if transaction:
                    transaction.payment_service_response_json = post_params
                    transaction.save()
                    if request.POST["status"] == "success":
                        try:
                            transactions = (
                                Transaction.objects.select_for_update().filter(
                                    id=request.POST["merchant_oid"]
                                )
                            )
                            transaction = complete_payments(
                                transactions, unmake_partial=False
                            )
                        except Exception as error:
                            print("ERROR WHILE PROCESSING PAYTR", error)
                            return HttpResponse("OK")
                        return HttpResponse("OK")
                return HttpResponse("OK")
        return HttpResponse("OK")
