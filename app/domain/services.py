from typing import List, Union, TYPE_CHECKING, Optional, Iterable
import datetime
from collections import namedtuple
from decimal import Decimal, InvalidOperation
from itertools import groupby
from functools import partial
from json.decoder import JSONDecodeError

import redis
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry, CHANGE, DELETION, ContentType
from django.db import transaction as db_transaction
from django.db.models import F, Count, Q, Exists, Subquery, OuterRef, Prefetch, Sum
from django.utils import timezone, translation
from django.utils.translation import ugettext_lazy as _

from ontime import messages as msg
from customer.models import Role
from core.converter import Converter
from core.models import Country, Currency
from domain.exceptions.customer import InsufficientBalanceError
from domain.exceptions.logic import (
    DifferentPackageSourceError,
    InvalidActionError,
    AlreadyAcceptedPackageError,
    QueueError,
    NoQueueError,
    AcceptedInWrongWarehouseError,
    CourierError,
    CantPlaceCourierOrderError,
)
from domain.conf import Configuration
from domain.utils import (
    Invoice,
    MergedInvoice,
    InvoiceReason,
    QueueClient,
    Notification,
    VirtualOrder,
    NotificationEvent,
)
from domain.utils.cashback import Cashback
from domain.exceptions.payment import PaymentError
from domain.exceptions.customer import CantTopUpBalanceError
from cybersource.secure_acceptance import SecureAcceptanceClient
from ulduzum.client import UlduzumClient
from ulduzum.exceptions import UlduzumException
from fulfillment.tasks import (
    assign_orders_to_operator as assign_orders_to_operator_task,
    save_ordered_products_in_shipment,
    apply_cashbacks_to_promo_code_owner_task,
    commit_to_customs,
)
from fulfillment.models import (
    AdditionalService,
    PackageAdditionalService,
    PackageAdditionalServiceAttachment,
    ShipmentAdditionalService,
    ShipmentAdditionalServiceAttachment,
    Box,
    Order,
    Package,
    Product,
    Shipment,
    Status,
    TrackingStatus,
    StatusEvent,
    Transaction,
    Assignment,
    ShoppingAssistantProfile,
    Warehouse,
    WarehousemanProfile,
    CashierProfile,
    CustomerServiceProfile,
    Transportation,
    Queue,
    QueuedItem,
    Monitor,
    Ticket,
    NotificationEvent as EVENTS,
    CourierOrder,
    UserCountryLog,
    Discount,
    PromoCode,
    PromoCodeBenefit,
)

User = get_user_model()


def get_staff_user_data(staff_user, as_role=None):
    if as_role == Role.WAREHOUSEMAN:
        from fulfillment.serializers.admin.warehouseman import WarehousemanSerializer

        profile = getattr(staff_user, "warehouseman_profile", None)
        return profile and WarehousemanSerializer(profile).data

    if as_role == Role.SHOPPING_ASSISTANT:
        from fulfillment.serializers.admin.shopping_assistant import (
            ShoppingAssistantProfileSerializer,
        )

        profile = getattr(staff_user, "assistant_profile", None)
        return profile and ShoppingAssistantProfileSerializer(profile).data

    if as_role == Role.CASHIER:
        from fulfillment.serializers.admin.cashier import CashierProfileSerializer

        profile = getattr(staff_user, "cashier_profile", None)
        return profile and CashierProfileSerializer(profile).data

    if as_role == Role.CUSTOMER_SERVICE:
        from fulfillment.serializers.admin.customer_service import (
            CustomerServiceProfileSerializer,
        )

        profile = getattr(staff_user, "customer_service_profile", None)
        return profile and CustomerServiceProfileSerializer(profile).data

    if as_role == Role.MONITOR:
        from fulfillment.serializers.admin.queue import MonitorSerializer

        profile = getattr(staff_user, "as_monitor", None)
        return profile and MonitorSerializer(profile).data

    if as_role == Role.COURIER:
        from fulfillment.serializers.admin.courier import CourierProfileSerializer

        profile = getattr(staff_user, "courier_profile", None)
        return profile and CourierProfileSerializer(profile).data

    if as_role is None:
        worker_data = {}

        for role_type in filter(
            lambda t: t not in [Role.ADMIN, Role.USER], Role.FLAT_TYPES
        ):  # prevents recursion
            worker_data[role_type] = get_staff_user_data(staff_user, as_role=role_type)

        return worker_data

    return None


def get_staff_user_timezone(staff_user):
    timezone = None

    if staff_user.role_id and staff_user.role.type in [Role.WAREHOUSEMAN, Role.ADMIN]:
        warehouse = (
            getattr(staff_user, "warehouseman_profile", None)
            and staff_user.warehouseman_profile.warehouse
        )
        timezone = (
            warehouse
            and warehouse.city_id
            and warehouse.city.country_id
            and warehouse.city.country.timezone
        )

    return timezone or settings.TIME_ZONE


def complete_shopping_assistant_creation(*, user, role, staff_data):
    country_ids = staff_data.get("countries", None)
    profile, created = ShoppingAssistantProfile.objects.get_or_create(user=user)

    if country_ids:
        countries = Country.objects.filter(id__in=country_ids)
        profile.countries.set(countries)

    return profile


def complete_warehouseman_creation(*, user, role, staff_data):
    warehouse_id = staff_data.get("warehouse", None)
    warehouse = None

    if warehouse_id:
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id)
        except Warehouse.DoesNotExist:
            pass

    if warehouse:
        profile, created = WarehousemanProfile.objects.update_or_create(
            user=user, defaults={"warehouse": warehouse}
        )

        return profile

    return None


def complete_cashier_creation(*, user, role, staff_data):
    warehouse_id = staff_data.get("warehouse", None)
    warehouse = None

    if warehouse_id:
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id)
        except Warehouse.DoesNotExist:
            pass

    if warehouse:
        profile, created = CashierProfile.objects.update_or_create(
            user=user, defaults={"warehouse": warehouse}
        )

        return profile

    return None


def complete_customer_service_creation(*, user, role, staff_data):
    warehouse_id = staff_data.get("warehouse", None)
    warehouse = None

    if warehouse_id:
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id)
        except Warehouse.DoesNotExist:
            pass

    if warehouse:
        profile, created = CustomerServiceProfile.objects.update_or_create(
            user=user, defaults={"warehouse": warehouse}
        )

        return profile

    return None


# TODO: Rename this functions name
@db_transaction.atomic
def prepare_balance_add_form(
    customer, amount=None, currency: Currency = None, transaction: Transaction = None
):
    amount = amount or transaction.discounted_amount
    currency = currency or transaction.discounted_amount_currency

    if not check_if_customer_can_top_up_balance(
        customer, Transaction.CYBERSOURCE_SERVICE
    ):
        raise CantTopUpBalanceError

    try:
        amount = Decimal(amount)
    except (TypeError, InvalidOperation):
        raise PaymentError(human=msg.INVALID_AMOUNT_FORMAT)

    if amount <= 0:
        raise PaymentError(human=msg.AMOUNT_MUST_BE_BIGGER_THAN_ZERO)

    currency_code = currency.code

    try:
        # We must convert amount to currency supported by our cybersource profile
        currency = Currency.objects.get(code=settings.CYBERSOURCE_CURRENCY_CODE)
        amount = Converter.convert(
            amount, currency_code, settings.CYBERSOURCE_CURRENCY_CODE
        )
    except (Currency.DoesNotExist, AssertionError):
        raise PaymentError(human=msg.INVALID_CURRENCY)

    # Create uncomplete transaction for payment service
    transaction = (
        Transaction.objects.create(
            user=customer,
            currency=currency,
            amount=amount,
            purpose=Transaction.BALANCE_INCREASE,
            type=Transaction.CARD,
            payment_service=Transaction.CYBERSOURCE_SERVICE,
        )
        if not transaction
        else transaction
    )

    transaction_uuid = transaction.invoice_number
    secure_acceptance_client = SecureAcceptanceClient(
        transaction_uuid=transaction_uuid,
        reference_number=transaction.id,
        bill_address="%s, %s"
        % (
            customer.billed_recipient.city.name,
            customer.billed_recipient.region.title,
        ),
        bill_city=customer.billed_recipient.city.name,
        bill_country=customer.billed_recipient.city.country.code,
        customer_email=customer.email,
        customer_first_name=customer.first_name,
        customer_last_name=customer.last_name,
        amount=amount,
        currency_code=currency.code,
    )
    return secure_acceptance_client.get_form_data()


def unmake_payment_partial(transaction: Transaction):
    if transaction.is_partial:
        transaction.amount += Converter.convert(
            transaction.from_balance_amount,
            transaction.from_balance_currency.code,
            transaction.currency.code,
        )
        transaction.is_partial = False
        transaction.from_balance_amount = None
        transaction.from_balance_currency = None
        transaction.payment_service = None
        transaction.payment_service_responsed_at = None
        # If transaction was partial
        # then its type originally was BALANCE
        transaction.type = Transaction.BALANCE

        transaction.save(
            update_fields=[
                "type",
                "payment_service",
                "from_balance_amount",
                "from_balance_currency",
                "is_partial",
                "amount",
            ]
        )

    return transaction


def copy_transaction(transaction: Transaction, delete_old=True):
    """
    Copy the transaction.
    This is needed for payment services, they will not accept
    the cancelled transaction again + we take a log of cancelled transactions that way.
    """
    transaction_copy = Transaction.objects.create(
        user_id=transaction.user_id,
        currency_id=transaction.currency_id,
        parent_id=transaction.parent_id,
        amount=transaction.amount,
        purpose=transaction.purpose,
        type=transaction.type,
        related_object=transaction.related_object,
        related_object_identifier=transaction.related_object_identifier,
        completed=transaction.completed,
        completed_at=transaction.completed_at,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
        payment_service=transaction.payment_service,
        payment_service_responsed_at=transaction.payment_service_responsed_at,
        payment_service_response_json=transaction.payment_service_response_json,
        original_amount=transaction.original_amount,
        original_currency_id=transaction.original_currency_id,
        is_partial=transaction.is_partial,
        from_balance_amount=transaction.from_balance_amount,
        from_balance_currency=transaction.from_balance_currency,
        extra=transaction.extra,
        cashback_to_id=transaction.cashback_to_id,
    )

    for child in transaction.children.all():
        child.parent = transaction_copy
        child.save(update_fields=["parent"])

    transaction.cashbacks.all().update(cashback_to=transaction_copy)

    if delete_old:
        transaction.is_deleted = True
        transaction.extra["deletion_detail"] = "Copied to a newer transaction"
        transaction.save(update_fields=["is_deleted", "extra"])

    return transaction_copy


