from pprint import pprint
from datetime import datetime

import pytest
from django.urls import reverse
from django import utils

from domain.services import (
    create_uncomplete_transaction_for_shipment,
    confirm_shipment_properties,
)
from fulfillment.models import Transaction


@pytest.mark.django_db
def test_multiple_shipment_invoice(
    api_client,
    simple_customer,
    shipment_factory,
    currency_factory,
):
    usd = currency_factory(code="USD")
    api_client.force_authenticate(user=simple_customer)
    shipment1 = shipment_factory(
        user=simple_customer,
        total_price=10,
        total_price_currency=usd,
    )
    shipment2 = shipment_factory(
        user=simple_customer,
        total_price=10,
        total_price_currency=usd,
    )

    shipments = [shipment1, shipment2]

    for s in shipments:
        t = create_uncomplete_transaction_for_shipment(s)
        print(t)

    url = (
        reverse("multiple-invoice")
        + "?"
        + "&".join(f"identifier={s.identifier}" for s in shipments)
    )
    response = api_client.get(url)

    pprint(response.data)

    assert len(response.data["objects"]) == 2


# @pytest.mark.django_db
# def test_updating_related_transaction_when_shipment_updated(
#     simple_customer, shipment_factory, currency_factory, transaction_factory
# ):
#     usd = currency_factory(code="USD")
#     shipment = shipment_factory(
#         user=simple_customer, total_price=10, total_price_currency=usd, is_paid=False
#     )
#
#     transaction = transaction_factory(
#         user=simple_customer,
#         amount=shipment.total_price,
#         currency=shipment.total_price_currency,
#         related_object=shipment,
#         purpose=Transaction.SHIPMENT_PAYMENT,
#         completed=False,
#     )
#
#     shipment.total_price = 20
#     shipment._must_recalculate = True
#     shipment.save()
#
#     transaction.refresh_from_db()
#
#     assert transaction.amount == transaction.original_amount == shipment.total_price


@pytest.mark.django_db
def test_updating_status_update_time_when_confirming(
    simple_customer, shipment_factory, usd
):
    shipment = shipment_factory(
        user=simple_customer,
        fixed_total_weight=1,
        is_volume_considered=False,
        is_paid=False,
        confirmed_properties=False,
        total_price=100,
        total_price_currency=usd,
    )
    old_time = shipment.status_last_update_time
    confirm_shipment_properties(shipment)
    new_time = shipment.status_last_update_time
    assert new_time > old_time
