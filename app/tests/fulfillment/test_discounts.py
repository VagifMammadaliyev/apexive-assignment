from decimal import Decimal

import pytest

from domain.services import (
    add_discounts,
    create_uncomplete_transactions_for_orders,
    revoke_discounts,
)
from fulfillment.models import Discount


@pytest.mark.django_db
def test_adding_single_discount(simple_customer, order_factory, currency_factory):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    add_discounts(order, [Discount(percentage=20, reason=Discount.SIMPLE_DISCOUNT)])

    assert order.discounts.count() == 1
    assert order.discounts.first().reason == Discount.SIMPLE_DISCOUNT
    assert order.discounts.first().percentage == 20


@pytest.mark.django_db
def test_adding_multiple_discounts(simple_customer, order_factory, currency_factory):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    add_discounts(
        order,
        [
            Discount(percentage=20, reason=Discount.SIMPLE_DISCOUNT),
            Discount(percentage=20, reason=Discount.SIMPLE_DISCOUNT),
        ],
    )

    assert order.discounts.count() == 2


@pytest.mark.django_db
def test_calculating_single_discount(simple_customer, order_factory, currency_factory):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    add_discounts(order, [Discount(percentage=20, reason=Discount.SIMPLE_DISCOUNT)])

    assert order.discounted_total_price == Decimal("80")
    assert order.discounted_total_price_currency == order.total_price_currency
    assert order.discounted_total_price_currency_id == order.total_price_currency_id


@pytest.mark.django_db
def test_calculating_multiple_discounts(
    simple_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    add_discounts(
        order,
        [
            Discount(percentage=20, reason=Discount.SIMPLE_DISCOUNT),
            Discount(percentage=30, reason=Discount.SIMPLE_DISCOUNT),
        ],
    )

    assert order.discounted_total_price == Decimal("56")
    assert order.discounted_total_price_currency == order.total_price_currency
    assert order.discounted_total_price_currency_id == order.total_price_currency_id


@pytest.mark.django_db
def test_calculate_discounted_price_without_discounts(
    simple_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    assert order.discounted_total_price == Decimal("100")
    assert order.discounted_total_price_currency == order.total_price_currency
    assert order.discounted_total_price_currency_id == order.total_price_currency_id


@pytest.mark.django_db
def test_calculate_transaction_with_single_discount(
    simple_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    add_discounts(order, [Discount(percentage=20, reason=Discount.SIMPLE_DISCOUNT)])
    (transaction,) = create_uncomplete_transactions_for_orders([order])

    assert transaction.amount == Decimal("100")
    assert transaction.discounted_amount == Decimal("80")
    assert transaction.discounted_amount_currency == transaction.currency
    assert transaction.discounted_amount_currency_id == transaction.currency_id


@pytest.mark.django_db
def test_calculate_transaction_with_multiple_discounts(
    simple_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    add_discounts(
        order,
        [
            Discount(percentage=20, reason=Discount.SIMPLE_DISCOUNT),
            Discount(percentage=30, reason=Discount.SIMPLE_DISCOUNT),
        ],
    )

    (transaction,) = create_uncomplete_transactions_for_orders([order])

    assert transaction.amount == Decimal("100")
    assert transaction.discounted_amount == Decimal("56")
    assert transaction.discounted_amount_currency == transaction.currency
    assert transaction.discounted_amount_currency_id == transaction.currency_id


@pytest.mark.django_db
def test_calculate_transaction_after_revoking_single_discount_on_related_object(
    simple_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    add_discounts(order, [Discount(percentage=20, reason=Discount.SIMPLE_DISCOUNT)])
    (transaction,) = create_uncomplete_transactions_for_orders([order])

    revoke_discounts(order)

    transaction.refresh_from_db()
    assert transaction.amount == Decimal("100")
    assert transaction.discounted_amount == Decimal("100")
    assert transaction.discounted_amount_currency == transaction.currency
    assert transaction.discounted_amount_currency_id == transaction.currency_id


@pytest.mark.django_db
def test_overdiscount_with_single_discount(
    simple_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    add_discounts(order, [Discount(percentage=110, reason=Discount.SIMPLE_DISCOUNT)])

    assert order.discounted_total_price == Decimal("0")
    assert order.discounted_total_price_currency == order.total_price_currency
    assert order.discounted_total_price_currency_id == order.total_price_currency_id


@pytest.mark.django_db
def test_overdiscount_with_multiple_discounts(
    simple_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    add_discounts(
        order,
        [
            Discount(percentage=10, reason=Discount.SIMPLE_DISCOUNT),
            Discount(percentage=110, reason=Discount.SIMPLE_DISCOUNT),
        ],
    )

    assert order.discounted_total_price == Decimal("0")
    assert order.discounted_total_price_currency == order.total_price_currency
    assert order.discounted_total_price_currency_id == order.total_price_currency_id