def make_payment_partial(transaction: Transaction, payment_service: str):
    """
    Makes payment partial. Part of the amount (amount stored in from_balance_amount)
    charged from user's balance, another part from Bank account.
    """
    # if not transaction.type == Transaction.BALANCE:
    #     raise PaymentError(human=msg.ONLY_BALANCE_PAYMENTS_CAN_BE_PARTIONATED)

    # Undo previous action
    # This is done to restore original amount and remove from_balance_amount,
    # otherwise amount is decreased from already decreased amount
    transaction = unmake_payment_partial(transaction)
    transaction = copy_transaction(transaction)

    user = transaction.user
    balance = user.as_customer.active_balance

    transaction_amount = Converter.convert(
        transaction.discounted_amount,
        transaction.discounted_amount_currency.code,
        balance.currency.code,
    )

    from_bank_amount = transaction_amount - balance.amount

    if from_bank_amount <= 0:
        # User already has enough balance
        raise PaymentError(human=msg.USER_ALREADY_HAS_ENOUGH_BALANCE)

    transaction.type = Transaction.CARD
    transaction.from_balance_amount = balance.amount
    transaction.from_balance_currency = balance.currency
    transaction.is_partial = True
    transaction.amount = Converter.convert(
        from_bank_amount, balance.currency.code, transaction.currency.code
    )
    transaction.payment_service = payment_service
    transaction.save(
        update_fields=[
            "type",
            "payment_service",
            "from_balance_amount",
            "from_balance_currency",
            "is_partial",
            "amount",
        ]
    )

    return transaction


def get_courier_order_related_shipment_transactions(courier_order):
    if courier_order:
        shipment_numbers = courier_order.shipments.filter(is_paid=False).values_list(
            "number", flat=True
        )
        shipment_transactions = list(
            get_user_transactions(
                courier_order.user,
                identifiers=shipment_numbers,
                on_error=Transaction.objects.none(),
            )
        )
        return shipment_transactions
    return []


@db_transaction.atomic
def prepare_transaction_for_courier_order(transaction, merge_type):
    courier_order = transaction.related_object

    # Check if this transaction has parent transaction (means that it was already merged)
    if transaction.parent_id:
        transaction.parent.children.update(parent=None)
        transaction.parent.is_deleted = True
        transaction.parent.extra[
            "deletion_detail"
        ] = 'The same as "old parent deletion", but from legacy code for courier payment'
        transaction.parent.save(update_fields=["is_deleted", "extra"])

    # Get related unpaid shipments transactions
    shipment_transactions = get_courier_order_related_shipment_transactions(
        courier_order
    )

    transactions = normalize_transactions([transaction] + shipment_transactions)
    mergable, type_, currency_id, user_id = transactions_are_mergable(
        transactions, override_type=merge_type
    )
    transaction = merge_transactions(user_id, type_, currency_id, transactions)
    return transaction


@db_transaction.atomic
def create_shipment(
    customer,
    packages,
    recipient,
    destination_warehouse,
    user_note=None,
    is_oneclick=False,
    is_serviced=None,
    is_dangerous=False,
    # payment_method="balance",
    _accepted=False,
    skip_comitting=False,
):
    source_country_id = None
    current_warehouse_id = None
    invalid_tracking_codes = []

    if not packages:
        raise InvalidActionError(human=msg.CANT_CREATE_SHIPMENT_WITHOUT_PACKAGE)

    # Check that all packages are from the same country and warehouse (if not oneclick)
    for package in packages:
        if not source_country_id:
            source_country_id = package.source_country_id
            current_warehouse_id = package.current_warehouse_id
        elif not (
            package.source_country_id == source_country_id
            or (  # if not oneclick then package must already has current warehouse
                not is_oneclick and package.current_warehouse_id == current_warehouse_id
            )
        ):
            invalid_tracking_codes.append(package.tracking_code)

    if invalid_tracking_codes:
        raise DifferentPackageSourceError(invalid_tracking_codes=invalid_tracking_codes)

    # If any package was problematic, change its status to foreign and notify warehouseman about that
    # TODO: Notify warehouseman
    for package in filter(lambda p: p.is_problematic, packages):
        promote_status(
            package,
            to_status=Status.objects.get(type=Status.PACKAGE_TYPE, codename="foreign"),
        )
        # notify warehouseman here...

    # if user_address.nearby_warehouse_id == current_warehouse_id:
    #     raise InvalidActionError(human=msg.CANT_SEND_TO_SELECETED_WAREHOUSE)

    shipment = Shipment(
        user=customer,
        source_country_id=source_country_id,
        current_warehouse_id=current_warehouse_id,
        source_warehouse_id=current_warehouse_id,
        destination_warehouse_id=destination_warehouse.id,
        recipient=recipient.freeze(),
        user_note=user_note,
        is_oneclick=is_oneclick,
        is_dangerous=is_dangerous
        # payment_method=payment_method,
    )
    shipment._accepted = _accepted
    shipment._skip_commiting = skip_comitting

    if is_serviced is not None:
        shipment.is_serviced = True

    # get any package that has source country
    any_package = None
    for _package in packages:
        if _package.source_country_id:
            any_package = _package

    sh_number_country_prefix = None
    if any_package:
        sh_number_country_prefix = any_package.source_country.code
    shipment.save(source_country_code=sh_number_country_prefix)

    shipment.packages.add(*packages)
    shipment.declared_price = shipment.calculate_declared_price()
    shipment.declared_items_title = shipment.generate_declared_items_title()
    shipment.save(
        update_fields=[
            "number",
            "declared_price_currency",
            "declared_price",
            "declared_items_title",
        ]
    )
    shipment._skip_commiting = False
    return shipment


def transactions_are_mergable(transactions, override_type=None):
    """Checks that transactions are mergable by their type and currency."""
    transaction_type = override_type
    transaction_currency_id = None
    user_id = None

    if transactions:
        transaction_type = transactions[0].type
        transaction_currency_id = transactions[0].currency_id
        user_id = transactions[0].user_id

    if transaction_type is None or transaction_currency_id is None or user_id is None:
        return False, None, None, None

    for transaction in transactions[1:]:
        if not (
            (override_type or transaction.type == transaction_type)
            and transaction.currency_id == transaction_currency_id
            and transaction.user_id == user_id
        ):
            return False, None, None, None

    # If override type is specified then return it instead of type infered from transaction
    return True, override_type or transaction_type, transaction_currency_id, user_id


@db_transaction.atomic
def normalize_transactions(transactions: List[Transaction], to_currency=None):
    """
    Normalize tranaction currencies, so ther are the same.
    If not `to_currency` is provided, currency of transactions[0] is taken.

    Empty transactions list will return empty list.
    On success returns transaction in the same order as the were provided.
    """
    if not transactions:
        return []

    to_currency = to_currency or transactions[0].currency

    for transaction in transactions:
        if transaction.currency_id != to_currency.id:
            original_amount = transaction.amount
            original_currency = transaction.currency
            transaction.amount = Converter.convert(
                original_amount, original_currency.code, to_currency.code
            )
            transaction.currency = to_currency
            transaction.original_amount = original_amount
            transaction.original_currency = original_currency
            transaction.save(
                update_fields=[
                    "original_amount",
                    "original_currency",
                    "amount",
                    "currency",
                ]
            )

    return transactions


def handle_promo_data(transaction: Transaction):
    instance = transaction.related_object
    if isinstance(instance, Shipment) and "ulduzum_data" in instance.extra:
        identical_code = instance.extra["ulduzum_data"].get("identical_code", "")
        client = UlduzumClient(
            identical_code=identical_code,
            test_mode=instance.extra["ulduzum_data"].get("test_mode", settings.DEBUG),
        )
        try:
            client.complete_for_shipment(instance)
        except UlduzumException:
            pass  # ignore


@db_transaction.atomic
def complete_payments(
    transactions: List[Transaction],
    override_type=None,
    callback=None,
    callback_params=None,
    force_merge=True,
    unmake_partial=True,
):
    callback_params = callback_params or dict()

    if override_type and override_type not in Transaction.FLAT_TYPES:
        raise PaymentError(msg.INVALID_NEW_PAYMENT_TYPE)

    _all_ids = [t.id for t in transactions]

    nice_transactions = []

    for transaction in transactions:
        if transaction.parent_id and transaction.parent_id in _all_ids:
            continue
        else:
            nice_transactions.append(transaction)

    transactions = nice_transactions

    if any(transaction.completed for transaction in transactions):
        raise PaymentError(msg.ALREADY_PAID)

    if any(transaction.purpose == Transaction.CASHBACK for transaction in transactions):
        raise PaymentError("Cashback")

    if any(transaction.is_deleted for transaction in transactions):
        raise PaymentError("Is deleted")

    if unmake_partial:
        for transaction in transactions:
            unmake_payment_partial(transaction)

    if len(transactions) > 1:
        mergable, type_, currency_id, user_id = transactions_are_mergable(
            transactions, override_type=override_type
        )
        if not mergable:
            if force_merge:  # ...normalize and then try again
                transactions = normalize_transactions(transactions)
                # Check if mergable again
                mergable, type_, currency_id, user_id = transactions_are_mergable(
                    transactions, override_type=override_type
                )

        if not mergable:  # ...if fails here again, then raise an exception
            raise PaymentError(msg.PAYMENT_TYPES_AND_CURRENCIES_MUST_BE_THE_SAME)

        transaction = merge_transactions(user_id, type_, currency_id, transactions)

    elif transactions:  # only one
        transaction = transactions[0]
        remove_from_parent(transaction)

        if override_type:
            transaction.type = override_type
            transaction.save(update_fields=["type"])

    else:
        raise PaymentError

    if transaction.type == Transaction.BALANCE:
        customer = transaction.user.as_customer
        balance = customer.active_balance

        transaction_amount = Converter.convert(
            transaction.discounted_amount,
            transaction.discounted_amount_currency.code,
            balance.currency.code,
        )

        if balance.amount < transaction_amount:
            raise InsufficientBalanceError(
                currency_code=balance.currency.code,
                missing_amount=transaction_amount - balance.amount,
            )

        balance.amount = F("amount") - transaction_amount
        balance.save(update_fields=["amount"])

    elif transaction.type == Transaction.CARD:
        if not transaction.check_payment_service_confirmation():
            raise PaymentError(msg.CARD_PAYMENT_FAILED)

        affected = affect_balance_by(transaction, notify=True)

        if not affected:  # then this is partial payment
            from_balance_amount = transaction.from_balance_amount
            from_balance_currency = transaction.from_balance_currency
            balance = transaction.user.as_customer.active_balance

            balance.amount = F("amount") - Converter.convert(
                from_balance_amount,
                from_balance_currency.code,
                balance.currency.code,
            )
            balance.save(update_fields=["amount"])

    elif transaction.type in [Transaction.CASH, Transaction.TERMINAL]:
        affect_balance_by(transaction, notify=True)

    handle_promo_data(transaction)
    _make_completed(
        transaction, custom_callback=callback, custom_callback_params=callback_params
    )
    return transaction


