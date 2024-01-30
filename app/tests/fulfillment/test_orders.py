from pprint import pprint
from decimal import Decimal
import pytest
from django.urls import reverse

from fulfillment.models import Transaction, Order, Status, Discount
from domain.services import (
    set_remainder_price,
    approve_remainder_price,
    create_uncomplete_transactions_for_orders,
    complete_payments,
    add_discounts,
)


def create_order_pay_and_then_add_remainder(
    user,
    staff_user,
    currency_factory,
    order_factory,
    country_factory,
    discounts=[],
    return_transaction=False,
):
    """`staff_user` is for logging in approve_remainder"""
    usd = currency_factory(code="USD")
    order = order_factory(
        source_country=country_factory(code="US"),
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
        user=user,
        product_price=90,
        cargo_price=10,
        product_price_currency=usd,
        cargo_price_currency=usd,
        total_price_currency=usd,
    )

    if discounts:
        add_discounts(order, discounts)

    print(f"{order.user.active_balance=} -> before payment")
    create_uncomplete_transactions_for_orders([order])
    tr = complete_payments(
        [Transaction.objects.get(related_object_identifier=order.identifier)]
    )
    order.user.active_balance.refresh_from_db()
    print(f"{order.user.active_balance=} -> after payment")

    order.refresh_from_db()
    order.real_product_price = 100
    order.save(update_fields=["real_product_price"])
    set_remainder_price(order, log=False, staff_user=None)
    order.refresh_from_db()
    t = approve_remainder_price(staff_user, order)
    order.refresh_from_db()
    if return_transaction:
        return order, t
    return order


@pytest.mark.django_db
def test_remainder_transaction_creation(
    dummy_conf,
    rich_customer,
    staff_user,
    order_factory,
    currency_factory,
    country_factory,
):
    order = create_order_pay_and_then_add_remainder(
        rich_customer, staff_user, currency_factory, order_factory, country_factory
    )

    transactions = Transaction.objects.all()
    assert (
        transactions.count() == 2
    ), "Two transactions must be created, one for payment, another for remainder"

    tr1, tr2 = transactions.order_by("id").all()
    assert (
        tr1.amount == 100
    ), "First transaction's amount must be order's total price (100 USD)"
    assert tr2.amount == 10, "Second transaction's amount must be 10 USD"


@pytest.mark.django_db
def test_payments_view_after_adding_remainder_transaction(
    dummy_conf,
    api_client,
    rich_customer,
    staff_user,
    order_factory,
    currency_factory,
    country_factory,
):
    order = create_order_pay_and_then_add_remainder(
        rich_customer, staff_user, currency_factory, order_factory, country_factory
    )

    api_client.force_authenticate(rich_customer)
    url = reverse("payment-list")
    response = api_client.get(url)

    data = response.data

    assert data["count"] == 2, "Two transactions must be created"
    assert (
        Decimal(data["results"][0]["amount"]) == 10
    ), "Remainder transaction must be latest and 10 USD"
    assert (
        data["results"][0]["currency"]["code"] == "USD"
    ), "Remainder transaction currency must be USD"
    assert (
        Decimal(data["results"][1]["amount"]) == 100
    ), "Main transaction must be oldest and 100 USD"
    assert (
        data["results"][1]["currency"]["code"] == "USD"
    ), "Main transaction currency must be USD"


@pytest.mark.django_db
def test_order_invoice_total_after_remainder_added(
    dummy_conf,
    api_client,
    rich_customer,
    staff_user,
    order_factory,
    currency_factory,
    country_factory,
):
    order = create_order_pay_and_then_add_remainder(
        rich_customer, staff_user, currency_factory, order_factory, country_factory
    )

    api_client.force_authenticate(rich_customer)
    url = reverse("order-invoice", args=[order.identifier])
    response = api_client.get(url)

    total_amounts = response.data["totals"]
    total_amount = None

    for ta in total_amounts:
        if ta.get("is_main"):
            total_amount = ta

    assert total_amount, "No main total amount provided"

    assert (
        Decimal(total_amount["amount"]) == 110
    ), "Invalid total amount in order invoice"


@pytest.mark.django_db
def test_order_invoice_remainder_field_after_remainder_added(
    dummy_conf,
    api_client,
    rich_customer,
    staff_user,
    order_factory,
    currency_factory,
    country_factory,
):
    order = create_order_pay_and_then_add_remainder(
        rich_customer, staff_user, currency_factory, order_factory, country_factory
    )

    api_client.force_authenticate(rich_customer)
    url = reverse("order-invoice", args=[order.identifier])
    response = api_client.get(url)

    order_remainder = response.data["order_remainders"][
        0
    ]  # only one object because base currency same as transaction currency

    assert order_remainder, "Order remainder is not provided"

    amount = order_remainder["amount"]
    currency = order_remainder["currency"]

    assert currency and currency["code"] == "USD", "Remainder must be in USD"
    assert Decimal(amount) == 10, "Remainder amount must be 10"


