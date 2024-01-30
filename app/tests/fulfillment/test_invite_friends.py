from decimal import Decimal

import pytest

from domain.services import (
    generate_promo_code,
    can_get_promo_code_cashbacks,
    complete_payments,
    get_consumers_for_promo_code,
)
from domain.exceptions.customer import InvalidPromoCode
from fulfillment.models import PromoCode, Transaction
from fulfillment.tasks import apply_cashbacks_to_promo_code_owner_task


@pytest.mark.django_db
def test_generate_promo_code(simple_customer):
    promo_code = generate_promo_code(simple_customer)

    assert isinstance(promo_code, PromoCode)
    assert len(promo_code.value) == 7
    assert promo_code.pk


@pytest.mark.django_db
def test_regenerate_promo_code(simple_customer):
    promo_code = generate_promo_code(simple_customer)
    new_promo_code = generate_promo_code(simple_customer)

    assert promo_code.pk == new_promo_code.pk


@pytest.mark.django_db
def test_registering_to_someones_promo_code(simple_customer, promo_code_factory):
    promo_code = promo_code_factory()
    promo_code.register(simple_customer)

    assert can_get_promo_code_cashbacks(simple_customer) == True


def create_shipment_with_transaction(
    customer, shipment_factory, transaction_factory, currency, pay_it=False
):
    shipment = shipment_factory(user=customer, is_paid=False)
    transaction = transaction_factory(
        user=customer,
        related_object=shipment,
        amount=100,
        currency=currency,
        completed=False,
    )

    if pay_it:
        complete_payments([transaction], override_type=Transaction.BALANCE)

    shipment.refresh_from_db()
    transaction.refresh_from_db()

    return shipment, transaction


@pytest.mark.django_db
def test_can_get_promo_code_cashbacks(
    rich_customer, promo_code_factory, shipment_factory, transaction_factory, usd
):
    promo_code = promo_code_factory()
    promo_code.register(rich_customer)

    shipment, transaction = create_shipment_with_transaction(
        rich_customer, shipment_factory, transaction_factory, usd, pay_it=True
    )
    assert can_get_promo_code_cashbacks(rich_customer) == True


@pytest.mark.django_db
def test_can_get_promo_code_cashbacks_after_using_all_benefits(
    rich_customer, promo_code_factory, shipment_factory, transaction_factory, usd
):
    promo_code = promo_code_factory()
    promo_code.register(rich_customer)

    create_shipment_with_transaction(
        rich_customer, shipment_factory, transaction_factory, usd, pay_it=True
    )
    create_shipment_with_transaction(
        rich_customer, shipment_factory, transaction_factory, usd, pay_it=True
    )
    assert can_get_promo_code_cashbacks(rich_customer) == False


@pytest.mark.django_db
def test_absolutely_inactive_invited_friend(
    dummy_conf, simple_customer, promo_code_factory
):
    promo_code = promo_code_factory()
    promo_code.register(simple_customer)
    assert promo_code.get_next_cashback() is None


@pytest.mark.django_db
def test_inactive_invited_friend(
    dummy_conf,
    transaction_factory,
    simple_customer,
    shipment_factory,
    promo_code_factory,
    usd,
):
    promo_code = promo_code_factory()
    promo_code.register(simple_customer)
    shipment = shipment_factory(user=simple_customer)
    transaction = transaction_factory(
        user=simple_customer,
        related_object=shipment,
        amount=100,
        currency=usd,
        completed=False,
    )
    assert promo_code.get_next_cashback() is None


@pytest.mark.django_db
def test_semiactive_invited_friend(
    dummy_conf,
    rich_customer,
    promo_code_factory,
    shipment_factory,
    transaction_factory,
    usd,
):
    promo_code = promo_code_factory()
    promo_code.register(rich_customer)

    shipment = shipment_factory(user=rich_customer)
    transaction = transaction_factory(
        user=rich_customer,
        related_object=shipment,
        amount=100,
        currency=usd,
        completed=False,
    )

    complete_payments([transaction])
    cb = promo_code.get_next_cashback()

    assert cb is not None
    # in our case cashback currency is usd so it is okay not to convert
    assert cb.amount == transaction.discounted_amount * (
        dummy_conf.invite_friend_cashback_percentage / Decimal("100.0")
    )


@pytest.mark.django_db
def test_active_invited_friend(
    dummy_conf,
    rich_customer,
    promo_code_factory,
    shipment_factory,
    transaction_factory,
    usd,
):
    promo_code = promo_code_factory()
    promo_code.register(rich_customer)

    transactions = []
    for i in range(2):
        shipment = shipment_factory(user=rich_customer)
        transaction = transaction_factory(
            user=rich_customer,
            related_object=shipment,
            amount=100,
            currency=usd,
            completed=False,
        )
        transactions.append(transaction)

    complete_payments(transactions)

    cb1 = promo_code.get_next_cashback()
    cb2 = promo_code.get_next_cashback()

    assert cb1 is not None
    assert cb2 is not None
    assert cb1 == cb2
    assert cb1.amount == transactions[0].discounted_amount * (
        dummy_conf.invite_friend_cashback_percentage / Decimal("100")
    )