def affect_balance_by(transaction: Transaction, notify: bool = False):
    """
    Topup user balance and send notification if `notify` is True.
    Returns boolean indicating that operation was successfull.
    """
    balance = transaction.user.as_customer.active_balance
    amount = None

    if transaction.type == Transaction.CARD:
        amount = transaction.get_payment_service_transaction_amount()
    else:  # only CASH here...
        amount = transaction.amount

    if not amount or transaction.purpose not in [
        Transaction.BALANCE_DECREASE,
        Transaction.BALANCE_INCREASE,
    ]:
        return False

    if transaction.purpose == Transaction.BALANCE_INCREASE:
        balance.amount = F("amount") + Converter.convert(
            Decimal(amount), transaction.currency.code, balance.currency.code
        )
        balance.save(update_fields=["amount"])

        if notify:
            create_notification(
                transaction,
                EVENTS.ON_USER_BALANCE_TOPUP,
                [transaction.user],
                add_related_obj=False,
            )

    elif transaction.purpose == Transaction.BALANCE_DECREASE:
        balance.amount = F("amount") - Converter.convert(
            Decimal(amount),
            transaction.currency.code,
            balance.currency.code,
        )
        balance.save(update_fields=["amount"])

    return True


def _make_completed(transaction, custom_callback=None, custom_callback_params=None):
    custom_callback_params = custom_callback_params or dict()
    related_objects = []
    children = []

    now = timezone.now()
    transaction.completed = True
    transaction.completed_at = now
    transaction.save(update_fields=["completed", "completed_at"])

    if transaction.children.exists():
        transaction.children.update(completed=True, completed_at=now)

        for transaction in transaction.children.all():
            # TODO: Make some recursivness here.
            # But for now we will not go deeper than 2 nested levels of transactions.
            children.append(transaction)
            related_objects.append(transaction.related_object)

            # FIXME: DRY needed...
            if transaction.children.exists():
                transaction.children.update(completed=True, completed_at=now)

                for nested_transaction in transaction.children.all():
                    children.append(nested_transaction)
                    related_objects.append(nested_transaction.related_object)

    else:
        related_objects.append(transaction.related_object)

    payment_callback(related_objects, transaction, children)
    if custom_callback and callable(custom_callback):
        custom_callback(
            related_objects, transaction, children, **custom_callback_params
        )


def remove_from_parent(transaction: Transaction, parent=None):
    parent = transaction.parent or parent

    if parent:
        transaction.parent = None
        transaction.save(update_fields=["parent"])
        if parent.children.count() == 1:
            parent.is_deleted = True
            parent.extra["deletion_detail"] = "Because only one child left"
            parent.save(update_fields=["is_deleted", "extra"])
            parent.children.update(parent=None)
            parent.delete()  # make soft delete
        else:
            parent_amount = Decimal("0.00")
            for child in parent.children.all():
                parent_amount += Converter.convert(
                    child.discounted_amount,
                    child.discounted_amount_currency.code,
                    parent.currency.code,
                )
                parent.amount = parent_amount
                parent.save(update_fields=["amount"])
                parent.refresh_from_db(fields=["amount"])

            parent.save(update_fields=["amount"])
            parent.refresh_from_db(fields=["amount"])

    return parent


def merge_transactions(user_id, transaction_type, currency_id, transactions):
    """
    Merges transactions, created new transaction with provided data, and with children == transactions.

    Important note!
    Call this function only and only after you have checked that transaction are mergable.
    Otherwise invalid entries may be created!
    """

    if transactions and len(transactions) == 1:
        return transactions[0]

    parent = Transaction.objects.create(
        user_id=user_id,
        currency_id=currency_id,
        type=transaction_type,
        amount=sum(t.discounted_amount for t in transactions if not t.completed),
        purpose=Transaction.MERGED,
        completed=False,
    )

    for transaction in transactions:
        remove_from_parent(transaction)

        transaction.type = transaction_type
        transaction.parent = parent
        transaction.save(update_fields=["parent", "type"])

        for cashback_transaction in transaction.cashbacks.all():
            copy_of_cashback = copy_transaction(cashback_transaction, delete_old=False)
            copy_of_cashback.cashback_to = parent
            copy_of_cashback.save()

        # check if this transaction has child transactions
        # collect that cashbacks too
        # TODO: Not respecting DRY, fix that, may be some recursivness would help
        cashbacks_exist = Transaction.objects.filter(
            cashback_to=OuterRef("id"), completed=False, is_deleted=False
        ).values("id")
        for child_transaction in transaction.children.annotate(
            cashbacks_exist=Exists(cashbacks_exist)
        ).filter(completed=False, is_deleted=False, cashbacks_exist=True):
            for child_cashback in child_transaction.cashbacks.all():
                copy_of_child_cashback = copy_transaction(
                    child_cashback, delete_old=False
                )
                copy_of_cashback.cashback_to = parent
                copy_of_child_cashback.save()

    return parent


def payment_callback(
    instances: List[Union[CourierOrder, Shipment, Order]],
    transaction: Transaction,
    children,
):
    _orders = []
    owner_id = None
    if instances and instances[0]:
        owner_id = instances[0].user_id
    instance_identifiers = []

    for instance in instances:
        if instance and hasattr(instance, "identifier"):
            instance_identifiers.append(instance.identifier)

        # ========== SHIPMENT ==========
        if isinstance(instance, Shipment):
            instance.is_paid = True
            instance.save(update_fields=["is_paid"])

            # done_status = Status.objects.get(type=Status.SHIPMENT_TYPE, codename="done")
            # promote_status(instance, to_status=done_status)

        # ========== ORDER ==========
        elif isinstance(instance, Order):
            if instance.status.codename == "created":
                instance.paid_amount = instance.total_price
                instance.is_paid = True
                instance.save(update_fields=["is_paid", "paid_amount"])
                promote_status(
                    instance,
                    Status.objects.get(type=Status.ORDER_TYPE, codename="processing"),
                )
                _orders.append(instance)
            elif instance.status.codename == "unpaid":  # remainder is being paid
                additional_amount = Decimal("0.00")
                nice_transaction = (
                    True  # transaction is for remainder and this instance
                )

                if transaction.type == Transaction.MERGED:
                    for _transaction in filter(
                        lambda t: t.related_object_identifier == instance.identifier
                        and t.purpose == Transaction.ORDER_REMAINDER_PAYMENT
                    ):
                        additional_amount += Converter.convert(
                            _transaction.discounted_amount,
                            _transaction.discounted_amount_currency.code,
                            instance.total_price.code,
                        )
                elif (
                    transaction.related_object_identifier == instance.identifier
                    and transaction.purpose == Transaction.ORDER_REMAINDER_PAYMENT
                ):
                    additional_amount += Converter.convert(
                        transaction.discounted_amount,
                        transaction.discounted_amount_currency.code,
                        instance.total_price_currency.code,
                    )
                else:
                    nice_transaction = False

                if nice_transaction:
                    # Set paid amount before, because remainder is calculated
                    # using that field, not total price!
                    instance.paid_amount = F("paid_amount") + additional_amount
                    instance.save(update_fields=["paid_amount"])
                    # Because we must have a valid python decimal
                    instance.refresh_from_db(fields=["paid_amount"])
                    set_remainder_price(instance, save=True, log=False)
                    promote_status(
                        instance,
                        Status.objects.get(type=Status.ORDER_TYPE, codename="paid"),
                    )
        # ========== COURIER ORDER ==========
        elif isinstance(instance, CourierOrder):
            instance.is_paid = True
            instance.save(update_fields=["is_paid"])

    if instance_identifiers:
        PromoCodeBenefit.objects.filter(
            consumer_id=owner_id,
            related_object_identifier__in=instance_identifiers,
        ).update(used_by_consumer=True)
        db_transaction.on_commit(
            lambda: apply_cashbacks_to_promo_code_owner_task.delay(transaction.id)
        )

    if _orders:
        assign_orders_to_operator_task([_order.id for _order in _orders])

    # Apply cashbacks
    cashback_amount = transaction.get_cashback_amount(complete_cashbacks=True)
    balance = transaction.user.active_balance
    balance.amount = F("amount") + Converter.convert(
        cashback_amount, transaction.currency.code, balance.currency.code
    )
    balance.save(update_fields=["amount"])
    if transaction.cashbacks.filter(extra__invite_friend_cashback=True).exists():
        create_notification(
            transaction,
            EVENTS.ON_INVITE_FRIEND_CASHBACK_CONSUMER,
            [transaction.user],
            add_related_obj=False,
        )


def promote_status(instance, to_status=None, **kwargs):
    status = None

    if isinstance(instance, Order):
        status = _promote_order_status(instance, to_status, **kwargs)
    elif isinstance(instance, Package):
        status = _promote_package_status(instance, to_status, **kwargs)
    elif isinstance(instance, Shipment):
        status = _promote_shipment_status(instance, to_status, **kwargs)
    elif isinstance(instance, Ticket):
        status = _promote_ticket_status(instance, to_status, **kwargs)

    if not status:
        raise InvalidActionError

    return status


def _promote_order_status(order, to_status, **kwargs):
    current_status = order.status

    if not to_status and current_status.is_final:
        next_status = None
    else:
        next_status = to_status or current_status.next

    if next_status:
        with db_transaction.atomic():
            StatusEvent.objects.create(
                order=order, from_status=current_status, to_status=next_status
            )
            update_fields = ["status", "status_last_update_time"]

            if next_status.codename == "paid":
                order.is_paid = True
                update_fields.append("is_paid")
            elif next_status.codename == "deleted":
                if order.is_paid:
                    refund_order(order, kwargs.get("staff_user_id"))
                elif order.status.codename == "created":
                    remove_related_uncomplete_transaction(order)
            elif next_status.codename == "ordered":
                create_notification(order, EVENTS.ON_ORDER_FULFILL, [order, order.user])

            order.status = next_status
            order.status_last_update_time = timezone.now()
            order.save(update_fields=update_fields)

        return order.status

    return None


def _promote_package_status(package, to_status, **kwargs):
    current_status = package.status

    if not to_status and current_status.is_final:
        next_status = None
    else:
        next_status = to_status or current_status.next

    if next_status:
        with db_transaction.atomic():
            StatusEvent.objects.create(
                package=package, from_status=current_status, to_status=next_status
            )

            package.status = next_status
            package.status_last_update_time = timezone.now()
            package.save(update_fields=["status", "status_last_update_time"])

            notification = _get_package_status_notification(package, next_status)
        return package.status

    return None