@pytest.mark.django_db
def test_order_invoice_missing_field_after_remainder_added(
    dummy_conf,
    api_client,
    rich_customer,
    staff_user,
    order_factory,
    currency_factory,
    country_factory,
):
    order = create_order_pay_and_then_add_remainder(
        rich_customer, staff_user, currency_factory, order_factory, country_factory
    )

    balance = rich_customer.active_balance
    balance.amount = 5
    balance.save()
    api_client.force_authenticate(rich_customer)
    url = reverse("order-invoice", args=[order.identifier])
    response = api_client.get(url)

    missing_amount = response.data["missing"]
    is_active = missing_amount["is_active"]
    amount = missing_amount["amount"]
    currency = missing_amount["currency"]

    assert is_active == True, "Order missing price must be active on invoice"
    assert currency and currency["code"] == "USD", "Missing amount currency bust be USD"
    assert Decimal(amount) == 5, "Remainder amount must be 5"


@pytest.mark.django_db
def test_order_remainder_payment_with_discounts(
    dummy_conf,
    rich_customer,
    staff_user,
    order_factory,
    currency_factory,
    country_factory,
):
    order, remainder_transaction = create_order_pay_and_then_add_remainder(
        rich_customer,
        staff_user,
        currency_factory,
        order_factory,
        country_factory,
        discounts=[Discount(percentage=20)],
        return_transaction=True,
    )

    old_balance = rich_customer.active_balance.amount
    print(f"{old_balance=}")
    complete_payments([remainder_transaction], override_type=Transaction.BALANCE)
    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount
    print(f"{new_balance=}")

    assert new_balance == old_balance - Decimal("10") * Decimal("0.8")


@pytest.mark.django_db
def test_order_invoice_for_remainder_price_with_discounts(
    api_client,
    dummy_conf,
    rich_customer,
    staff_user,
    order_factory,
    currency_factory,
    country_factory,
):
    order, remainder_transaction = create_order_pay_and_then_add_remainder(
        rich_customer,
        staff_user,
        currency_factory,
        order_factory,
        country_factory,
        discounts=[Discount(percentage=20)],
        return_transaction=True,
    )

    api_client.force_authenticate(rich_customer)
    url = reverse("order-invoice", args=[order.identifier])
    response = api_client.get(url)

    pprint(response.data)

    order_remainder = response.data["order_remainders"][0]
    amount = order_remainder["amount"]

    assert Decimal(amount) == Decimal(
        "8"
    ), "Order remainder is not discounted in response invoice"


@pytest.mark.django_db
def test_order_invoice_for_remainder_missing_price_with_discounts(
    api_client,
    dummy_conf,
    rich_customer,
    staff_user,
    order_factory,
    currency_factory,
    country_factory,
):
    order, remainder_transaction = create_order_pay_and_then_add_remainder(
        rich_customer,
        staff_user,
        currency_factory,
        order_factory,
        country_factory,
        discounts=[Discount(percentage=20)],
        return_transaction=True,
    )

    api_client.force_authenticate(rich_customer)
    url = reverse("order-invoice", args=[order.identifier])

    balance = rich_customer.active_balance
    balance.amount = 5
    balance.save()

    response = api_client.get(url)

    pprint(response.data)

    missing_amount = response.data["missing"]
    is_active = missing_amount["is_active"]
    amount = missing_amount["amount"]
    currency = missing_amount["currency"]

    assert is_active == True
    assert currency["code"] == "USD"
    assert Decimal(amount) == Decimal(
        "3"
    ), "Missing price must be calculated from discounted remainder price"


@pytest.mark.django_db
def test_order_transaction_updating_after_customer_updated_order_price(
    dummy_conf, rich_customer, order_factory, country_factory
):
    country = country_factory(code="US")
    order = order_factory(
        user=rich_customer,
        total_price=100,
        source_country=country,
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
        is_paid=False,
    )
    create_uncomplete_transactions_for_orders([order])

    transaction = Transaction.objects.get(related_object_identifier=order.identifier)
    assert transaction.amount == 100
    assert transaction.currency_id == country.currency_id

    order.total_price = 200
    order.save()

    transaction.refresh_from_db()
    assert transaction.amount == 200
    assert transaction.currency_id == country.currency_id


@pytest.mark.django_db
def test_real_fields_setting_when_customer_creates_order(
    dummy_conf, rich_customer, order_factory, country_factory
):
    country = country_factory(code="US")
    order = order_factory(
        user=rich_customer,
        product_price=100,
        cargo_price=50,
        source_country=country,
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
        is_paid=False,
    )

    assert order.real_product_price == 100
    assert order.real_cargo_price == 50


@pytest.mark.django_db
def test_real_fields_updating_when_customer_updates_order(
    dummy_conf, rich_customer, order_factory, country_factory
):
    country = country_factory(code="US")
    order = order_factory(
        user=rich_customer,
        product_price=100,
        cargo_price=50,
        source_country=country,
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
        is_paid=False,
    )

    order.product_price = 200
    order.save()

    assert order.real_product_price == 200
    assert order.real_cargo_price == 50


@pytest.mark.django_db
def test_preventing_real_price_updating_when_paid_order_updated(
    dummy_conf, rich_customer, order_factory, country_factory
):
    country = country_factory(code="US")
    order = order_factory(
        user=rich_customer,
        product_price=100,
        cargo_price=50,
        source_country=country,
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
        is_paid=True,
    )

    order.product_price = 200000
    order.save()

    assert order.real_product_price == 100
    assert order.real_cargo_price == 50
