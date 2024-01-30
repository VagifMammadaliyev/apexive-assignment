import pytest

from fulfillment.models import Transaction
from domain.services import complete_payments


@pytest.mark.django_db
def test_cashback_transaction(transaction_factory, rich_customer):
    transaction = transaction_factory(
        user=rich_customer,
        purpose=Transaction.ORDER_PAYMENT,
        type=Transaction.BALANCE,
        amount=100,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    cashback_transaction = transaction_factory(
        user=rich_customer,
        cashback_to=transaction,
        purpose=Transaction.CASHBACK,
        type=Transaction.BALANCE,
        amount=5,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    old_balance_amount = rich_customer.active_balance.amount
    complete_payments([transaction])
    rich_customer.active_balance.refresh_from_db()
    new_balance_amount = rich_customer.active_balance.amount

    assert new_balance_amount == old_balance_amount - 100 + 5


@pytest.mark.django_db
def test_multiple_cashback_transaction(transaction_factory, rich_customer):
    transaction = transaction_factory(
        user=rich_customer,
        purpose=Transaction.ORDER_PAYMENT,
        type=Transaction.BALANCE,
        amount=100,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    transaction_factory.create_batch(
        4,
        user=rich_customer,
        cashback_to=transaction,
        purpose=Transaction.CASHBACK,
        type=Transaction.BALANCE,
        amount=5,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )
    # and one completed transaction, this must not count
    transaction_factory(
        user=rich_customer,
        cashback_to=transaction,
        purpose=Transaction.CASHBACK,
        type=Transaction.BALANCE,
        amount=5,
        currency=rich_customer.active_balance.currency,
        completed=True,
    )

    print(Transaction.objects.all())

    old_balance_amount = rich_customer.active_balance.amount
    complete_payments([transaction])
    rich_customer.active_balance.refresh_from_db()
    new_balance_amount = rich_customer.active_balance.amount

    assert new_balance_amount == old_balance_amount - 100 + 4 * 5


@pytest.mark.django_db
def test_cashbackable_amount_with_one_cashback(transaction_factory, rich_customer):
    transaction = transaction_factory(
        user=rich_customer,
        purpose=Transaction.SHIPMENT_PAYMENT,
        type=Transaction.BALANCE,
        amount=100,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    transaction_factory(
        user=rich_customer,
        cashback_to=transaction,
        purpose=Transaction.CASHBACK,
        type=Transaction.BALANCE,
        amount=5,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    assert transaction.cashbackable_amount == 95


@pytest.mark.django_db
def test_cashbackable_amount_with_two_cashbacks(transaction_factory, rich_customer):
    transaction = transaction_factory(
        user=rich_customer,
        purpose=Transaction.SHIPMENT_PAYMENT,
        type=Transaction.BALANCE,
        amount=100,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    transaction_factory(
        user=rich_customer,
        cashback_to=transaction,
        purpose=Transaction.CASHBACK,
        type=Transaction.BALANCE,
        amount=5,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )
    transaction_factory(
        user=rich_customer,
        cashback_to=transaction,
        purpose=Transaction.CASHBACK,
        type=Transaction.BALANCE,
        amount=10,
        currency=rich_customer.active_balance.currency,
        completed=True,  # this must not matter
    )

    assert transaction.cashbackable_amount == 85


@pytest.mark.django_db
def test_single_cashback_completed_field_after_completing(
    transaction_factory, rich_customer
):
    transaction = transaction_factory(
        user=rich_customer,
        purpose=Transaction.SHIPMENT_PAYMENT,
        type=Transaction.BALANCE,
        amount=100,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    cb_transaction = transaction_factory(
        user=rich_customer,
        cashback_to=transaction,
        purpose=Transaction.CASHBACK,
        type=Transaction.BALANCE,
        amount=5,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    complete_payments([transaction], override_type=Transaction.BALANCE)

    cb_transaction.refresh_from_db()
    assert cb_transaction.completed == True


@pytest.mark.django_db
def test_multiple_cashback_completed_field_after_completing(
    transaction_factory, rich_customer
):
    transaction = transaction_factory(
        user=rich_customer,
        purpose=Transaction.SHIPMENT_PAYMENT,
        type=Transaction.BALANCE,
        amount=100,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    cb1 = transaction_factory(
        user=rich_customer,
        cashback_to=transaction,
        purpose=Transaction.CASHBACK,
        type=Transaction.BALANCE,
        amount=5,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )
    cb2 = transaction_factory(
        user=rich_customer,
        cashback_to=transaction,
        purpose=Transaction.CASHBACK,
        type=Transaction.BALANCE,
        amount=5,
        currency=rich_customer.active_balance.currency,
        completed=False,
    )

    complete_payments([transaction], override_type=Transaction.BALANCE)

    cb1.refresh_from_db()
    cb2.refresh_from_db()
    assert cb1.completed == True
    assert cb2.completed == True