def _promote_shipment_status(shipment: Shipment, to_status, **kwargs):
    current_status = shipment.status

    if not to_status and current_status.is_final:
        next_status = None
    else:
        next_status = to_status or current_status.next

    if next_status:
        if next_status.is_final and not shipment.is_paid:
            return

        to_be_shipped = False
        if next_status.codename == "tobeshipped":
            to_be_shipped = True

            if not (shipment.total_price and shipment.total_price_currency):
                raise InvalidActionError(msg.SHIPMENT_PRICE_NOT_SET)

        with db_transaction.atomic():
            shipment_update_fields = kwargs.get("update_fields", [])

            if shipment.status_id != next_status.id:
                event = StatusEvent.objects.create(
                    shipment=shipment, from_status=current_status, to_status=next_status
                )

                event_update_fields = []
                for lang_code, lang_name in settings.LANGUAGES:
                    # Set message in multiple languages
                    with translation.override(lang_code):
                        event_update_fields.append("message_%s" % lang_code)
                        _set_shipment_status_message(shipment, event, next_status)

                if event_update_fields:
                    event.save(update_fields=event_update_fields)

                shipment.status = next_status
                shipment_update_fields += ["status", "status_last_update_time"]

                notification = _get_shipment_status_notification(
                    shipment, next_status, send_notification=True
                )

            if to_be_shipped:
                # We are recalculating declared price here, because
                # there are big chances we have set delivery price (total price) for the shipment
                shipment_update_fields += ["declared_at", "declared_price"]
                shipment.declared_at = timezone.now()
                shipment.declared_price = shipment.calculate_declared_price()

            shipment.status_last_update_time = timezone.now()
            shipment._accepted = True
            shipment.save(update_fields=shipment_update_fields)

        return shipment.status

    return None


def _promote_ticket_status(ticket: Ticket, to_status, **kwargs):
    current_status = ticket.status

    if not to_status and current_status.is_final:
        next_status = None
    else:
        next_status = to_status or current_status.next

    if next_status:
        ticket.status = next_status
        ticket.status_last_update_time = timezone.now()
        ticket.save(update_fields=["status_last_update_time", "status"])

        return ticket.status

    return None


def _get_shipment_status_notification(shipment, to_status, send_notification=False):
    message = None

    if to_status.codename == "tobeshipped":
        source_warehouse = shipment.source_warehouse
        message = msg.SHIPMENT_IS_BEING_PREPARED_FOR_FLIGHT_FMT % {
            "city": source_warehouse.city.name
        }
        if send_notification:
            create_notification(
                shipment,
                EVENTS.ON_SHIPMENT_STATUS_TOBESHIPPED,
                [shipment, shipment.user],
            )

    elif to_status.codename == "ontheway":
        source_warehouse = shipment.source_warehouse
        message = msg.SHIPMENT_LEFT_FOREIGN_WAREHOUSE_FMT % {
            "city": source_warehouse.city.name
        }
        if send_notification:
            create_notification(
                shipment, EVENTS.ON_SHIPMENT_STATUS_ONTHEWAY, [shipment, shipment.user]
            )

    elif to_status.codename == "received":
        destination_warehouse = shipment.destination_warehouse
        message = msg.SHIPMENT_ARRIVED_INTO_LOCAL_WAREHOUSE_FMT % {
            "warehouse": destination_warehouse.title
        }
        if send_notification:
            create_notification(
                shipment, EVENTS.ON_SHIPMENT_STATUS_RECEIVED, [shipment, shipment.user]
            )

    elif to_status.codename == "done":
        message = msg.SHIPMENT_GIVEN_TO_CUSTOMER

        if send_notification:
            create_notification(
                shipment, EVENTS.ON_SHIPMENT_STATUS_DONE, [shipment, shipment.user]
            )

    elif to_status.codename == "customs":
        message = msg.SHIPMENT_ON_CUSTOMS

    return message


# MiniNotification = namedtuple("MiniNotification", ["title", "body"])


def _get_package_status_notification(package, to_status):
    if to_status.codename == "problematic":
        return create_notification(
            package, EVENTS.ON_PACKAGE_STATUS_PROBLEMATIC, [package.user, package]
        )
    elif to_status.codename == "foreign":
        return create_notification(
            package, EVENTS.ON_PACKAGE_STATUS_FOREIGN, [package.user, package]
        )


def _set_shipment_status_message(shipment, event, to_status):
    # This will not send notification, but simply returns tracking message
    event.message = _get_shipment_status_notification(
        shipment, to_status, send_notification=False
    )


def create_uncomplete_transactions_for_orders(orders, instant_payment=False):
    transactions = Transaction.objects.bulk_create(
        [
            Transaction(
                user=order.user,
                currency=order.total_price_currency,
                amount=order.total_price,
                purpose=Transaction.ORDER_PAYMENT,
                type=Transaction.BALANCE,
                completed=False,
                related_object=order,
                related_object_identifier=order.identifier,
            )
            for order in orders
        ]
    )

    if not instant_payment:
        for transaction in transactions:
            create_notification(
                transaction,
                EVENTS.ON_ORDER_PAYMENT_CREATE,
                [transaction.related_object, transaction.user, transaction],
            )

    return transactions


def remove_related_uncomplete_transaction(order):
    Transaction.objects.filter(
        related_object_identifier=order.identifier, completed=False
    ).delete()


def create_uncomplete_transaction_for_shipment(shipment, notify=True, extra=None):
    has_total_price = bool(shipment.total_price and shipment.total_price_currency_id)

    if not has_total_price:
        raise InvalidActionError(human=msg.SHIPMENT_PRICE_CANNOT_BE_SET)

    transaction = shipment.related_transaction
    if not transaction:
        transaction = Transaction.objects.create(
            user_id=shipment.user_id,
            currency_id=shipment.total_price_currency_id,
            amount=shipment.total_price,
            purpose=Transaction.SHIPMENT_PAYMENT,
            type=Transaction.BALANCE,
            completed=False,
            related_object=shipment,
            related_object_identifier=shipment.identifier,
            extra=extra or {},
        )

    if notify:
        create_notification(
            transaction,
            EVENTS.ON_SHIPMENT_PAYMENT_CREATE,
            [transaction, shipment, shipment.user],
        )

    return transaction


_UPDATED = 1
_CREATED = 2
_NOTHING_HAPPENED = 4


def update_or_create_transaction_for_shipment(shipment: Shipment):
    if not (shipment.total_price and shipment.total_price_currency):
        return _NOTHING_HAPPENED
    related_transaction: Transaction = shipment.related_transaction
    if related_transaction:
        unmake_payment_partial(related_transaction)
        related_transaction.amount = shipment.total_price
        related_transaction.related_object_identifier = shipment.identifier
        related_transaction.currency_id = shipment.total_price_currency_id
        related_transaction.original_amount = shipment.total_price
        related_transaction.original_currency_id = shipment.total_price_currency_id
        related_transaction.completed = shipment.is_paid
        if related_transaction.is_amount_changed:
            related_transaction.extra["autofix"] = {
                "old_amount": str(related_transaction.old_amount),
                "old_currency_id": related_transaction.old_currency_id,
            }
        related_transaction.save()
        return _UPDATED
    if not related_transaction:
        transaction = create_uncomplete_transaction_for_shipment(
            shipment, notify=False, extra={"create_reason": "autofix"}
        )
        transaction.completed = shipment.is_paid
        if transaction.completed:
            transaction.completed_at = timezone.now()
        transaction.save(update_fields=["completed", "completed_at"])
        return _CREATED
    return _NOTHING_HAPPENED


def create_uncomplete_transaction_for_courier_order(order: CourierOrder):
    has_total_price = bool(order.total_price and order.total_price_currency_id)

    if not has_total_price:
        raise InvalidActionError

    transaction = Transaction.objects.create(
        user_id=order.user_id,
        currency_id=order.total_price_currency_id,
        amount=order.total_price,
        purpose=Transaction.COURIER_ORDER_PAYMENT,
        type=Transaction.BALANCE,
        completed=False,
        related_object=order,
        related_object_identifier=order.identifier,
    )

    return transaction


RealPrice = namedtuple("RealPrice", ["price", "currency"])


def calculate_remainder_price(order) -> (RealPrice, RealPrice, RealPrice):
    """
    Calculates remainder price based on paid amount.
    """
    # First get real total price
    real_total_price = Decimal("0.00")

    if not order.real_total_price_currency_id:
        return real_total_price

    # Usually real total price currency is the same as total price currency
    main_currency = order.real_total_price_currency
    currency_code = main_currency.code

    # Product price
    real_product_price = Converter.convert(
        order.real_product_price, order.real_product_price_currency.code, currency_code
    )
    real_total_price += real_product_price * order.real_product_quantity

    # Cargo price
    real_cargo_price = Converter.convert(
        order.real_cargo_price, order.real_cargo_price_currency.code, currency_code
    )
    real_total_price += real_cargo_price

    # Add comission price too
    real_commission_price = Configuration().calculate_commission_for_price(
        real_total_price, main_currency
    )
    real_commission_price_currency = main_currency
    real_total_price += real_commission_price
    # Now get the difference
    remainder_price = real_total_price - Converter.convert(
        order.paid_amount, order.total_price_currency.code, currency_code
    )

    remainder = RealPrice(remainder_price, main_currency)
    real_total = RealPrice(real_total_price, main_currency)
    real_commission = RealPrice(real_commission_price, main_currency)

    return remainder, real_total, real_commission


def set_remainder_price(order, save=True, log=True, staff_user=None):
    """
    Sets remainder price for specified order. This method calculates
    remainder price based on paid amount.
    """
    remainder, real_total, real_commission = calculate_remainder_price(order)
    order.remainder_price = remainder.price
    order.remainder_price_currency = remainder.currency
    order.real_total_price = real_total.price
    order.real_total_price_currency = real_total.currency
    order.real_commission_price = real_commission.price
    order.real_commission_price_currency = real_commission.currency

    update_fields = [
        "remainder_price",
        "remainder_price_currency",
        "real_total_price",
        "real_total_price_currency",
        "real_commission_price",
        "real_commission_price_currency",
    ]

    if save:
        order.save(update_fields=update_fields)

    if log and staff_user:  # ...log that staff_user has set the remainder price
        LogEntry.objects.log_action(
            user_id=staff_user.id,
            content_type_id=ContentType.objects.get_for_model(order).pk,
            object_id=order.id,
            object_repr=str(order),
            action_flag=CHANGE,
            change_message=(
                "Real total price was set to %s %s. Remainder price was calculated to be %s %s."
                % (
                    real_total.price,
                    real_total.currency.code,
                    remainder.price,
                    remainder.currency.code,
                )
            ),
        )

    if save:
        return order

    return update_fields


