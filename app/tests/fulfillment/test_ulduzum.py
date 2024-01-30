from decimal import Decimal

import pytest

from ulduzum.client import UlduzumClient
from ulduzum.exceptions import UlduzumException
from core.converter import Converter
from domain.services import (
    create_uncomplete_transaction_for_shipment,
    complete_payments,
)


@pytest.mark.django_db
def test_ulduzum_calculate(shipment_factory, currency_factory, simple_customer):
    usd = currency_factory(code="USD")
    azn = currency_factory(code="AZN")

    shipment = shipment_factory(
        user=simple_customer,
        total_price=10,
        total_price_currency=usd,
    )

    client = UlduzumClient("1111", test_mode=True)
    data = client.calculate_for_shipment(shipment)

    discount_data = data

    print(discount_data)

    assert Decimal(str(discount_data["amount"])) == Decimal(
        Converter.convert(10, "USD", "AZN")
    )
    assert Decimal(str(discount_data["discounted_amount"])) == Decimal(
        Converter.convert(7.5, "USD", "AZN")
    )
    assert Decimal(str(discount_data["discount_amount"])) == Decimal(
        Converter.convert(2.5, "USD", "AZN")
    )

    # Check that this data saved to extra
    shipment.refresh_from_db()
    extra = shipment.extra

    assert extra["ulduzum_data"]["discount_amount"] == discount_data["discount_amount"]
    assert extra["ulduzum_data"]["applied"] == False


@pytest.mark.django_db
def test_ulduzum_fixed_calculate(shipment_factory, currency_factory, simple_customer):
    usd = currency_factory(code="USD")
    azn = currency_factory(code="AZN")

    shipment = shipment_factory(
        user=simple_customer,
        total_price=10,
        total_price_currency=usd,
    )

    client = UlduzumClient("1111", test_mode=True)
    data = client.calculate_for_shipment(shipment)

    shipment.refresh_from_db()
    discount_data = shipment.extra["ulduzum_data"]["fixed_data"]

    print(discount_data)

    assert Decimal(str(discount_data["amount"])) == Decimal(
        Converter.convert(10, "USD", "AZN")
    )
    assert Decimal(str(discount_data["discounted_amount"])) == Decimal(
        Converter.convert(9, "USD", "AZN")
    )
    assert Decimal(str(discount_data["discount_amount"])) == Decimal(
        Converter.convert(1, "USD", "AZN")
    )


@pytest.mark.django_db
def test_ulduzum_complete(shipment_factory, currency_factory, simple_customer):
    usd = currency_factory(code="USD")
    azn = currency_factory(code="AZN")

    shipment = shipment_factory(
        user=simple_customer,
        total_price=10,
        total_price_currency=usd,
    )
    transaction = create_uncomplete_transaction_for_shipment(shipment)

    client = UlduzumClient("1111", test_mode=True)
    client.calculate_for_shipment(shipment)
    data = client.complete_for_shipment(shipment)

    assert transaction.cashbacks.count() == 1

    cashback_transaction = transaction.cashbacks.first()
    assert cashback_transaction.amount == Decimal(
        str(shipment.extra["ulduzum_data"]["fixed_data"]["discount_amount"])
    )
    assert cashback_transaction.currency.code == "AZN"

    shipment.refresh_from_db()
    assert shipment.extra["ulduzum_data"]["applied"] == True


@pytest.mark.django_db
def test_ulduzum_fail_calculate(shipment_factory, currency_factory, simple_customer):
    usd = currency_factory(code="USD")
    azn = currency_factory(code="AZN")

    shipment = shipment_factory(
        user=simple_customer,
        total_price=10,
        total_price_currency=usd,
    )

    client = UlduzumClient("BAD_CODE", test_mode=True)
    with pytest.raises(UlduzumException):
        data = client.calculate_for_shipment(shipment)

    shipment.refresh_from_db()
    assert "ulduzum_data" not in shipment.extra


@pytest.mark.django_db
def test_ulduzum_fail_complete(shipment_factory, currency_factory, simple_customer):
    usd = currency_factory(code="USD")
    azn = currency_factory(code="AZN")

    shipment = shipment_factory(
        user=simple_customer,
        total_price=10,
        total_price_currency=usd,
    )
    transaction = create_uncomplete_transaction_for_shipment(shipment)

    client = UlduzumClient("1111", test_mode=True)
    client.calculate_for_shipment(shipment)

    client = UlduzumClient("BAD_CODE", test_mode=True)
    with pytest.raises(UlduzumException):
        data = client.complete_for_shipment(shipment)

    assert transaction.cashbacks.exists() == False


@pytest.mark.django_db
def test_complete_ulduzumed_shipment(shipment_factory, currency_factory, rich_customer):
    usd = currency_factory(code="USD")
    azn = currency_factory(code="AZN")

    shipment = shipment_factory(
        user=rich_customer,
        total_price=10,
        total_price_currency=usd,
    )
    transaction = create_uncomplete_transaction_for_shipment(shipment)
    client = UlduzumClient("1111", test_mode=True)
    client.calculate_for_shipment(shipment)

    balance = rich_customer.active_balance
    old_amount = balance.amount
    complete_payments(
        [transaction],
    )
    balance.refresh_from_db()
    new_amount = balance.amount

    assert new_amount == old_amount - Decimal("10") + Decimal("1")


@pytest.mark.django_db
def test_ulduzum_cancel(shipment_factory, currency_factory, simple_customer):
    usd = currency_factory(code="USD")
    azn = currency_factory(code="AZN")

    shipment = shipment_factory(
        user=simple_customer,
        total_price=10,
        total_price_currency=usd,
    )

    client = UlduzumClient("1111", test_mode=True)
    client.calculate_for_shipment(shipment)
    shipment.refresh_from_db()
    client.cancel_for_shipment(shipment)
    shipment.refresh_from_db()

    assert "ulduzum_data" not in shipment.extra
