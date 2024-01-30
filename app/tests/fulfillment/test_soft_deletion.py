import pytest

from fulfillment.models import Transaction
from core.converter import Converter


@pytest.mark.django_db
def test_soft_deleting_of_incomplete_transaction(simple_customer, transaction_factory):
    tr = transaction_factory(user=simple_customer, completed=False)
    tr.delete()

    assert tr.deleted_at is not None
    assert not Transaction.objects.filter(pk=tr.pk).exists()


@pytest.mark.django_db
def test_soft_deleting_of_complete_transaction(simple_customer, transaction_factory):
    tr = transaction_factory(user=simple_customer, completed=True)
    tr.delete()

    assert tr.deleted_at is None, "Complete transaction must not be deleted"
    assert Transaction.objects.filter(pk=tr.pk).exists()


@pytest.mark.django_db
def test_soft_deletion_of_incomplete_child_transaction(
    simple_customer, transaction_factory, usd
):
    parent = transaction_factory(
        user=simple_customer, amount=400, completed=False, currency=usd
    )
    child1 = transaction_factory(
        parent=parent, user=simple_customer, completed=False, amount=100, currency=usd
    )
    child2 = transaction_factory(
        parent=parent, user=simple_customer, completed=False, amount=170, currency=usd
    )
    child3 = transaction_factory(
        parent=parent, user=simple_customer, completed=False, amount=130, currency=usd
    )
    old_parent_amount = parent.amount
    child1.delete()
    parent.refresh_from_db()
    new_parent_amount = parent.amount
    assert new_parent_amount == old_parent_amount - child1.amount
    assert parent.children.count() == 2


@pytest.mark.django_db
def test_soft_deleting_one_of_two_child_transactions(
    simple_customer, transaction_factory
):
    parent = transaction_factory(user=simple_customer, completed=False)
    child1 = transaction_factory(parent=parent, user=simple_customer, completed=False)
    child2 = transaction_factory(parent=parent, user=simple_customer, completed=False)
    child1.delete()
    parent.refresh_from_db()
    child2.refresh_from_db()
    assert parent.deleted_at is not None
    assert child2.parent is None