@db_transaction.atomic
def refund_order(order, staff_user_id=None):
    if not order.is_paid:
        raise InvalidActionError(human=msg.ORDER_IS_NOT_PAID)
    if not order.can_assistant_reject_order:
        raise InvalidActionError(human=msg.ORDER_CANNOT_BE_REJECTED)

    customer = order.user.as_customer
    balance = customer.active_balance

    transactions = Transaction.objects.filter(
        related_object_identifier=order.identifier,
        purpose__in=[
            Transaction.ORDER_PAYMENT,
            Transaction.ORDER_REMAINDER_PAYMENT,
            Transaction.ORDER_REMAINDER_REFUND,
        ],
        completed=True,
    )

    sign_map = {
        Transaction.ORDER_PAYMENT: 1,
        Transaction.ORDER_REMAINDER_PAYMENT: 1,
        Transaction.ORDER_REMAINDER_REFUND: -1,
    }

    refund_amount = sum(
        sign_map[t.purpose]
        * Converter.convert(
            t.get_refundable_amount(), t.currency.code, balance.currency.code
        )
        for t in transactions
    )

    balance.amount = F("amount") + refund_amount
    balance.save(update_fields=["amount"])

    # Create refund transaction
    transaction = Transaction.objects.create(
        user=order.user,
        currency_id=balance.currency_id,
        amount=refund_amount,
        purpose=Transaction.ORDER_REFUND,
        type=Transaction.BALANCE,
        related_object=order,
        related_object_identifier=order.identifier,
        completed=True,
    )

    order.is_paid = False
    order.paid_amount = 0
    order.remainder_price = 0
    order.save(update_fields=["is_paid", "paid_amount", "remainder_price"])

    create_notification(
        transaction, EVENTS.ON_ORDER_REJECT, [transaction, order, order.user]
    )

    if staff_user_id:
        # Log staff user who have rejected the order
        LogEntry.objects.log_action(
            user_id=staff_user_id,
            content_type_id=ContentType.objects.get_for_model(order).pk,
            object_id=order.id,
            object_repr=str(order),
            action_flag=DELETION,
            change_message=(
                "Order was rejected and %s %s was refunded to user"
                % (refund_amount, balance.currency.code)
            ),
        )

    return transaction


def get_assistant_with_minimum_workload(country_id):
    return (
        ShoppingAssistantProfile.objects.filter(
            ~Q(user__role__type=Role.ADMIN), countries__id=country_id
        )
        .annotate(
            count_of_assignments=Count(
                "assignment", filter=Q(assignment__is_completed=False)
            )
        )
        .order_by("count_of_assignments")
        .first()
    )


def assign_orders_to_assistants(orders):
    """
    Delays assignments.
    """
    assign_orders_to_operator_task.delay([order.id for order in orders])


@db_transaction.atomic
def approve_remainder_price(staff_user, order):
    if not order.is_paid:
        raise InvalidActionError(human=msg.ORDER_IS_NOT_PAID)
    if not (order.remainder_price and order.remainder_price_currency_id):
        # Try to find existing remainder price transaction and delete it,
        # otherwise raise an error.
        transaction = Transaction.objects.filter(
            purpose=Transaction.ORDER_REMAINDER_PAYMENT,
            user_id=order.user_id,
            related_object_identifier=order.identifier,
            completed=False,
        ).first()

        if transaction:
            transaction.delete()
        else:
            raise InvalidActionError(human=msg.ORDER_DOES_NOT_HAVE_REMAINDER_PRICE)

    # Check if this order already has remainder transaction, then update it
    existed = False
    transaction = Transaction.objects.filter(
        purpose=Transaction.ORDER_REMAINDER_PAYMENT,
        user_id=order.user_id,
        related_object_identifier=order.identifier,
        completed=False,
    ).first()

    if transaction:  # update amount and currency
        existed = True
        transaction.currency = order.remainder_price_currency
        transaction.amount = abs(order.remainder_price)
    else:
        transaction = Transaction(
            user_id=order.user_id,
            currency_id=order.remainder_price_currency_id,
            amount=abs(order.remainder_price),
            type=Transaction.BALANCE,
            related_object=order,
            related_object_identifier=order.identifier,
        )

    change_message = ""
    reason = None  # ...notification reason

    if order.remainder_price > 0:
        transaction.purpose = Transaction.ORDER_REMAINDER_PAYMENT
        transaction.completed = False
        promote_status(
            order,
            to_status=Status.objects.get(type=Status.ORDER_TYPE, codename="unpaid"),
        )
        change_message = (
            "Remainder price %s %s approved and uncomplete transaction was %s for user."
            % (
                transaction.amount,
                transaction.currency.code,
                "updated" if existed else "created",
            )
        )

        if existed:
            reason = EVENTS.ON_ORDER_REMAINDER_UPDATE
        else:
            reason = EVENTS.ON_ORDER_REMAINDER_CREATE
    else:
        transaction.purpose = Transaction.ORDER_REMAINDER_REFUND
        transaction.completed = True
        customer = order.user.as_customer
        balance = customer.active_balance

        refund_amount = Converter.convert(
            transaction.amount,
            order.remainder_price_currency.code,
            balance.currency.code,
        )

        order.paid_amount = F("paid_amount") - Converter.convert(
            transaction.amount,
            order.remainder_price_currency.code,
            order.total_price_currency.code,
        )
        order.save(update_fields=["paid_amount"])
        order.refresh_from_db(fields=["paid_amount"])
        order_update_fields = set_remainder_price(
            order, save=False, log=False, staff_user=staff_user
        )
        order.save(update_fields=order_update_fields)

        balance.amount = F("amount") + refund_amount
        balance.save(update_fields=["amount"])
        change_message = (
            "User's overpaid amount of %s %s was refunded to his balance"
            % (transaction.amount, transaction.currency.code)
        )

        if refund_amount:
            reason = EVENTS.ON_ORDER_REMAINDER_REFUND

    LogEntry.objects.log_action(
        user_id=staff_user.id,
        content_type_id=ContentType.objects.get_for_model(order).pk,
        object_id=order.id,
        object_repr=str(order),
        action_flag=CHANGE,
        change_message=change_message,
    )

    transaction.save()

    if reason:
        create_notification(
            transaction,
            reason,
            [transaction, transaction.related_object, transaction.user],
        )

    return transaction


def create_related_products_from_orders(package, orders, commit=True):
    products = []
    for order in orders:
        print("QTY AND PRICE")
        print(order.real_product_quantity)
        print(order.real_product_price)
        print("---------------")

        products.append(
            Product(
                package_id=package.id,
                category_id=order.product_category_id,
                type_id=order.product_type_id,
                description=order.product_description,
                url=order.product_url,
                price=order.real_product_price,
                price_currency_id=order.real_product_price_currency_id,
                cargo_price=order.real_cargo_price,
                cargo_price_currency_id=(
                    order.real_cargo_price_currency_id
                    or order.real_product_price_currency_id
                ),
                commission_price=order.real_commission_price,
                commission_price_currency_id=order.real_commission_price_currency_id,
                quantity=order.real_product_quantity,
                order_id=order.id,
            )
        )

    if commit:
        products = Product.objects.bulk_create(products)

    return products


@db_transaction.atomic
def update_products_for_package(package: Package):
    related_orders = package.related_orders.all()

    if related_orders.exists():
        # remove all related products that are created from order
        package.products.filter(order__isnull=False).delete()
        create_related_products_from_orders(package, related_orders, commit=True)
        # Update package's shipments' declared items title
        shipment: Shipment = package.shipment
        if shipment:
            shipment.declared_items_title = shipment.generate_declared_items_title()
            shipment.save(update_fields=["declared_items_title"])


@db_transaction.atomic
def create_package_from_orders(
    staff_user, orders: Iterable[Order], tracking_code, arrival_date
):
    for order in orders:
        if not order.can_assistant_add_package:
            raise InvalidActionError

    packages = [o.package for o in orders if o.package_id]
    initial_orders = orders
    orders = [
        o
        for o in orders
        if (
            (o.package and o.package.tracking_code != tracking_code)
            or (not o.package_id)
        )
    ]
    if not orders:
        return None

    user_id = orders[0].user_id
    seller = orders[0].product_seller
    seller_address = orders[0].product_seller
    source_country_id = orders[0].source_country_id
    is_oneclick = orders[0].is_oneclick
    recipient_id = orders[0].recipient_id
    destination_warehouse_id = orders[0].destination_warehouse_id
    order = orders[0]

    products = []
    awaiting_status = Status.objects.get(type=Status.PACKAGE_TYPE, codename="awaiting")

    existing_package = Package.objects.filter(admin_tracking_code=tracking_code).first()
    if existing_package:
        package = existing_package
        package.user_id = user_id
        package.source_country_id = source_country_id
        package.arrival_date = arrival_date
        packageseller = seller
        package.seller_address = seller_address
        package.is_by_assistant = True
        package.save()
    else:
        package = Package.objects.create(
            status=awaiting_status,
            user_id=user_id,
            source_country_id=source_country_id,
            admin_tracking_code=tracking_code,
            arrival_date=arrival_date,
            seller=seller,
            seller_address=seller_address,
            is_by_assistant=True,
        )
    packages.append(package)

    Order.objects.filter(id__in=[o.id for o in orders]).update(package_id=package.id)

    for p in packages:
        update_products_for_package(p)

    if is_oneclick and recipient_id and destination_warehouse_id:
        # Now handle oneclick order, for which packages must also
        # behave as oneclicked, therefore we must create shipments
        package.is_serviced = True
        package.save(update_fields=["is_serviced"])
        shipment = create_shipment(
            package.user,
            [package],
            order.recipient,
            order.destination_warehouse,
            is_oneclick=True,
            is_serviced=True,
        )

    for order in orders:
        # Promote order's status to completed (ordered)
        ordered_status = Status.objects.get(type=Status.ORDER_TYPE, codename="ordered")
        promote_status(order, to_status=ordered_status)

        # Set assignment as completed
        assignment = order.as_assignment
        assignment.is_completed = True
        assignment.save(update_fields=["is_completed"])

        LogEntry.objects.log_action(
            user_id=staff_user.id,
            content_type_id=ContentType.objects.get_for_model(assignment).pk,
            object_id=assignment.id,
            object_repr=str(assignment),
            action_flag=CHANGE,
            change_message="Assignment completed by assistant",
        )

        LogEntry.objects.log_action(
            user_id=staff_user.id,
            content_type_id=ContentType.objects.get_for_model(order).pk,
            object_id=order.id,
            object_repr=str(order),
            action_flag=CHANGE,
            change_message="Package [%s] was created by assistant.%s"
            % (
                package.tracking_code,
                " Related shipments was also created because order is one-clicked"
                if order.is_oneclick
                else "",
            ),
        )

    return package


@db_transaction.atomic
def accept_incoming_packages(packages, warehouseman, override_tracking_code=None):
    current_warehouse = warehouseman.warehouse
    foreign = Status.objects.get(type=Status.PACKAGE_TYPE, codename="foreign")

    for package in filter(lambda p: not p.is_accepted, packages):
        promote_status(package, to_status=foreign)

        # If ordererd using oneclick, automatically set source_warehouse
        if package.shipment_id:
            package.shipment.source_warehouse = current_warehouse
            package.shipment.current_warehouse = current_warehouse
            package.shipment.save(
                update_fields=["source_warehouse", "current_warehouse"]
            )

        if override_tracking_code:
            package.user_tracking_code = override_tracking_code
        package.is_accepted = True
        package.real_arrival_date = timezone.now()
        package.current_warehouse = current_warehouse
        package.is_volume_considered = current_warehouse.does_consider_volume
        package.save(
            update_fields=[
                "current_warehouse",
                "is_accepted",
                "real_arrival_date",
                "user_tracking_code",
            ]
        )

    return packages


