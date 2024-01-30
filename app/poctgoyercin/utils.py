from poctgoyercin.client import PoctGoyercinClient


def send_sms_to_number(phone_number, message, title=None):
    return PoctGoyercinClient().send_sms(
        phone_number=phone_number, message=message, title=title
    )


def send_sms_to_customer(customer, message, title=None):
    return PoctGoyercinClient().send_sms(
        customer=customer, message=message, title=title
    )