@pytest.mark.django_db
def test_over_active_invited_friend(
    dummy_conf,
    rich_customer,
    promo_code_factory,
    shipment_factory,
    transaction_factory,
    usd,
):
    promo_code = promo_code_factory()
    promo_code.register(rich_customer)

    transactions = []
    for i in range(3):
        shipment = shipment_factory(user=rich_customer)
        transaction = transaction_factory(
            user=rich_customer,
            related_object=shipment,
            amount=100,
            currency=usd,
            completed=False,
        )
        transactions.append(transaction)

    complete_payments(transactions)

    cb1 = promo_code.get_next_cashback()
    cb2 = promo_code.get_next_cashback()
    cb3 = promo_code.get_next_cashback()

    assert cb1 == cb2, "First two cashbacks must be the same due to test logic"
    assert cb3 is None, "Only two cashback at max for each invited friend"


@pytest.mark.django_db
def test_multiple_invited_friends(
    dummy_conf,
    rich_customer,
    simple_customer,
    promo_code_factory,
    shipment_factory,
    transaction_factory,
    usd,
):
    simple_customer.active_balance.amount = 1000
    simple_customer.active_balance.save()

    promo_code = promo_code_factory()
    promo_code.register(rich_customer)
    promo_code.register(simple_customer)

    transactions1 = []
    for i in range(2):
        shipment = shipment_factory(user=rich_customer)
        transaction = transaction_factory(
            user=rich_customer,
            related_object=shipment,
            amount=100,
            currency=usd,
            completed=False,
        )
        transactions1.append(transaction)

    transactions2 = []
    for i in range(2):
        shipment = shipment_factory(user=simple_customer)
        transaction = transaction_factory(
            user=simple_customer,
            related_object=shipment,
            amount=100,
            currency=usd,
            completed=False,
        )
        transactions2.append(transaction)

    complete_payments(transactions1)
    complete_payments(transactions2)

    cb1 = promo_code.get_next_cashback()
    cb2 = promo_code.get_next_cashback()
    cb3 = promo_code.get_next_cashback()
    cb4 = promo_code.get_next_cashback()

    assert cb1 == cb2 == cb3 == cb4


@pytest.mark.django_db
def test_use_registered_promo_code(
    dummy_conf, simple_customer, promo_code_factory, shipment_factory, usd
):
    promo_code = promo_code_factory()
    promo_code.register(simple_customer)

    shipment = shipment_factory(user=simple_customer)
    cashbacks = shipment.get_appliable_cashbacks()

    assert cashbacks and len(cashbacks) == 1
    cb = cashbacks[0]
    assert cb.percentage == dummy_conf.invite_friend_cashback_percentage


@pytest.mark.django_db
def test_overuse_registered_promo_code(
    dummy_conf, simple_customer, promo_code_factory, shipment_factory, usd
):
    promo_code = promo_code_factory()
    promo_code.register(simple_customer)

    shipment = shipment_factory(user=simple_customer)
    cashbacks = shipment.get_appliable_cashbacks()
    assert len(cashbacks) == 1

    shipment1 = shipment_factory(user=simple_customer)
    cashbacks = shipment1.get_appliable_cashbacks()
    assert len(cashbacks) == 1

    shipment2 = shipment_factory(user=simple_customer)
    cashbacks = shipment2.get_appliable_cashbacks()
    assert len(cashbacks) == 0

    shipment3 = shipment_factory(user=simple_customer)
    cashbacks = shipment3.get_appliable_cashbacks()
    assert len(cashbacks) == 0


@pytest.mark.django_db
def test_discounts_for_unregistered_model_in_configuration(
    dummy_conf, simple_customer, promo_code_factory, order_factory, usd
):
    promo_code = promo_code_factory()
    promo_code.register(simple_customer)

    order = order_factory(user=simple_customer)
    cashbacks = order.get_appliable_cashbacks()
    assert len(cashbacks) == 0


@pytest.mark.django_db
def test_register_to_inactive_users_promo_code(simple_customer, promo_code_factory):
    promo_code = promo_code_factory(user__is_active=False)

    with pytest.raises(InvalidPromoCode):
        promo_code.register(simple_customer)