@db_transaction.atomic
def create_packages_from_orders(staff_user, orders, tracking_code, arrival_date):
    if not orders:
        return []

    packages = []
    awaiting_status = Status.objects.get(type=Status.PACKAGE_TYPE, codename="awaiting")

    for order in orders:
        if not order.can_assistant_add_package:
            raise InvalidActionError

        packages.append(
            Package(
                status=awaiting_status,
                user_id=order.user_id,
                source_country_id=order.source_country_id,
                admin_tracking_code=tracking_code,
                arrival_date=arrival_date,
                order=order,
                seller=order.product_seller,
                seller_address=order.product_seller_address,
                is_by_assistant=True,
            )
        )

    if packages:
        packages = Package.objects.bulk_create(packages)

        products = []

        for package in packages:
            products.append(
                Product(
                    package_id=package.id,
                    category_id=package.order.product_category_id,
                    type_id=package.order.product_type_id,
                    description=package.order.product_description,
                    url=package.order.product_url,
                    price=package.order.real_product_price,
                    price_currency_id=package.order.real_product_price_currency_id,
                    cargo_price=package.order.real_cargo_price,
                    cargo_price_currency_id=package.order.real_cargo_price_currency_id
                    or package.order.real_product_price_currency_id,
                    commission_price=package.order.real_commission_price,
                    commission_price_currency_id=package.order.real_commission_price_currency_id,
                    quantity=package.order.real_product_quantity,
                )
            )

        Product.objects.bulk_create(products)

        # Now handle oneclick order, for which packages must also
        # behave as oneclicked, therefore we must create shipments
        for package in packages:
            _order: Order = package.order
            if (
                _order.is_oneclick
                and _order.recipient_id
                and _order.destination_warehouse_id
            ):
                package.is_serviced = True  # mark package as serviced
                package.save(update_fields=["is_serviced"])
                shipment = create_shipment(
                    _order.user,
                    [package],
                    _order.recipient,
                    _order.destination_warehouse,
                    is_oneclick=True,
                    is_serviced=True,  # will force the shipment to be marked as serviced
                )

    for order in orders:
        # Promote order's status to completed (ordered)
        ordered_status = Status.objects.get(type=Status.ORDER_TYPE, codename="ordered")
        promote_status(order, to_status=ordered_status)

        # Set assignment as completed
        assignment = order.as_assignment
        assignment.is_completed = True
        assignment.save(update_fields=["is_completed"])

        LogEntry.objects.log_action(
            user_id=staff_user.id,
            content_type_id=ContentType.objects.get_for_model(assignment).pk,
            object_id=assignment.id,
            object_repr=str(assignment),
            action_flag=CHANGE,
            change_message="Assignment completed by assistant",
        )

        LogEntry.objects.log_action(
            user_id=staff_user.id,
            content_type_id=ContentType.objects.get_for_model(order).pk,
            object_id=order.id,
            object_repr=str(order),
            action_flag=CHANGE,
            change_message="%s packages was created by assistant.%s"
            % (
                ", ".join(package.tracking_code for package in packages),
                " Related shipments was also created because order is one-clicked"
                if order.is_oneclick
                else "",
            ),
        )

    return packages


@db_transaction.atomic
def accept_incoming_packages(packages, warehouseman, override_tracking_code=None):
    current_warehouse = warehouseman.warehouse
    foreign = Status.objects.get(type=Status.PACKAGE_TYPE, codename="foreign")

    for package in filter(lambda p: not p.is_accepted, packages):
        promote_status(package, to_status=foreign)

        # If ordererd using oneclick, automatically set source_warehouse
        if package.shipment_id:
            package.shipment.source_warehouse = current_warehouse
            package.shipment.current_warehouse = current_warehouse
            package.shipment.save(
                update_fields=["source_warehouse", "current_warehouse"]
            )

        if override_tracking_code:
            package.user_tracking_code = override_tracking_code
        package.is_accepted = True
        package.real_arrival_date = timezone.now()
        package.current_warehouse = current_warehouse
        package.is_volume_considered = current_warehouse.does_consider_volume
        package.save(
            update_fields=[
                "current_warehouse",
                "is_accepted",
                "real_arrival_date",
                "user_tracking_code",
            ]
        )

    return packages


@db_transaction.atomic
def accept_incoming_shipment(shipment: Shipment, warehouseman: WarehousemanProfile):
    if shipment.destination_warehouse_id != warehouseman.warehouse_id:
        raise AcceptedInWrongWarehouseError(
            correct_warehouse=shipment.destination_warehouse
        )

    current_warehouse_id = warehouseman.warehouse_id
    received = Status.objects.get(type=Status.SHIPMENT_TYPE, codename="received")

    if shipment.status_id != received.id:
        promote_status(shipment, to_status=received)

    # Mark related transportation object as completed if it is not completed yet
    if shipment.box_id and shipment.box.transportation_id:
        transportation = shipment.box.transportation
        transportation.is_completed = True
        transportation.save(update_fields=["is_completed"])

    shipment.current_warehouse_id = current_warehouse_id
    shipment.save(update_fields=["box", "current_warehouse_id", "updated_at"])

    return shipment


@db_transaction.atomic
def add_shipments_to_box(
    box,
    current_warehouse_id=None,
    shipment_numbers=None,
    shipments=None,
    add=False,
    force=False,
):
    shipments = shipments or []
    shipment_numbers = shipment_numbers or []

    no_warehouse_message = msg.BOX_DEST_WAREHOUSE_CANNOT_BE_DEFINED

    if not box.destination_warehouse_id and (
        len(shipments) == 1 or len(shipment_numbers) == 1
    ):
        # Only one shipment provided, deduct destination warehouse for the box
        _shipment = None
        if shipments:
            _shipment = shipments[0]
        elif shipment_numbers:
            _shipment = Shipment.objects.filter(number__in=shipment_numbers).first()

        if _shipment:
            box.destination_warehouse = _shipment.destination_warehouse
            box.save(update_fields=["destination_warehouse"])
        else:
            raise InvalidActionError(human=no_warehouse_message)

    if not box.destination_warehouse_id:
        raise InvalidActionError(human=no_warehouse_message)

    if not shipments:
        destination_query = (
            Q(destination_warehouse_id=box.destination_warehouse_id)
            if not box.destination_warehouse.is_universal
            else Q(
                destination_warehouse__country_id=box.destination_warehouse.country_id
            )
        )
        shipments = Shipment.objects.filter(
            destination_query,
            current_warehouse_id=current_warehouse_id,
            number__in=shipment_numbers or [],
            # box__isnull=True,
        )

    invalid_shipments = []
    for shipment in shipments:
        if force:
            # shipment.confirmed_properties = True
            # promote_status(
            #     shipment,
            #     to_status=Status.objects.get(
            #         type=Status.SHIPMENT_TYPE, codename="tobeshipped"
            #     ),
            #     update_fields=["confirmed_properties"],
            # )
            confirm_shipment_properties(shipment)
        if not shipment.can_be_placed_in_a_box:
            invalid_shipments.append(shipment.number)

    if invalid_shipments:
        raise InvalidActionError(
            human=msg.AT_LEAST_ONE_SHIPMENT_IS_NOT_CONFIRMED,
            shipment_numbers=invalid_shipments,
        )

    if box.transportation_id:
        raise InvalidActionError(human=msg.THIS_BOX_IS_ALREADY_SENT)

    if shipments:
        if add:
            box.shipments.add(*shipments)
        else:
            box.shipments.set(shipments)

        # As we will return box for serializing
        # we update shipment_count and real_total_weight
        # to fresh values (because these fields were aggregated)
        box.shipments_count = box.shipments.count()
        box.real_total_weight = sum(
            shipment.fixed_total_weight
            for shipment in list(shipments)
            + (
                list(box.shipments.exclude(id__in=[s.id for s in shipments]))
                if add
                else []
            )
            if shipment.fixed_total_weight
        )

    return box


def map_package_properties_to_shipment(package, only_dimensions=False):
    """Mapping package properties to the shipment is needed when package is being sent 'in one click'"""
    shipment = package.shipment

    if shipment and not shipment.confirmed_properties:
        if not only_dimensions:
            shipment.fixed_total_weight = package.weight
            shipment.shelf = package.shelf
        shipment.fixed_width = package.width
        shipment.fixed_length = package.length
        shipment.fixed_height = package.height
        shipment.is_volume_considered = package.is_volume_considered
        shipment.save(
            update_fields=[
                "fixed_total_weight",
                "fixed_width",
                "fixed_length",
                "fixed_height",
                "is_volume_considered",
                "shelf",
            ]
        )


@db_transaction.atomic
def confirm_shipment_properties(shipment: Shipment):
    if not shipment.can_be_confirmed_by_warehouseman:
        raise InvalidActionError(
            human=msg.SHIPMENT_ALREADY_CONFIRMED_OR_CANNOT_BE_CONFIRMED
        )

    was_already_confirmed = (
        shipment.confirmed_properties
    )  # to prevent recreating transaction! although it is hardly possible
    shipment.confirmed_properties = True
    shipment._accepted = True
    # Total price is recalculated when confirmed_properties is True!
    shipment.save(
        update_fields=["confirmed_properties", "total_price", "total_price_currency"]
    )
    promote_status(
        shipment,
        to_status=Status.objects.get(type=Status.SHIPMENT_TYPE, codename="tobeshipped"),
    )

    # Creating transaction after confirming total price
    if not was_already_confirmed:
        shipment.refresh_from_db(fields=["number"])
        create_uncomplete_transaction_for_shipment(shipment)

    return shipment


