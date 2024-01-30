import pytest

from domain.services import (
    create_uncomplete_transactions_for_orders,
    complete_payments,
    merge_transactions,
    transactions_are_mergable,
    make_objects_paid,
)
from domain.exceptions.payment import PaymentError
from fulfillment.models import Notification, Transaction, Status


@pytest.mark.django_db
def test_create_uncomplete_transaction_for_one_order(
    dummy_conf, simple_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=simple_customer, total_price=100, total_price_currency=usd
    )

    transactions = create_uncomplete_transactions_for_orders([order])

    assert len(transactions) == 1, "Only one transaction must be created!"

    transaction = transactions[0]

    assert transaction.amount == order.total_price, "Amount must be order.total_price"
    assert (
        transaction.currency_id == order.total_price_currency_id
    ), "Currency must be order.total_price_currency"
    assert transaction.completed == False

    assert transaction.related_object_identifier == order.identifier
    assert transaction.related_object == order

    assert transaction.purpose == Transaction.ORDER_PAYMENT
    assert transaction.type == transaction.BALANCE


@pytest.mark.django_db
def test_create_uncomplete_transactions_for_multiple_orders(
    dummy_conf, simple_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    lira = currency_factory(code="TRY")
    orders = [
        order_factory(user=simple_customer, total_price=100, total_price_currency=usd),
        order_factory(user=simple_customer, total_price=200, total_price_currency=lira),
    ]

    transactions = create_uncomplete_transactions_for_orders(orders)

    assert len(transactions) == 2, "One transaction per order must be created"


@pytest.mark.django_db
def test_pay_order_transaction_by_balance(
    dummy_conf, rich_customer, order_factory, currency_factory
):
    usd = currency_factory(code="USD")
    order = order_factory(
        user=rich_customer,
        total_price=100,
        total_price_currency=usd,
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
    )

    old_balance_amount = rich_customer.active_balance.amount
    transaction = create_uncomplete_transactions_for_orders([order])[0]
    complete_payments([transaction])

    rich_customer.active_balance.refresh_from_db()
    assert old_balance_amount - rich_customer.active_balance.amount == order.total_price

    transaction.refresh_from_db()
    assert transaction.completed == True

    order.refresh_from_db()
    assert order.is_paid == True


@pytest.mark.django_db
def test_pay_multiple_transactions_by_balance(
    rich_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")
    transaction1 = transaction_factory(
        user=rich_customer, amount=100, completed=False, currency=usd
    )
    transaction2 = transaction_factory(
        user=rich_customer, amount=150, completed=False, currency=usd
    )

    old_balance = rich_customer.active_balance.amount

    transaction = complete_payments(
        [transaction1, transaction2], override_type=Transaction.BALANCE
    )

    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount

    assert new_balance == old_balance - 100 - 150

    assert Transaction.objects.count() == 3, "Merge transaction was not created"

    # Test created merge transaction
    assert transaction.purpose == Transaction.MERGED
    assert transaction.amount == 250
    assert transaction.currency == usd
    assert transaction.children.count() == 2


@pytest.mark.django_db
def test_pay_already_merged_transction(
    rich_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")
    transaction = transaction_factory(
        purpose=Transaction.MERGED,
        completed=False,
        amount=100,
        currency=usd,
        user=rich_customer,
    )
    old_balance = rich_customer.active_balance.amount

    result = complete_payments([transaction], override_type=Transaction.BALANCE)

    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount
    assert new_balance == old_balance - 100

    assert result.id == transaction.id


@pytest.mark.django_db
def test_pay_child_of_merged_transaction(
    rich_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")
    parent = transaction_factory(
        user=rich_customer,
        completed=False,
        purpose=Transaction.MERGED,
        amount=150,
        currency=usd,
    )

    child1 = transaction_factory(
        parent=parent, currency=usd, amount=50, user=rich_customer, completed=False
    )
    child2 = transaction_factory(
        parent=parent, currency=usd, amount=50, user=rich_customer, completed=False
    )
    child3 = transaction_factory(
        parent=parent, currency=usd, amount=50, user=rich_customer, completed=False
    )

    old_balance = rich_customer.active_balance.amount
    completed_transaction = complete_payments(
        [child1], override_type=Transaction.BALANCE
    )
    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount

    child1.refresh_from_db()
    assert child1.completed == True
    assert child1.parent is None

    child2.refresh_from_db()
    child3.refresh_from_db()
    assert child2.parent_id == parent.id
    assert child3.parent_id == parent.id

    assert new_balance == old_balance - 50

    parent.refresh_from_db()
    assert parent.amount == 100
    assert parent.completed == False


@pytest.mark.django_db
def test_pay_child_of_merged_transaction_and_then_complete_the_parent(
    rich_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")
    parent = transaction_factory(
        user=rich_customer,
        completed=False,
        purpose=Transaction.MERGED,
        amount=150,
        currency=usd,
    )

    child1 = transaction_factory(
        parent=parent, currency=usd, amount=50, user=rich_customer, completed=False
    )
    child2 = transaction_factory(
        parent=parent, currency=usd, amount=50, user=rich_customer, completed=False
    )
    child3 = transaction_factory(
        parent=parent, currency=usd, amount=50, user=rich_customer, completed=False
    )

    completed_child = complete_payments([child1], override_type=Transaction.BALANCE)

    old_balance = rich_customer.active_balance.amount

    completed_parent = complete_payments([parent], override_type=Transaction.BALANCE)

    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount

    assert new_balance == old_balance - 100


@pytest.mark.django_db
def test_pay_single_transaction(rich_customer, transaction_factory, currency_factory):
    usd = currency_factory(code="USD")
    transaction = transaction_factory(
        user=rich_customer, currency=usd, amount=100, completed=False
    )

    old_balance = rich_customer.active_balance.amount
    complete_payments([transaction], override_type=Transaction.BALANCE)

    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount

    assert new_balance == old_balance - 100


@pytest.mark.django_db
def test_pay_single_completed_transaction(
    rich_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")
    transaction = transaction_factory(
        user=rich_customer, currency=usd, amount=100, completed=True
    )
    old_balance = rich_customer.active_balance.amount

    with pytest.raises(PaymentError):
        complete_payments([transaction], override_type=Transaction.BALANCE)

    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount

    assert new_balance == old_balance, "Subtracted completed transaction amount"


@pytest.mark.django_db
def test_related_objects_completion_of_merged_transactions(
    rich_customer, transaction_factory, currency_factory, order_factory, dummy_conf
):
    usd = currency_factory(code="USD")

    order1 = order_factory(
        user=rich_customer,
        is_paid=False,
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
    )
    child1 = transaction_factory(
        user=rich_customer,
        related_object=order1,
        amount=100,
        currency=usd,
        completed=False,
    )
    order2 = order_factory(
        user=rich_customer,
        is_paid=False,
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
    )
    child2 = transaction_factory(
        user=rich_customer,
        related_object=order2,
        amount=100,
        currency=usd,
        completed=False,
    )

    parent = complete_payments([child1, child2], override_type=Transaction.BALANCE)

    order1.refresh_from_db()
    order2.refresh_from_db()

    assert order1.is_paid == True
    assert order1.paid_amount == order1.total_price
    assert order2.is_paid == True
    assert order2.paid_amount == order2.total_price


@pytest.mark.django_db
def test_pay_nested_merged_transactions_with_related_objects(
    rich_customer, order_factory, transaction_factory, currency_factory, dummy_conf
):
    usd = currency_factory(code="USD")
    parent = transaction_factory(
        amount=250, currency=usd, completed=False, user=rich_customer
    )
    order1 = order_factory(
        user=rich_customer,
        is_paid=False,
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
    )
    child1 = transaction_factory(
        user=rich_customer,
        related_object=order1,
        amount=100,
        currency=usd,
        completed=False,
        parent=parent,
    )
    order2 = order_factory(
        user=rich_customer,
        is_paid=False,
        status=Status.objects.get(type=Status.ORDER_TYPE, codename="created"),
    )
    child2 = transaction_factory(
        user=rich_customer,
        related_object=order2,
        amount=150,
        currency=usd,
        completed=False,
        parent=parent,
    )

    another_transaction = transaction_factory(
        user=rich_customer, amount=200, currency=usd, completed=False
    )

    old_balance = rich_customer.active_balance.amount

    complete_payments([another_transaction, parent], override_type=Transaction.BALANCE)

    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount

    assert new_balance == old_balance - 250 - 200

    # Test that related objects are completed :)
    orders = [order1, order2]
    is_paid_results = []
    for order in orders:
        order.refresh_from_db()
        is_paid_results += [order.is_paid]

    print(orders)
    print(is_paid_results)
    assert all(is_paid_results), "Nested related objects are not completed"


@pytest.mark.django_db
def test_complete_children_of_irrelevant_merged_transactions(
    rich_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")

    # First group
    parent1 = transaction_factory(
        amount=75, currency=usd, completed=False, user=rich_customer
    )
    child1_1 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent1
    )
    child1_2 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent1
    )
    child1_3 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent1
    )

    # Second group
    parent2 = transaction_factory(
        amount=75, currency=usd, completed=False, user=rich_customer
    )
    child2_1 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent2
    )
    child2_2 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent2
    )
    child2_3 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent2
    )

    new_parent = complete_payments(
        [child1_1, child2_1], override_type=Transaction.BALANCE
    )

    parent1.refresh_from_db()
    parent2.refresh_from_db()
    child1_1.refresh_from_db()
    child2_1.refresh_from_db()

    assert child1_1.parent_id == new_parent.id
    assert child2_1.parent_id == new_parent.id

    assert parent1.children.count() == 2, "Only two children must be left"
    assert parent2.children.count() == 2, "Only two children must be left"

    assert parent1.amount == 50, "Amount of old parent must be decreased"
    assert parent2.amount == 50, "Amount of old parent must be decreased"

    assert new_parent.amount == 50


@pytest.mark.django_db
def test_complete_children_of_irrevelevant_merged_transaction_and_removing_parent_of_orphaned_child(
    rich_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")

    # First group
    parent1 = transaction_factory(
        amount=50, currency=usd, completed=False, user=rich_customer
    )
    child1_1 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent1
    )
    child1_2 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent1
    )

    # Second group
    parent2 = transaction_factory(
        amount=50, currency=usd, completed=False, user=rich_customer
    )
    child2_1 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent2
    )
    child2_2 = transaction_factory(
        amount=25, currency=usd, completed=False, user=rich_customer, parent=parent2
    )

    new_parent = complete_payments(
        [child1_1, child2_1], override_type=Transaction.BALANCE
    )

    child1_1.refresh_from_db()

    # Just in case)
    assert child1_1.parent_id == new_parent.id

    # Old parents transaction must be deleted
    # because only one children left for them
    parent1.refresh_from_db()
    parent2.refresh_from_db()

    assert parent1.is_deleted == True
    assert parent2.is_deleted == True

    # Their children must not exist now...
    assert parent1.children.exists() == False
    assert parent2.children.exists() == False