@pytest.mark.django_db
def test_balance_cashback_when_registered_with_promo_code(
    rich_customer,
    shipment_factory,
    usd,
    dummy_conf,
    transaction_factory,
    promo_code_factory,
):
    promo_code = promo_code_factory()
    promo_code.register(rich_customer)

    shipment = shipment_factory(user=rich_customer, is_paid=False)
    transaction = transaction_factory(
        currency=usd,
        amount=100,
        related_object=shipment,
        completed=False,
        user=rich_customer,
    )

    old_balance = rich_customer.active_balance.amount
    complete_payments([transaction], override_type=Transaction.BALANCE)
    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount

    assert new_balance == old_balance - Decimal("100") + Decimal("100") * (
        dummy_conf.invite_friend_cashback_percentage / Decimal("100")
    ), "Cashback not applied to consumers balance"

    assert rich_customer.transactions.filter(
        purpose=Transaction.CASHBACK
    ).exists(), "Cashback transaction not created"


@pytest.mark.django_db
def test_balance_cashback_for_promo_code_owner(
    rich_customer,
    shipment_factory,
    usd,
    dummy_conf,
    transaction_factory,
    promo_code_factory,
    celery_app,
):
    promo_code = promo_code_factory()
    promo_code.register(rich_customer)

    shipment = shipment_factory(user=rich_customer, is_paid=False)
    transaction = transaction_factory(
        currency=usd,
        amount=100,
        related_object=shipment,
        completed=False,
        user=rich_customer,
    )
    owner = promo_code.user
    old_balance = owner.active_balance.amount
    completed_transaction = complete_payments(
        [transaction], override_type=Transaction.BALANCE
    )
    apply_cashbacks_to_promo_code_owner_task(completed_transaction.id)
    owner.active_balance.refresh_from_db()
    new_balance = owner.active_balance.amount

    assert new_balance == old_balance + Decimal("100") * (
        dummy_conf.invite_friend_cashback_percentage / Decimal("100")
    ), "Cashback not applied to promo code owner"
    assert owner.transactions.filter(
        purpose=Transaction.CASHBACK, cashback_to__isnull=True
    ).exists(), "Cashback transaction is not created for owner"


@pytest.mark.django_db
def test_cashback_total_amount_for_promo_code_owner(
    rich_customer,
    shipment_factory,
    usd,
    dummy_conf,
    transaction_factory,
    promo_code_factory,
    celery_app,
):
    promo_code = promo_code_factory()
    promo_code.register(rich_customer)

    shipment = shipment_factory(user=rich_customer, is_paid=False)
    transaction = transaction_factory(
        currency=usd,
        amount=100,
        related_object=shipment,
        completed=False,
        user=rich_customer,
    )
    owner = promo_code.user
    old_balance = owner.active_balance.amount
    completed_transaction = complete_payments(
        [transaction], override_type=Transaction.BALANCE
    )
    apply_cashbacks_to_promo_code_owner_task(completed_transaction.id)

    consumers = get_consumers_for_promo_code(promo_code=promo_code)
    consumer = consumers[0]
    assert consumer.total_cashback_amount == Decimal("100") * (
        dummy_conf.invite_friend_cashback_percentage / Decimal("100")
    )
    assert consumer.used_benefits == 1


@pytest.mark.django_db
def test_cashback_updating_after_changing_transaction_amount(
    transaction_factory, usd, rich_customer
):
    transaction = transaction_factory(
        user=rich_customer,
        currency=usd,
        amount=100,
        completed=False,
    )
    cb_trans = transaction_factory(
        user=rich_customer,
        currency=usd,
        amount=20,  # 5% of 100
        completed=False,
        cashback_to=transaction,
        extra={"invite_friend_cashback": True},
    )

    transaction.amount = 200
    transaction.save()
    cb_trans.refresh_from_db()

    assert cb_trans.amount == Decimal("40")


@pytest.mark.django_db
def test_already_complated_cashback_updating_after_changing_transaction_amount(
    transaction_factory, usd, rich_customer
):
    transaction = transaction_factory(
        user=rich_customer,
        currency=usd,
        amount=100,
        completed=False,
    )
    cb_trans = transaction_factory(
        user=rich_customer,
        currency=usd,
        amount=20,  # 5% of 100
        completed=True,
        cashback_to=transaction,
        extra={"invite_friend_cashback": True},
    )

    transaction.amount = 200
    transaction.save()
    cb_trans.refresh_from_db()

    assert cb_trans.amount == Decimal("20")


@pytest.mark.django_db
def test_non_invite_friend_cashback_updated_after_changing_transaction_amount(
    transaction_factory, usd, rich_customer
):
    transaction = transaction_factory(
        user=rich_customer,
        currency=usd,
        amount=100,
        completed=False,
    )
    cb_trans = transaction_factory(
        user=rich_customer,
        currency=usd,
        amount=20,  # 5% of 100
        completed=False,
        cashback_to=transaction,
        extra={"invite_friend_cashback": False},
    )

    transaction.amount = 200
    transaction.save()
    cb_trans.refresh_from_db()

    assert cb_trans.amount == Decimal("20")