# This function usually run in atomic context, so there is no need to additionally
# wrap this function into db_transaction.atomic
def update_additional_services(provided_services, package=None, shipment=None):
    if provided_services is None:
        # If it was an empty list continue executing, all services are deleted then
        for instance in [package, shipment]:
            # Check if intance did not have any ordered service
            if instance and not instance.ordered_services.exists():
                instance.is_serviced = True
                instance.save(update_fields=["is_serviced"])
        return

    # Get country from shipment.package because shipment and related
    # package must always has same source country. Otherwise
    # just rely on package's source_country
    country_id = None
    if shipment:
        # Related packages always have the same source_country, so take any of them
        any_package = shipment.packages.first()

        if any_package:
            country_id = any_package.source_country_id
    elif package:
        country_id = package.source_country_id

    # It is safe to fetch them all, because usually there are 5-10 services total.
    # Filter by warehouse country, because not all warehouse may provide all services.
    warehouse_subquery = (
        Warehouse.objects.filter(  # filtering warehouse with the right country
            Q(country_id=country_id) if country_id else Q(), service__id=OuterRef("pk")
        ).values("pk")
    )
    all_services = list(
        AdditionalService.objects.annotate(
            warehouse_exists=Exists(warehouse_subquery)
        ).filter(warehouse_exists=True)
    )

    # Note: For now each country has only one warehouse, although it is not restricted on database level

    def find_real_service(provided_service, service_type):
        for real_service in all_services:
            if (
                real_service.id == provided_service.get("id")
                and real_service.type == service_type
                and (not real_service.needs_note or provided_service.get("note"))
            ):
                return real_service

        return None

    if package and not shipment:  # not one-clicked package
        package.ordered_services.all().delete()  # clear all services
        package_additional_services = []
        package.is_serviced = True

        # if provided_services:
        #     # Mark package as not serviced
        #     package.is_serviced = False

        for provided_service in provided_services:
            real_service = find_real_service(
                provided_service, AdditionalService.PACKAGE_TYPE
            )

            if real_service:
                package_additional_services.append(
                    PackageAdditionalService(
                        package=package,
                        service=real_service,
                        note=provided_service.get("note"),
                    )
                )

        if package_additional_services:
            package.is_serviced = False
            PackageAdditionalService.objects.bulk_create(package_additional_services)

        package.save(update_fields=["is_serviced"])

    elif (
        shipment
    ):  # one-clicked package or just a shipment, anyway save all services to shipment
        shipment.ordered_services.all().delete()  # clear all services
        shipment.is_serviced = True

        # if provided_services:
        #     # Mark shipment as not serviced
        #     shipment.is_serviced = False

        # If package is not received by warehouseman
        # and user has decided to make that package one-clicked (convert ot shipment),
        # then we must remove all legacy services.
        if package and package.status.codename != "foreign":
            package.is_serviced = True
            package.save(update_fields=["is_serviced"])
            package.ordered_services.all().delete()

        shipment_additional_services = []

        for provided_service in provided_services:
            real_service = find_real_service(
                provided_service, AdditionalService.SHIPMENT_TYPE
            )

            if real_service:
                shipment_additional_services.append(
                    ShipmentAdditionalService(
                        shipment=shipment,
                        service=real_service,
                        note=provided_service.get("note"),
                    )
                )

        if shipment_additional_services:
            shipment.is_serviced = False
            ShipmentAdditionalService.objects.bulk_create(shipment_additional_services)

        shipment._skip_commiting = True
        shipment.save(update_fields=["is_serviced"])


def get_invoice(instance: Union[Order, Shipment, CourierOrder]):
    return Invoice(instance)


def get_serialized_multiple_invoice(
    user_balance, instances: List[Union[Order, Shipment, CourierOrder]]
):
    from core.serializers.client import CurrencySerializer

    # FIXME: This function is fucking hack...
    serialized_invoices = []
    invoice_instances = []

    total = Decimal("0")
    total_currency = user_balance.currency
    discounted_total = Decimal("0")
    discounted_total_currency = total_currency

    for instance in instances:
        invoice = get_invoice(instance)
        serialized_invoice = invoice.serialize()

        if serialized_invoice:
            del serialized_invoice["missing"]
            serialized_invoices.append(serialized_invoice)
            invoice_instances.append(instance)
            total += Converter.convert(
                invoice.main_total,
                invoice.main_total_currency.code,
                total_currency.code,
            )
            discounted_total += Converter.convert(
                invoice.discounted_total_price,
                invoice.discounted_total_price_currency.code,
                discounted_total_currency.code,
            )

    is_missing = total > user_balance.amount
    missing_amount = discounted_total - user_balance.amount
    serialized_total_currency = CurrencySerializer(total_currency).data

    result = {
        "discount": {
            "is_active": discounted_total < total,
            "amount": str(discounted_total),
            "currency": serialized_total_currency,
        },
        "total": {
            "amount": str(round(total, 2)),
            "currency": serialized_total_currency,
        },
        "missing": {
            "is_active": is_missing,
            "amount": str(round(missing_amount, 2)),
            "currency": serialized_total_currency,
        },
        "objects": [
            {
                "object": instance.serialize_for_payment(),
                "invoice": serialized_invoice,
            }
            for instance, serialized_invoice in zip(
                invoice_instances, serialized_invoices
            )
        ],
    }

    return result


def merge_invoices(user, invoices):
    return MergedInvoice(user, invoices)


def mark_instance_as_serviced(instance):
    """
    Will try to check that instance is serviced.
    Although we can't check if it was actually serviced,
    but at least check that every ordered service
    that needs attachment has at least one.
    """
    instance.is_serviced = True

    # Check if provided attachments
    ordered_services = instance.ordered_services.filter(
        service__needs_attachment=True
    ).prefetch_related(Prefetch("attachments", to_attr="prefetched_attacments"))

    for ordered_service in ordered_services:
        if not ordered_service.prefetched_attacments:
            raise InvalidActionError(
                human=msg.SOME_SERVICES_DOES_NOT_HAVE_REQUESTED_ATTACHMENTS
            )

    instance.ordered_services.update(is_completed=True)
    instance.save(update_fields=["is_serviced"])


def is_consolidation_enabled_for_country(country, warehouses=[]):
    if not warehouses:
        warehouses = country.warehouses.all()

    return any(w.is_consolidation_enabled for w in warehouses)


def get_additional_services(country_id=None, type=None, services=None):
    services = services or AdditionalService.objects.filter(type=type)

    if country_id:
        warehouse_subquery = Warehouse.objects.filter(
            country_id=country_id, country__is_active=True, service__id=OuterRef("pk")
        ).values("pk")
        return services.annotate(warehouse_exists=Exists(warehouse_subquery)).filter(
            warehouse_exists=True
        )

    return services


def get_shipment_payment(shipment):
    return Transaction.objects.filter(
        purpose=Transaction.SHIPMENT_PAYMENT,
        related_object_identifier=shipment.identifier,
    ).first()


@db_transaction.atomic
def handover_queued_item(queued_item: QueuedItem):
    queue_client = QueueClient()

    if not queued_item.for_cashier:
        done = Status.objects.get(type=Status.SHIPMENT_TYPE, codename="done")
        shipment_ids = list(queued_item.shipments.values_list("id", flat=True))
        queue_client.publish_assigned_item(
            queued_item, to_dashboard=False, to_monitor=True, action="delete"
        )
        queued_item.delete()

        for shipment in Shipment.objects.filter(id__in=shipment_ids):
            promote_status(shipment, to_status=done)
    else:
        queued_item.queue = queued_item.dest_queue
        queued_item.dest_queue = None
        queued_item.save(update_fields=["queue", "dest_queue"])
        queue_client.publish_assigned_item(
            queued_item, to_dashboard=True, to_monitor=False
        )


def mark_queued_customer_as_serviced(queued_item: QueuedItem):
    QueueClient().publish_assigned_item(
        queued_item, to_dashboard=False, to_monitor=True, action="delete"
    )
    queued_item.delete()


# @db_transaction.atomic
# def get_service_queue_item(warehouse_id) -> QueuedItem:
#     return _add_to_queue(warehouse_id, Queue.TO_CUSTOMER_SERVICE)


def create_cashier_payment_log_callback(instances, transaction, children, **params):
    """Logs cashier payment. Used as a callback for complete_payments function."""
    staff_user_id = params.get("staff_user_id")

    if staff_user_id:
        len_instances = len(instances)

        for instance in instances:
            change_message = (
                "This shipment was paid using customer's %s by cashier."
                % transaction.type
            )
            if len_instances > 1:
                change_message += (
                    " This shipment was paid among with following shipments: %s."
                    % (", ".join(i.number for i in instances if i.id != instance.id))
                )

            LogEntry.objects.log_action(
                user_id=staff_user_id,
                content_type_id=ContentType.objects.get_for_model(instance).pk,
                object_id=instance.pk,
                object_repr=str(instance),
                action_flag=CHANGE,
                change_message=change_message,
            )


def make_completed_callback(instances, *args, **kwargs):
    """
    Makes instances completed (shipments). Used as a callback for complete_payments function.
    """
    done = Status.objects.get(type=Status.SHIPMENT_TYPE, codename="done")
    queue_client = QueueClient()
    other_already_paid_instances = []

    # Remvoe queued item first
    # It will be deleted for all instances
    if instances:
        any_shipment = instances[0]
        queued_item = any_shipment.queued_item_id and any_shipment.queued_item

        if queued_item:
            for other_shipment in queued_item.shipments.exclude(
                id__in=[instance.id for instance in instances]
            ):
                other_already_paid_instances.append(other_shipment)
            queue_client.publish_assigned_item(
                queued_item, to_dashboard=False, to_monitor=True, action="delete"
            )
            queued_item.delete()

    for instance in list(instances) + other_already_paid_instances:
        instance.queued_item = (
            None  # Set to none, because we've already deleted that item
        )
        promote_status(instance, to_status=done)


MonthlySpendings = namedtuple("MonthlySpendings", ["amount", "currency", "status"])


def calculate_monthly_spendings(recipient) -> MonthlySpendings:
    """
    Calculated monthly (current month) spendings of customer.
    Shipments must have `declared_at` field of non-null value.
    """
    customer = recipient.user

    conf = Configuration()
    monthly_spendings_currency = conf.monthly_spendings_treshold_currency

    current_date = timezone.now().date()
    shipments = customer.shipments.filter(
        recipient__id_pin=recipient.id_pin,
        declared_at__isnull=False,
        declared_at__year=current_date.year,
        declared_at__month=current_date.month,
    ).only(
        "declared_price",
        "declared_price_currency",
    )

    total_spendings = Decimal("0.00")

    for shipment in shipments:
        total_spendings += Converter.convert(
            shipment.declared_price,
            shipment.declared_price_currency.code,
            monthly_spendings_currency.code,
        )

    return MonthlySpendings(
        total_spendings,
        monthly_spendings_currency,
        conf.get_monthly_spendings_status_for_amount(total_spendings),
    )


def create_notification(
    instance, reason, subject_instances, lang_code=None, add_related_obj=True
):
    try:
        NotificationEvent(
            instance,
            reason,
            subject_instances,
            lang_code,
            add_related_obj=add_related_obj,
        ).trigger()
    except EVENTS.DoesNotExist:
        pass


def check_if_customer_can_top_up_balance(customer, payment_service):
    if payment_service in [
        Transaction.CYBERSOURCE_SERVICE,
        Transaction.PAYPAL_SERVICE,
        Transaction.PAYTR_SERVICE,
    ]:
        # Do not check that email is verified, but email is required!
        return all([customer.billed_recipient_id, customer.email])

    return None


def get_exposable_customer_payments(customer):
    is_partial = Q(is_partial=True)
    is_parent = Q(type=Transaction.MERGED)
    no_parent = Q(parent__isnull=True)
    completed = Q(completed=True)
    from_payment_service = Q(payment_service__isnull=False)
    is_cashback = Q(cashback_to__isnull=False)

    return (
        customer.transactions.filter(
            (is_parent & completed) | (no_parent & ~is_parent),
            (from_payment_service & completed)
            | (~from_payment_service)
            | (from_payment_service & is_partial & completed),
            is_deleted=False,
        )
        .exclude(is_cashback & ~completed)
        .order_by("completed", "-id")
        .select_related()
    )


