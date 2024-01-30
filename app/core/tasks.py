from __future__ import absolute_import, unicode_literals
from decimal import Decimal

import requests
from celery import shared_task
from bs4 import BeautifulSoup
from django.db import transaction

from core.models import CurrencyRateLog, Currency

EXCHANGEGERATE = "exchangerate"
AZECENTRALBANK = "azecentralbank"


@shared_task(autoretry_for=(Exception,), retry_backoff=True)
def fetch_currency_rates(from_=EXCHANGEGERATE):
    updated_currencies = 0
    has_tried = False
    base_currency = Currency.objects.filter(rate=1).first()

    if from_ == AZECENTRALBANK:
        response = requests.get("https://www.cbar.az/currency/rates")

        if response.status_code == 200:
            has_tried = True
            soup = BeautifulSoup(response.text, "html.parser")
            data = soup.find("div", {"class": "table_items"})
            currencies_list = data.find_all("div", {"class": "table_row"})

            for currency_row in currencies_list:
                fetched_currency_code = currency_row.find(
                    "div", {"class": "kod"}
                ).text.upper()
                fetched_value = currency_row.find("div", {"class": "kurs"}).text

                try:
                    currency = Currency.objects.exclude(pk=base_currency.pk).get(
                        code=fetched_currency_code
                    )
                except Currency.DoesNotExist:
                    continue

                with transaction.atomic():
                    # We are also saving rate to the related currency object.
                    # It makes more easy to fetch that rate later.
                    rate = round(Decimal(fetched_value), 4)
                    CurrencyRateLog.objects.create(currency=currency, rate=rate)
                    currency.rate = rate
                    currency.save(update_fields=["rate"])
                    updated_currencies += 1

    elif from_ == EXCHANGEGERATE:
        request_url = (
            "https://api.exchangerate.host/latest?base={base_currency}&places=4".format(
                base_currency=base_currency.code
            )
        )
        response = requests.get(request_url)

        if response.status_code == 200:
            has_tried = True
            data = response.json()

            if data.get("success", False):
                rates_data = data.get("rates", {})
                for currency_code, currency_rate in rates_data.items():
                    try:
                        currency = Currency.objects.exclude(pk=base_currency.pk).get(
                            code=currency_code
                        )
                    except Currency.DoesNotExist:
                        continue

                    with transaction.atomic():
                        rate = 1 / round(Decimal(currency_rate), 4)
                        CurrencyRateLog.objects.create(currency=currency, rate=rate)
                        currency.rate = rate
                        currency.save(update_fields=["rate"])
                        updated_currencies += 1

    if has_tried:
        return "Updated %d currencies" % updated_currencies

    return "Request's response to provided URL was not OK (!= 200)."


@shared_task
def test_task(number=None):
    return "Completed" + f" #{number}" if number else ""
