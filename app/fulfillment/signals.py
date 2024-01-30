from django.db.models import signals
from django.dispatch import receiver

from fulfillment.models import Shipment, Transaction, Order


@receiver(
    signals.post_save,
    sender=Order,
    dispatch_uid="order_update_related_transactions_uid",
)
def order_update_related_transactions(sender, instance, **kwargs):
    from domain.services import unmake_payment_partial

    order = instance
    related_transaction = Transaction.objects.filter(
        object_type__model="order",
        purpose=Transaction.ORDER_PAYMENT,
        object_id=order.id,
        completed=False,
        is_deleted=False,
    ).first()

    if not order.is_paid and related_transaction:
        unmake_payment_partial(related_transaction)
        related_transaction.currency_id = order.total_price_currency_id
        related_transaction.original_currency_id = order.total_price_currency_id
        related_transaction.amount = order.total_price
        related_transaction.original_amount = order.total_price
        related_transaction.related_object_identifier = order.identifier
        related_transaction.save()