def create_virtual_invoice(order_data: dict):
    """
    Creates virtual invoice from validated order data.
    """
    virtual_order = VirtualOrder(order_data)
    return get_invoice(virtual_order)


@db_transaction.atomic
def accept_box_at_customs(box: Box, tracking_status: TrackingStatus):
    """
    When box's physical weight and theoritical weight
    matches (+-) customs officer approves the box
    (if no other problem arises), thus promoting statuses
    of containing shipments.
    """
    customs_status = Status.objects.get(type=Status.SHIPMENT_TYPE, codename="customs")

    counter = 0
    # All boxes have at max 15-30 shipments
    # FIXME: Make this function async if it hurts performance
    for shipment in box.shipments.all():
        counter += 1

        if tracking_status:
            shipment.tracking_status = tracking_status
            shipment.save(update_fields=["tracking_status"])

        promote_status(shipment, to_status=customs_status)
        create_notification(
            shipment, EVENTS.ON_SHIPMENT_STATUS_CUSTOMS, [shipment, shipment.user]
        )
    return counter


def accept_shipment_at_customs(shipment: Shipment, tracking_status: TrackingStatus):
    customs_status = Status.objects.get(type=Status.SHIPMENT_TYPE, codename="customs")

    promote_status(shipment, to_status=customs_status)

    if tracking_status:
        shipment.tracking_status = tracking_status
        shipment.save(update_fields=["tracking_status"])

    return shipment


@db_transaction.atomic
def create_courier_order(user, shipments, recipient, tariff, additional_note, region):
    bad_shipments = []
    for shipment in shipments:
        if not shipment.courier_can_be_ordered:
            bad_shipments.append(shipment)

    if bad_shipments:
        raise CantPlaceCourierOrderError(bad_shipments=bad_shipments)

    created_status = Status.objects.get(
        type=Status.COURIER_ORDER_TYPE, codename="created"
    )

    courier_order = CourierOrder.objects.create(
        user=user,
        status=created_status,
        region=region,
        recipient=recipient.freeze(),
        tariff=tariff,
        additional_note=additional_note,
    )

    courier_order.shipments.set(shipments)

    return courier_order


def get_user_transactions(user, identifiers=None, invoice_numbers=None, on_error=None):
    transactions = Transaction.objects.filter(
        ~Q(type=Transaction.CASH),
        user=user,
        completed=False,
        is_deleted=False,
        # parent__isnull=True,
    )
    if identifiers:
        return transactions.filter(
            purpose__in=[
                Transaction.ORDER_PAYMENT,
                Transaction.SHIPMENT_PAYMENT,
                Transaction.ORDER_REMAINDER_PAYMENT,
                Transaction.COURIER_ORDER_PAYMENT,
            ],
            related_object_identifier__in=identifiers or [],
        )
    elif invoice_numbers:
        return transactions.filter(invoice_number__in=invoice_numbers or [])
    else:
        if on_error is not None:
            return on_error
        raise PaymentError


def save_user_country_log(user_id, country_id):
    """
    Saves country log for user. So that we can
    order countries then by user preference.
    """
    UserCountryLog.objects.update_or_create(
        user_id=user_id, country_id=country_id, defaults={"updated_at": timezone.now()}
    )


def save_government_data_to_user(data: dict, user_id: int = None, user=None):
    if not (user_id or user):
        raise ValueError("user_id or user must be provided")

    if not user:
        user = User.objects.get(id=user_id)

    user.id_pin = data.get("_pincode")
    user.id_serial_number = f"{data.get('Serial')}{data.get('series')}"
    user.real_name = data.get("Name")
    user.real_surname = data.get("Surname")
    user.real_patronymic = data.get("Patronymic")
    user.photo_base64 = data.get("Photo")

    if any(data.values()):
        user.save(
            update_fields=[
                "id_pin",
                "id_serial_number",
                "real_name",
                "real_surname",
                "real_patronymic",
                "photo_base64",
            ]
        )
        return True

    return False


def fetch_citizen_data_raw(id_pin):
    response = requests.post(
        "https://e-xidmet.eco.gov.az/index.php?lang=az&do=getPin",
        data={
            "pincode": id_pin,
            "key": "d54414929c737a054f43cfb00606a27a",
        },
    )

    return response


def fetch_citizen_data(recipient_id, save_to_user=True):
    from customer.models import Recipient

    try:
        recipient = Recipient.objects.get(id=recipient_id)
        id_pin = recipient.id_pin

        if id_pin:
            # Fetch data from government resources (WTF???)
            response = fetch_citizen_data_raw(id_pin)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if not data.get("Name"):
                        # If we don't get the name probably other fields
                        # are missing too.  # TODO: Check for other fields too.
                        raise ValueError(
                            "Data from government resource is not fully provided"
                            " or not provided at all"
                        )
                except (JSONDecodeError, ValueError):
                    return {}

                data = data.copy()
                data["_pincode"] = id_pin
                if save_to_user:
                    save_government_data_to_user(data, user=recipient.user)
                return data

    except Recipient.DoesNotExist:
        pass

    return {}


def add_discounts(
    instance: Union[Order, Shipment, CourierOrder], discounts: List[Discount]
):
    """
    Will save unsaved discounts in `discounts` as a discount for `instance`.
    Ignores other already saved discounts as it does not make sense.
    No need to shift already existing discounts to other object.
    """
    unsaved_discounts = [d for d in discounts if not d.pk]

    for unsaved_discount in unsaved_discounts:
        unsaved_discount.related_object = instance

    saved_discounts = Discount.objects.bulk_create(unsaved_discounts)


def revoke_discounts(instance: Union[Order, Shipment, CourierOrder]):
    """
    Just removed all related discounts. In the future this function may do
    something more, so it is recommended to revoke discounts using this function only.
    """
    instance.discounts.all().delete()


def generate_promo_code(user: User):
    print("generating promo code")
    existing_promo_code = getattr(user, "promo_code", None)

    if existing_promo_code:
        return existing_promo_code

    value = PromoCode.generate_new_promo_code_value()
    promo_code, created = PromoCode.objects.get_or_create(value=value, user=user)

    if not created:
        return generate_promo_code(user)

    print("generated promo code", promo_code)
    return promo_code


def get_left_promo_code_benefits(user):
    promo_code = user.registered_promo_code

    if not promo_code:
        return 0

    used_benefits_count = (
        PromoCodeBenefit.objects.filter(consumer_id=user, used_by_consumer=True)
        .values("id")
        .count()
    )
    return Configuration().invite_friend_benefit_count - used_benefits_count


def get_consumers_for_promo_code(promo_code: PromoCode):
    consumed_benefit_filter = Q(consumed_benefit__used_by_consumer=True)
    consumers = User.objects.filter(
        consumed_benefit__promo_code=promo_code,
        consumed_benefit__deleted_at__isnull=True,
    ).annotate(
        used_benefits=Count("consumed_benefit", filter=consumed_benefit_filter),
        # cashback amount is in USD already
        total_cashback_amount=Sum(
            "consumed_benefit__cashback_amount", filter=consumed_benefit_filter
        ),
    )
    return consumers


def can_get_promo_code_cashbacks(user):
    return get_left_promo_code_benefits(user) > 0


def add_cashbacks(
    instance: Union[Shipment, CourierOrder, Order], cashbacks: List[Cashback]
):
    dumped_cashbacks = [c.dump() for c in cashbacks]
    existing_cashbacks = instance.extra.get("cashback_data", [])
    existing_cashbacks += dumped_cashbacks
    instance.extra["cashback_data"] = existing_cashbacks
    instance.__class__.objects.filter(id=instance.id).update(extra=instance.extra)
    return instance


def try_create_promo_code_cashbacks(instance: Union[Shipment, CourierOrder, Order]):
    conf = Configuration()
    if conf.can_get_invite_friend_cashback(instance):
        # Check if user can get discounts from invited friends
        promo_code = getattr(instance.user, "promo_code", None)
        cashback_created = False

        if promo_code:
            cashback: Optional[Cashback] = promo_code.get_next_cashback()
            if cashback:
                add_cashbacks(instance, [cashback])
                cashback_created = True

        if not cashback_created and instance.user.registered_promo_code:
            # Check if user can get cashbacks from registered promo code
            existing_benefits = PromoCodeBenefit.objects.filter(
                consumer_id=instance.user_id,
                promo_code=instance.user.registered_promo_code,
            )

            if existing_benefits.count() < conf.invite_friend_benefit_count:
                add_cashbacks(instance, [conf.get_invite_friend_cashback()])
                PromoCodeBenefit.objects.get_or_create(
                    object_id=instance.pk,
                    object_type=ContentType.objects.get_for_model(instance),
                    related_object_identifier=instance.identifier,
                    defaults={
                        "consumer": instance.user,
                        "promo_code": instance.user.registered_promo_code,
                    },
                )


@db_transaction.atomic
def apply_cashbacks_to_promo_code_owner(transaction_id):
    try:
        transaction = Transaction.objects.get(id=transaction_id)
    except Transaction.DoesNotExist:
        return

    cashbacks = transaction.cashbacks.filter(
        completed=True, is_deleted=False, extra__invite_friend_cashback=True
    )

    for cashback in cashbacks:
        user = cashback.user
        promo_code = user.registered_promo_code
        next_cashback = promo_code.get_next_cashback()

        if next_cashback:
            cashback_transaction = Transaction.objects.create(
                user_id=promo_code.user_id,
                amount=cashback.amount,
                currency_id=cashback.currency_id,
                cashback_to=None,
                completed=True,
                type=Transaction.BALANCE,
                purpose=Transaction.CASHBACK,
                extra={"cashback_from_invited_friend": True},
            )
            balance = promo_code.user.active_balance
            balance.amount = F("amount") + Converter.convert(
                cashback_transaction.amount,
                cashback_transaction.currency.code,
                promo_code.user.active_balance.currency.code,
            )
            balance.save(update_fields=["amount"])
            balance.refresh_from_db(fields=["amount"])
            create_notification(
                cashback_transaction,
                EVENTS.ON_INVITE_FRIEND_CASHBACK_OWNER,
                [transaction.user],
                add_related_obj=False,
            )


@db_transaction.atomic
def make_objects_paid(
    instances: List[Union[CourierOrder, Shipment, Order]], user_id=None
):
    content_type_model_pk_map = {}

    for instance in instances:
        instance.is_paid = True
        instance.save(update_fields=["is_paid"])
        instance.transactions.filter(is_deleted=False).update(
            completed=True, completed_at=timezone.now(), completed_manually=True
        )
        if user_id:
            content_type_pk = content_type_model_pk_map.get(type(instance), None)

            if not content_type_pk:
                content_type_pk = ContentType.objects.get_for_model(instance).pk
                content_type_model_pk_map[type(instance)] = content_type_pk

            LogEntry.objects.log_action(
                user_id=user_id,
                content_type_id=content_type_pk,
                object_id=instance.pk,
                object_repr=str(instance),
                action_flag=CHANGE,
                change_message=("Manually marked instance as paid"),
            )