def _merge_transactions(transactions):
    _, type_, currency_id, user_id = transactions_are_mergable(
        transactions, override_type=Transaction.BALANCE
    )
    parent = merge_transactions(user_id, type_, currency_id, transactions)
    return parent


@pytest.mark.django_db
def test_remerge_children_of_merged_transaction(
    rich_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")

    child1 = transaction_factory(
        user=rich_customer, currency=usd, amount=25, completed=False
    )
    child2 = transaction_factory(
        user=rich_customer, currency=usd, amount=25, completed=False
    )

    parent = _merge_transactions([child1, child2])

    # Now merge again
    child1.refresh_from_db()
    child2.refresh_from_db()
    new_parent = _merge_transactions([child1, child2])
    child1.refresh_from_db()
    child2.refresh_from_db()

    parent.refresh_from_db()
    assert parent.is_deleted == True
    assert parent.children.exists() == False
    assert child1.parent_id == new_parent.id
    assert child2.parent_id == new_parent.id


@pytest.mark.django_db
def test_pay_child_transaction_along_with_its_parent(
    rich_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")

    parent = transaction_factory(
        user=rich_customer, currency=usd, amount=100, completed=False
    )
    child1 = transaction_factory(
        user=rich_customer, currency=usd, amount=50, completed=False, parent=parent
    )
    child2 = transaction_factory(
        user=rich_customer, currency=usd, amount=50, completed=False, parent=parent
    )

    assert Transaction.objects.count() == 3

    old_balance = rich_customer.active_balance.amount

    completed_transaction = complete_payments(
        [parent, child1], override_type=Transaction.BALANCE
    )

    rich_customer.active_balance.refresh_from_db()
    new_balance = rich_customer.active_balance.amount

    assert new_balance == old_balance - 100

    assert Transaction.objects.count() == 3

    child1.refresh_from_db()
    child2.refresh_from_db()
    parent.refresh_from_db()

    assert parent.id == completed_transaction.id
    assert child1.completed == True
    assert child2.completed == True
    assert child1.parent_id == parent.id


@pytest.mark.django_db
def test_make_single_shipment_paid(
    simple_customer, shipment_factory, transaction_factory
):
    shipment = shipment_factory(user=simple_customer, is_paid=False)
    transaction = transaction_factory(
        user=simple_customer,
        related_object=shipment,
        completed=False,
    )

    make_objects_paid([shipment])

    shipment.refresh_from_db()
    transaction.refresh_from_db()

    assert shipment.is_paid == True
    assert transaction.completed == True
    assert transaction.completed_manually == True


@pytest.mark.django_db
def test_make_single_shipment_paid_with_one_deleted_transactions(
    shipment_factory, transaction_factory, simple_customer
):
    shipment = shipment_factory(user=simple_customer, is_paid=False)
    t_nice = transaction_factory(
        user=simple_customer, related_object=shipment, completed=False
    )
    t_bad = transaction_factory(
        related_object=shipment, completed=False, is_deleted=True, user=simple_customer
    )

    make_objects_paid([shipment])

    t_nice.refresh_from_db()
    t_bad.refresh_from_db()

    assert t_nice.completed == True
    assert t_nice.completed_manually == True
    assert t_bad.completed == False, "Deleted transaction must not be altered"
    assert t_bad.completed_manually == False, "Deleted transaction must not be altered"


@pytest.mark.django_db
def test_make_multiple_shipment_paid(
    shipment_factory, transaction_factory, simple_customer
):
    all_shipments = []
    all_transactions = []

    for i in range(3):
        shipment = shipment_factory(is_paid=False, user=simple_customer)
        transaction = transaction_factory(
            user=simple_customer,
            related_object=shipment,
            completed=False,
        )
        all_shipments.append(shipment)
        all_transactions.append(transaction)

    make_objects_paid(all_shipments)

    for s, t in zip(all_shipments, all_transactions):
        s.refresh_from_db()
        t.refresh_from_db()

    assert all([s.is_paid for s in all_shipments])
    assert all([t.completed for t in all_transactions])
    assert all([t.completed_manually for t in all_transactions])


@pytest.mark.django_db
def test_make_single_object_paid_with_multiple_transactions(
    order_factory, transaction_factory, dummy_conf, simple_customer
):
    order = order_factory(is_paid=True, user=simple_customer)
    tr1 = transaction_factory(
        related_object=order, completed=False, user=simple_customer
    )
    tr2 = transaction_factory(
        related_object=order, completed=False, user=simple_customer
    )

    make_objects_paid([order])

    order.refresh_from_db()
    tr1.refresh_from_db()
    tr2.refresh_from_db()

    assert order.is_paid == True
    assert tr1.completed == True
    assert tr2.completed == True
    assert tr1.completed_manually == True
    assert tr2.completed_manually == True


@pytest.mark.django_db
def test_balance_addition_using_transaction(
    simple_customer, transaction_factory, currency_factory
):
    usd = currency_factory(code="USD")
    t = transaction_factory(
        user=simple_customer,
        amount=100,
        currency=usd,
        purpose=Transaction.BALANCE_INCREASE,
        type=Transaction.CASH,
        completed=False,
    )
    old_balance = simple_customer.active_balance.amount
    complete_payments([t])
    simple_customer.active_balance.refresh_from_db()
    new_balance = simple_customer.active_balance.amount

    assert new_balance == old_balance + 100
