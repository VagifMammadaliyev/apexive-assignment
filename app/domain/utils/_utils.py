import json
from typing import Union, List
from decimal import Decimal
from xml.dom.minidom import parseString
from itertools import zip_longest

import pytz
import dicttoxml

# import xlsxwriter
from django.core.files.base import ContentFile
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction as db_transaction
from django.db.models import Prefetch, F, Count, Q, Sum
from django.contrib.admin.models import ContentType
from django.utils import translation, timezone
from django.template import Template, Context
from django.utils.translation import ugettext_lazy as _
from djangorestframework_camel_case.render import CamelCaseJSONRenderer

from ontime import messages as msg
from poctgoyercin.utils import send_sms_to_customer
from domain.exceptions.logic import InvalidActionError, QueueError, ManifestError
from domain.conf import Configuration
from ontime.utils import get_redis_client
from core.converter import Converter
from core.models import Currency
from customer.models import Role
from fulfillment.models import (
    Shipment,
    Order,
    CourierOrder,
    QueuedItem,
    Queue,
    Notification as _Notification,
    NotificationEvent as _NotificationEvent,
    Transaction,
    Package,
    Tariff,
    CourierArea,
    CourierRegion,
    Transportation,
)
from fulfillment.tasks import send_notification

utc = pytz.utc


def from_warehouseman_timezone(value, timezone: str):
    return value.replace(tzinfo=pytz.timezone(timezone)).utcnow().replace(tzinfo=utc)


def to_warehouseman_timezone(value, timezone: str):
    return value.replace(tzinfo=pytz.timezone(timezone)).utcnow().replace(tzinfo=utc)


class VirtualOrder:
    """
    Virtual order class that simulates real order object.
    Needed for creating Invoice for unsaved order object.
    """

    def __init__(self, order_data: dict):
        conf = Configuration()

        self.source_country = order_data.get("source_country")
        self.total_price_currency = self.source_country and self.source_country.currency
        self.total_price_currency_id = (
            self.total_price_currency and self.total_price_currency.id
        )
        self.product_quantity = order_data.get("product_quantity", 1)
        self.product_price = order_data.get("product_price", Decimal("0.00"))
        self.product_price_currency = self.total_price_currency
        self.product_price_currency_id = self.total_price_currency_id
        self.cargo_price = order_data.get("cargo_price", Decimal("0.00"))
        self.cargo_price_currency = self.total_price_currency
        self.cargo_price_currency_id = self.total_price_currency_id
        self.total_price = self.product_price * self.product_quantity + self.cargo_price
        self.commission_price = conf.calculate_commission_for_price(
            self.total_price, self.total_price_currency
        )
        self.commission_price_currency = self.total_price_currency
        self.commission_price_currency_id = self.total_price_currency_id
        self.total_price += self.commission_price  # don't forget the commission price


class Invoice:
    def __init__(self, instance: Union[Order, VirtualOrder, Shipment]):
        shipment = None
        order = None
        courier_order = None

        if isinstance(instance, Shipment):
            shipment = instance
        elif isinstance(instance, (Order, VirtualOrder)):
            order = instance
        elif isinstance(instance, CourierOrder):
            courier_order = instance

        self.shipment: Shipment = shipment
        self.order: Order = order
        self.courier_order = courier_order
        self.instance = instance
        self.reasons = []

        self.main_total = Decimal("0")
        self.main_total_currency = None

    def get_reasons(self):
        if self.reasons:
            return self.reasons

        reasons = []

        if self.shipment:
            reasons = self.get_reasons_for_shipment()
        elif self.order:
            reasons = self.get_reasons_for_order()
        elif self.courier_order:
            reasons = self.get_reasons_for_courier_order()

        return reasons

    def get_reasons_for_shipment(self, shipment=None, desc_prefix=""):
        reasons = []
        shipment: Shipment = shipment or self.shipment
        # tariff = shipment.get_matching_tariff()

        if (
            shipment.total_price and shipment.total_price_currency_id
        ):  # if there is no total price or total price currency, then invoice is empty
            reasons.append(
                InvoiceReason(
                    description=desc_prefix + str(msg.TARIFF_PRICE),
                    price=shipment.total_price,
                    currency=shipment.total_price_currency,
                    instance=self.instance,
                )
            )

            # Fetch related shipment services
            shipment_services = shipment.ordered_services.all()

            for shipment_service in shipment_services:
                reasons.append(
                    InvoiceReason(
                        description=desc_prefix
                        + str(msg.SERVICE_DESCRIPTION_FMT)
                        % {"service_title": shipment_service.service.title},
                        price=Converter.convert(
                            shipment_service.service.price,
                            shipment_service.service.price_currency.code,
                            shipment.total_price_currency.code,
                        ),
                        currency=shipment.total_price_currency,
                        instance=self.instance,
                    )
                )

            # Fetch related package services
            for package in shipment.packages.prefetch_related(
                Prefetch("ordered_services", to_attr="prefetched_services")
            ):
                for package_service in package.prefetched_services:
                    reasons.append(
                        InvoiceReason(
                            description=msg.PACKAGE_SERVICE_DESCRIPTION_FMT
                            % {
                                "package_tracking_code": package.tracking_code,
                                "service_title": package_service.service.title,
                            },
                            price=Converter.convert(
                                package_service.service.price,
                                package_service.service.price_currency.code,
                                shipment.total_price_currency.code,
                            ),
                            currency=shipment.total_price_currency,
                            instance=self.instance,
                        )
                    )

        return reasons

    def get_reasons_for_courier_order(self):
        reasons = []
        courier_order: CourierOrder = self.courier_order

        courier_order.raw_total_price = courier_order.total_price
        courier_order.raw_total_price_currency = courier_order.total_price_currency

        shipments = courier_order.shipments.filter(is_paid=False)
        for shipment in shipments:
            courier_order.total_price += Converter.convert(
                shipment.total_price,
                shipment.total_price_currency.code,
                courier_order.total_price_currency.code,
            )
            reasons += self.get_reasons_for_shipment(
                shipment=shipment, desc_prefix="%s: " % (shipment.number)
            )

        if courier_order.total_price and courier_order.total_price_currency_id:
            reasons.append(
                InvoiceReason(
                    description=msg.COURIER_PRICE,
                    price=courier_order.raw_total_price,
                    currency=courier_order.raw_total_price_currency,
                    instance=self.instance,
                )
            )

        return reasons

    def get_reasons_for_order(self):
        from core.serializers.client import CurrencySerializer

        reasons = []
        order: Order = self.order

        if order.real_product_price and order.real_product_price_currency_id:
            reasons.append(
                InvoiceReason(
                    description=msg.PRODUCT_PRICE,
                    price=Converter.convert(
                        order.real_product_price * order.real_product_quantity,
                        order.real_product_price_currency.code,
                        order.real_total_price_currency.code,
                    ),
                    currency=order.total_price_currency,
                    # override={
                    #     "is_active": bool(order.remainder_price),
                    #     "price": {
                    #         "amount": Converter.convert(
                    #             order.real_product_price * order.real_product_quantity,
                    #             order.real_product_price_currency.code,
                    #             order.real_total_price_currency.code,
                    #         ),
                    #         "currency": CurrencySerializer(
                    #             order.real_total_price_currency
                    #         ).data,
                    #     },
                    #     "quantity": order.real_product_quantity,
                    # },
                    extra={"quantity": order.product_quantity},
                    instance=self.instance,
                )
            )

        if order.real_cargo_price and order.real_cargo_price_currency_id:
            reasons.append(
                InvoiceReason(
                    description=msg.INCOUNTRY_CARGO_PRICE,
                    price=Converter.convert(
                        order.real_cargo_price,
                        order.real_cargo_price_currency.code,
                        order.real_total_price_currency.code,
                    ),
                    currency=order.real_total_price_currency,
                    instance=self.instance,
                    # override={
                    #     "is_active": bool(order.remainder_price),
                    #     "price": {
                    #         "amount": Converter.convert(
                    #             order.real_cargo_price,
                    #             order.real_cargo_price_currency.code,
                    #             order.real_total_price_currency.code,
                    #         ),
                    #         "currency": CurrencySerializer(
                    #             order.real_total_price_currency
                    #         ).data,
                    #     },
                    # },
                )
            )

        if order.real_commission_price and order.real_commission_price_currency_id:
            reasons.append(
                InvoiceReason(
                    description=msg.COMMISSION_PRICE,
                    price=Converter.convert(
                        order.real_commission_price,
                        order.real_commission_price_currency.code,
                        order.real_total_price_currency.code,
                    ),
                    currency=order.real_total_price_currency,
                    instance=self.instance,
                    # override={
                    #     "is_active": bool(order.remainder_price),
                    #     "price": {
                    #         "amount": Converter.convert(
                    #             order.real_commission_price,
                    #             order.real_commission_price_currency.code,
                    #             order.real_total_price_currency.code,
                    #         ),
                    #         "currency": CurrencySerializer(
                    #             order.real_total_price_currency
                    #         ).data,
                    #     },
                    # },
                )
            )

        if self.order.real_total_price != self.order.total_price:
            self.order.total_price = self.order.real_total_price

        return reasons

    def serialize(self):
        reasons = self.get_reasons()

        if reasons:
            from core.serializers.client import CurrencySerializer

            payment_service_currency_codes = set(
                [settings.PAYPAL_CURRENCY_CODE, settings.CYBERSOURCE_CURRENCY_CODE]
            )

            remainder_transaction = None
            if self.order:
                remainder_transaction = Transaction.objects.filter(
                    purpose=Transaction.ORDER_REMAINDER_PAYMENT,
                    user=self.instance.user_id,
                    related_object_identifier=self.instance.identifier,
                ).first()

            if not self.order or not self.order.remainder_price:
                missing_amount = (
                    Converter.convert(
                        self.instance.discounted_total_price,
                        self.instance.discounted_total_price_currency.code,
                        self.instance.user.as_customer.active_balance.currency.code,
                    )
                    - self.instance.user.as_customer.active_balance.amount
                )
                is_missing = missing_amount > 0 and not self.instance.is_paid
            else:
                if remainder_transaction:
                    missing_amount = (
                        Converter.convert(
                            remainder_transaction.discounted_amount,
                            remainder_transaction.discounted_amount_currency.code,
                            self.instance.user.as_customer.active_balance.currency.code,
                        )
                        - self.instance.user.as_customer.active_balance.amount
                    )

                is_missing = (
                    bool(remainder_transaction)
                    and not remainder_transaction.completed
                    and missing_amount > 0
                )
            missing_amount_currency = CurrencySerializer(
                self.instance.user.as_customer.active_balance.currency
            ).data

            main_total = Converter.convert(
                self.instance.total_price,
                self.instance.total_price_currency.code,
                self.instance.user.as_customer.active_balance.currency.code,
            )
            main_total_currency = self.instance.user.as_customer.active_balance.currency
            self.main_total = main_total
            self.main_total_currency = main_total_currency

            discounted_total_price = self.instance.discounted_total_price
            discounted_total_price_currency = (
                self.instance.discounted_total_price_currency
            )
            discount_is_active = discounted_total_price < Converter.convert(
                main_total,
                main_total_currency.code,
                discounted_total_price_currency.code,
            )

            self.discounted_total_price = discounted_total_price
            self.discounted_total_price_currency = discounted_total_price_currency
            self.discount_is_active = discount_is_active

            return {
                "discount": {
                    "is_active": discount_is_active,
                    "amount": str(discounted_total_price),
                    "currency": CurrencySerializer(
                        discounted_total_price_currency
                    ).data,
                    "reasons": [
                        {
                            "percentage": str(d.percentage),
                            "reason": d.get_reason_display(),
                        }
                        for d in self.instance.discounts.all()
                    ],
                },
                "totals": [
                    {
                        "amount": str(main_total),
                        "is_main": True,
                        "currency": CurrencySerializer(main_total_currency).data,
                    }
                ]
                + (
                    [
                        {
                            "amount": str(self.instance.total_price),
                            "currency": CurrencySerializer(
                                self.instance.total_price_currency
                            ).data,
                            "is_main": False,
                        }
                    ]
                    if self.instance.total_price_currency_id
                    != self.instance.user.as_customer.active_balance.currency_id
                    else []
                ),
                "missing": {
                    "is_active": is_missing,
                    "amount": str(missing_amount) if is_missing else None,
                    "currency": missing_amount_currency if is_missing else None,
                },
                "order_remainders": (
                    [
                        {
                            "amount": str(
                                Converter.convert(
                                    remainder_transaction.discounted_amount,
                                    remainder_transaction.discounted_amount_currency.code,
                                    self.instance.user.as_customer.active_balance.currency.code,
                                )
                            ),
                            "currency": CurrencySerializer(
                                self.instance.user.as_customer.active_balance.currency,
                            ).data,
                            "is_main": True,
                        }
                    ]
                    + (
                        [
                            {
                                "amount": str(remainder_transaction.amount)
                                if remainder_transaction
                                else None,
                                "currency": CurrencySerializer(
                                    remainder_transaction.currency
                                ).data,
                                "is_main": False,
                            }
                        ]
                        if remainder_transaction.currency_id
                        != self.instance.user.active_balance.currency_id
                        else []
                    )
                )
                if remainder_transaction
                else None,
                "reasons": [
                    reason.serialize(number=number)
                    for number, reason in enumerate(reasons, start=1)
                ],
            }

        return None


class InvoiceReason:
    def __init__(
        self, description, price, currency, instance=None, override=None, extra=None
    ):
        self.description = description
        self.price = round(price, 2)
        self.currency = currency
        self.override = override
        self.extra = extra or {}
        self.instance = instance

    def serialize(self, number=1, serialize_related_object=False):
        from core.serializers.client import CurrencySerializer

        return {
            "number": number,
            "description": self.description,
            "price": {
                "amount": str(self.price),
                "currency": CurrencySerializer(self.currency).data,
            },
            "object": self.instance.serialize_for_payment()
            if serialize_related_object and self.instance
            else None,
            **self.extra,
            # "price_preview": "%s%s" % (self.price, self.currency.symbol),
        }


class MergedInvoice:
    def __init__(self, user, invoices):
        self.invoices: List[Invoice] = invoices
        self.user = user

    def serialize(self):
        from core.serializers.client import CurrencySerializer

        active_balance = self.user.as_customer.active_balance
        reasons = []

        discounted_total = 0

        for invoice in self.invoices:
            invoice.serialize()
            discounted_total += Converter.convert(
                invoice.discounted_total_price,
                invoice.discounted_total_price_currency.code,
                active_balance.currency.code,
            )
            for reason in invoice.get_reasons():
                reasons.append(reason)

        total_price = round(
            sum(
                Converter.convert(
                    invoice.instance.total_price,
                    invoice.instance.total_price_currency.code,
                    active_balance.currency.code,
                )
                for invoice in self.invoices
            ),
            2,
        )

        return {
            "discount": {
                "is_active": discounted_total < total_price,
                "amount": str(discounted_total),
                "currency": CurrencySerializer(active_balance.currency).data,
            },
            "totals": [
                {
                    "amount": str(total_price),
                    "is_main": True,
                    "currency": CurrencySerializer(active_balance.currency).data,
                }
            ],
            "missing": {
                "is_active": False,
                "amount": None,
                "currency": None,
            },
            "reasons": [
                reason.serialize(number=number, serialize_related_object=True)
                for number, reason in enumerate(reasons, start=1)
            ],
        }


class CHANNELS:
    def __getitem__(self, key):
        return self._map[key]


class DASHBOARD_CHANNELS(CHANNELS):
    WH_DASHBOARD = "warehouseman_dashboard"
    CASHIER_DASHBOARD = "cashier_dashboard"
    CUSTOMER_SERVICE_DASHBOARD = "customer_service_dashboard"
    _map = {
        Queue.TO_CASHIER: CASHIER_DASHBOARD,
        Queue.TO_WAREHOUSEMAN: WH_DASHBOARD,
        Queue.TO_CUSTOMER_SERVICE: CUSTOMER_SERVICE_DASHBOARD,
    }


class MONITOR_CHANNELS(CHANNELS):
    MAIN_MONITOR = "monitor"
    WH_MONITOR = "warehouseman_monitor"
    CASHIER_MONITOR = "cashier_monitor"
    CUSTOMER_SERVICE_MONITOR = "customer_service_monitor"
    _map = {
        Queue.TO_CASHIER: CASHIER_MONITOR,
        Queue.TO_WAREHOUSEMAN: WH_MONITOR,
        Queue.TO_CUSTOMER_SERVICE: CUSTOMER_SERVICE_MONITOR,
    }


class NOTIFY_CHANNELS(CHANNELS):
    WH_NOTIFY = "warehouseman_notification"
    CASHIER_NOTIFY = "cashier_notification"
    CUSTOMER_SERVICE_NOTIFY = "customer_service_notification"
    _map = {
        Queue.TO_CASHIER: CASHIER_NOTIFY,
        Queue.TO_WAREHOUSEMAN: WH_NOTIFY,
        Queue.TO_CUSTOMER_SERVICE: CUSTOMER_SERVICE_NOTIFY,
    }


DASHBOARD_CHANNELS = DASHBOARD_CHANNELS()
MONITOR_CHANNELS = MONITOR_CHANNELS()
NOTIFY_CHANNELS = NOTIFY_CHANNELS()


class QueueClient:
    def __init__(self, redis_client=None):
        from fulfillment.serializers.admin import queue as serializers

        self.redis_client = redis_client
        if not self.redis_client:
            self.redis_client = get_redis_client()
        self.serializers = serializers

    def publish_assignable_item(self, queued_item: QueuedItem):
        """
        Publishes to some notify channel (inforsm that staff member can get next item)
        """
        base_data = {
            "warehouse_id": queued_item.warehouse_id,
        }

        if queued_item.user_id:
            if queued_item.for_cashier and queued_item.warehouseman_ready:
                # Notify cashier that he can get next item
                self._publish(
                    NOTIFY_CHANNELS.CASHIER_NOTIFY,
                    {**base_data, "item": {"can_get": True}},
                )
            elif not queued_item.warehouseman_ready:
                self._publish(
                    NOTIFY_CHANNELS.WH_NOTIFY, {**base_data, "item": {"can_get": True}}
                )
        else:
            # self._publish(
            #    NOTIFY_CHANNELS.CUSTOMER_SERVICE_NOTIFY,
            #    {**base_data, "item": {"can_get": True}},
            # )
            self._publish(
                NOTIFY_CHANNELS.CASHIER_NOTIFY,
                {**base_data, "item": {"can_get": True}},
            )

    def publish_assigned_item(
        self, queued_item: QueuedItem, to_dashboard=True, to_monitor=True, action="add"
    ):
        base_dashboard_data = {
            "warehouse_id": queued_item.warehouse_id,
            "queue_id": queued_item.queue_id,
            "queue_code": queued_item.queue_id and queued_item.queue.code,
            # "monitor_code": (queued_item.queue_id and queued_item.queue.monitor.code),
            "action": action,
        }
        base_monitor_data = {"warehouse_id": queued_item.warehouse_id, "action": action}

        if to_dashboard:
            self._publish(
                DASHBOARD_CHANNELS[queued_item.queue.type],
                {
                    **base_dashboard_data,
                    "item": self.serializers.QueuedItemSerializer(queued_item).data,
                },
            )

        if to_monitor:
            self._publish(
                MONITOR_CHANNELS.MAIN_MONITOR,
                {
                    **base_monitor_data,
                    "item": self.serializers.MonitorQueuedItemSerializer(
                        queued_item
                    ).data,
                },
            )

    def _publish(self, channel, data):
        self.redis_client.publish(channel, CamelCaseJSONRenderer().render(data))


class QueueManager:
    def __init__(self, warehouse, staff_user):
        self.warehouse = warehouse
        self.client = QueueClient()

    @property
    def last_queue_number(self):
        self.warehouse.last_queue_number = F("last_queue_number") + 1
        self.warehouse.save(update_fields=["last_queue_number"])
        self.warehouse.refresh_from_db(fields=["last_queue_number"])
        return self.warehouse.last_queue_number

    def generate_queue_code(self):
        return str(self.last_queue_number).rjust(3, "0")

    def add_customer_to_queue(self):
        """Just created queued item with no user."""
        queued_item = QueuedItem.objects.create(
            warehouse=self.warehouse,
            code=self.generate_queue_code(),
        )

        self.client.publish_assignable_item(queued_item)
        self.client.publish_assigned_item(
            queued_item, to_monitor=True, to_dashboard=False
        )

        return queued_item

    @db_transaction.atomic
    def add_shipments_to_queue(self, shipments):
        # Shipments that passed must be filtered by caller,
        # we just check that filtered shipments exists
        if not shipments:
            raise InvalidActionError(human=msg.SHIPMENTS_ARE_ALREADY_DONE_OR_IN_QUEUE)

        customer_id = shipments[0].user_id
        warehouse = shipments[0].current_warehouse

        # Create dangling queued item (item with no queue)
        queued_item: QueuedItem = QueuedItem.objects.create(
            warehouse=warehouse,
            code=self.generate_queue_code(),
            for_cashier=any(not shipment.is_paid for shipment in shipments),
            user_id=customer_id,
        )
        queued_item.shipments.set(shipments)

        self.client.publish_assigned_item(
            queued_item, to_monitor=True, to_dashboard=False
        )
        self.client.publish_assignable_item(queued_item)

        return queued_item

    def accept_next_item(self, queue: Queue):
        queued_item: QueuedItem = self.get_next_queued_item(queue)

        if queued_item:
            return self.assign_item_to_queue(queued_item, queue)

        raise QueueError(human=msg.NO_QUEUED_ITEM)

    def get_next_queued_item(self, queue: Queue):
        if queue.type == Queue.TO_WAREHOUSEMAN:
            return (
                QueuedItem.objects.filter(
                    warehouse=self.warehouse,
                    user__isnull=False,
                    queue__isnull=True,
                    warehouseman_ready=False,
                )
                .order_by("id")
                .first()
            )

        if queue.type == Queue.TO_CASHIER:
            return (
                QueuedItem.objects.filter(
                    Q(
                        warehouse=self.warehouse,
                        user__isnull=False,
                        queue__type=Queue.TO_WAREHOUSEMAN,
                        warehouseman_ready=True,
                        dest_queue__isnull=True,
                        cashier_ready=False,
                    )
                    | Q(
                        warehouse=self.warehouse,
                        user__isnull=True,
                        queue__isnull=True,
                        customer_service_ready=False,
                    )
                )
                .order_by("id")
                .first()
            )

        if queue.type == Queue.TO_CUSTOMER_SERVICE:
            return (
                QueuedItem.objects.filter(
                    warehouse=self.warehouse,
                    user__isnull=True,
                    queue__isnull=True,
                    customer_service_ready=False,
                )
                .order_by("id")
                .first()
            )

        return None

    def assign_item_to_queue(self, item: QueuedItem, queue: Queue):
        if item.queue_id and not item.for_cashier:
            raise QueueError(human=msg.QUEUE_IS_ALREADY_SET)

        if item.user_id:
            if queue.type == Queue.TO_CUSTOMER_SERVICE:
                raise QueueError(human=msg.CANT_SET_TO_CUSTOMER_SERVICE_QUEUE)

            if item.for_cashier:
                if queue.type == Queue.TO_WAREHOUSEMAN:
                    if item.warehouseman_ready:
                        raise QueueError(human=msg.CANT_RESET_WAREHOUSEMAN_QUEUE)

                elif queue.type == Queue.TO_CASHIER:  # Special case!!!
                    if item.cashier_ready:
                        raise QueueError(human=msg.CANT_RESET_CASHIER_QUEUE)

                    if not item.warehouseman_ready:
                        raise QueueError(
                            human=msg.CANT_SET_TO_CASHIER_QUEUE_BYPASSING_WAREHOUSEMAN_APPROVAL
                        )

                    item.dest_queue = queue
                    item.save(update_fields=["dest_queue"])
                    self.client.publish_assigned_item(
                        item, to_dashboard=True, to_monitor=False
                    )
                    return item  # skip further execution

            else:  # warehouseman must handover to customer (direct)
                if queue.type == Queue.TO_CASHIER:
                    raise QueueError(human=msg.CANT_SET_TO_CASHIER_QUEUE)
        # else:
        #     if not queue.type == Queue.TO_CUSTOMER_SERVICE:
        #         raise QueueError(human=msg.CAN_SET_ONLY_TO_CUSTOMER_SERVICE_QUEUE)

        item.queue = queue
        item.save(update_fields=["queue"])
        # self.client.publish_assigned_item(item, to_monitor=False, to_dashboard=True)
        return item

    def make_item_ready(self, item: QueuedItem):
        if item.queue_id:
            if item.queue.type == Queue.TO_WAREHOUSEMAN:
                item.warehouseman_ready = True
                item.save(update_fields=["warehouseman_ready"])

                self.client.publish_assignable_item(item)
                self.client.publish_assigned_item(
                    item,
                    to_monitor=not item.for_cashier,
                    to_dashboard=False,
                )

            elif item.queue.type == Queue.TO_CASHIER:
                item.cashier_ready = True
                item.save(update_fields=["cashier_ready"])

                self.client.publish_assigned_item(
                    item, to_monitor=True, to_dashboard=False
                )

            elif item.queue.type == Queue.TO_CUSTOMER_SERVICE:
                item.customer_service_ready = True
                item.save(update_fields=["customer_service_ready"])

                self.client.publish_assigned_item(
                    item, to_monitor=True, to_dashboard=False
                )


# WARNING: Deprecated class, trigger only notification events!
# TODO: Remove this class
class Notification:
    """
    Wrapper around Notification model that knows how to notify.
    This is done to separate logic from Django model.

    Also this class takes care about translated title and body fields.
    """

    def __init__(self, instance, title, body=None, is_seen=False):
        """
        Note: `title` and `body` param must be
        translatable strings (wrapped by *gettext* function).
        """
        self.related_object = instance
        self.is_seen = is_seen
        self.title = title
        self.body = body
        self.notification_object = None

    def save(self, send=True) -> _Notification:
        notification_type = Notification.get_notification_type(self.related_object)
        self.notification_object = _Notification.objects.create(
            type=notification_type,
            user_id=self.related_object.user_id,
            is_seen=self.is_seen,
            related_object=self.related_object,
            related_object_identifier=self.related_object.identifier,
            **self._get_translated_field_values(["title", "body"]),
        )

        if send:
            cxn = db_transaction.get_connection()
            if cxn.in_atomic_block:
                db_transaction.on_commit(self.send)
            else:
                self.send()

        return self.notification_object

    def send(self):
        """
        Send notifications using SMS, e-mail using celery task.
        """
        send_notification.delay(self.notification_object.id)

    def _get_translated_field_values(self, field_names=None):
        """
        Return dictionary that can be passed to objects.create() method
        instead of directly passing title and body (or any other translated) field.
        """
        field_values = {}

        for field_name in field_names:
            for lang_code, lang_name in settings.LANGUAGES:
                with translation.override(lang_code):
                    field_values["%s_%s" % (field_name, lang_code)] = str(
                        getattr(self, field_name)
                    )

        return field_values

    @classmethod
    def get_notification_type(cls, instance):
        if isinstance(instance, Transaction):
            return _Notification.FOR_PAYMENT
        elif isinstance(instance, Shipment):
            return _Notification.FOR_SHIPMENT
        elif isinstance(instance, Order):
            return _Notification.FOR_ORDER
        elif isinstance(instance, Package):
            return _Notification.FOR_PACKAGE
        return _Notification.OTHER


class NotificationEvent:
    """
    Wrapper around NotificationEvent model that knows how to trigger notification events.
    This class knows how to handle some unwanted cases, such as when notification event
    missin fields, user have not selected notification language and so on.

    Also this class takes care about translated title and body fields.
    """

    def __init__(
        self,
        initiator_object,
        reason,
        subject_instances,
        lang_code=None,
        add_related_obj=True,
    ):
        self.initiator = initiator_object
        self.reason = reason
        self.subject_instances = [initiator_object] + subject_instances
        self.lang_code = lang_code
        self.add_related_object = add_related_obj

        self._event = _NotificationEvent.objects.filter(
            is_active=True, reason=self.reason
        ).first()

        if not self._event:
            raise _NotificationEvent.DoesNotExist

    def render(self, text):
        template = Template(text)
        context = Context(_NotificationEvent.get_context(*self.subject_instances))
        return template.render(context)

    def get_rendered_text(self, field_name):
        if getattr(self._event, field_name, None):
            return self.render(getattr(self._event, field_name))
        return None

    def get_rendered_text_in_all_languages(self, field_name):
        result = {}

        for lang_code, lang_name in settings.LANGUAGES:
            with translation.override(lang_code):
                result["%s_%s" % (field_name, lang_code)] = self.get_rendered_text(
                    field_name
                )

        return result

    def get_notification(self) -> _Notification:
        web_title = self.get_rendered_text_in_all_languages("web_title")
        web_text = self.get_rendered_text_in_all_languages("web_text")
        must_be_seen_on_web = all(web_title.values())
        email_subject = self.get_rendered_text_in_all_languages("email_subject")
        email_text = self.get_rendered_text_in_all_languages("email_text")
        email_text_simple = self.get_rendered_text_in_all_languages("email_text_simple")
        sms_text = self.get_rendered_text_in_all_languages("sms_text")
        related_object_variables = (
            {
                "related_object": self.initiator,
                "related_object_identifier": self.initiator.identifier,
            }
            if self.add_related_object
            else {}
        )

        notification = _Notification.objects.create(
            event=self._event,
            user_id=self.initiator.user_id,
            type=NotificationEvent.get_notification_type(
                self.initiator if self.add_related_object else None
            ),
            must_be_seen_on_web=must_be_seen_on_web,
            lang_code=self.lang_code,
            **web_title,
            **web_text,
            **email_subject,
            **email_text,
            **email_text_simple,
            **sms_text,
            **related_object_variables,
        )

        return notification

    def trigger(self) -> _Notification:
        """
        Triggers event and returns created notification.
        """
        self.notification_object = self.get_notification()

        cxn = db_transaction.get_connection()
        if cxn.in_atomic_block:
            db_transaction.on_commit(self._send)
        else:
            self._send()

        return self.notification_object

    def _send(self):
        return send_notification.delay(self.notification_object.id)

    def _get_translated_field(
        self, from_object, from_field_name, to_field_name=None, default=None
    ):
        to_field_name = to_field_name or from_field_name

        fields = {}

        for lang_code, lang_name in settings.LANGUAGES:
            fields["%s_%s" % (to_field_name, lang_code)] = getattr(
                from_object, "%s_%s" % (from_field_name, from_object), default
            )

        return fields

    @classmethod
    def get_notification_type(cls, instance):
        if isinstance(instance, Transaction):
            return _Notification.FOR_PAYMENT
        elif isinstance(instance, Shipment):
            return _Notification.FOR_SHIPMENT
        elif isinstance(instance, Order):
            return _Notification.FOR_ORDER
        elif isinstance(instance, Package):
            return _Notification.FOR_PACKAGE
        return _Notification.OTHER


class ShipmentDimensions:
    def __init__(self, h, w, l):
        self.h = h
        self.w = w
        self.l = l

    @property
    def volume_weight(self):
        return Decimal(self.w * self.h * self.l) / Decimal("6000.00")


class TariffCalculator:
    def calculate(
        self,
        shipment: Shipment = None,
        weight=None,
        dimensions=None,
        source_id=None,
        destination_id=None,
        is_dangerous=False,
        is_by_country=False,
    ):
        if shipment:
            dimensions = shipment.dimensions
            weight = shipment.total_weight

            if is_by_country:
                source_id = (
                    shipment.source_warehouse_id
                    and shipment.source_warehouse.city_id
                    and shipment.source_warehouse.city.country_id
                )
                destination_id = (
                    shipment.destination_warehouse_id
                    and shipment.destination_warehouse.city_id
                    and shipment.destination_warehouse.city.country_id
                )
            else:
                source_id = (
                    shipment.source_warehouse_id and shipment.source_warehouse.city_id
                )
                destination_id = (
                    shipment.destination_warehouse_id
                    and shipment.destination_warehouse.city_id
                )
            is_dangerous = shipment.is_dangerous

        volume_weight = dimensions.volume_weight if dimensions else 0
        customs_weight = max(weight, volume_weight)

        matching_tariff: Tariff = Tariff.objects.get_for_weight(
            customs_weight, source_id, destination_id, is_dangerous, is_by_country
        )

        if matching_tariff:
            return (
                matching_tariff.calculate_price_for_weight(customs_weight),
                matching_tariff,
            )

        return None, None


class CourierCalculator:
    def calculate(self, region_id, tariff_id):
        region = CourierRegion.objects.filter(id=region_id).first()

        if region:
            tariff = region.area.tariffs.filter(id=tariff_id).first()
            if tariff:
                return tariff.active_price, tariff.price_currency

        return None, None


class XMLManifestGenerator:
    """
    Generates manifiest from transportation or shipments or boxes in XML.

    Note: you can generate data in other formats too. But this class is for XML.
    """

    FORMAT_XML = "xml"
    FORMAT_PYTHON = "python"
    FORMAT_JSON = "json"

    def __init__(
        self,
        transportation_id=None,
        shipment_ids=None,
        box_ids=None,
        ignore_errors=False,
    ):
        self.transportation = Transportation.objects.filter(
            id=transportation_id
        ).first()
        shipment_ids = shipment_ids or []
        self.shipments = (
            Shipment.objects.filter(id__in=shipment_ids)
            .annotate(total_products_quantity=Sum("package__product__quantity"))
            .all()
        )
        self.shipments |= self._extract_shipments_from_transportation(
            self.transportation
        )
        self.shipments |= self._extract_shipments_from_boxes(box_ids)

    # self.shipments.annotate(
    #     products_quantity=Count("package__product__quantity")
    # ).select_related("declared_price_currency").distinct()

    def _extract_shipments_from_boxes(self, box_ids):
        if not box_ids:
            return Shipment.objects.none()

        return Shipment.objects.filter(box_id__in=box_ids)

    def _extract_shipments_from_transportation(self, transportation):
        if not transportation:
            return Shipment.objects.none()

        boxes = transportation.boxes.all()
        return Shipment.objects.filter(
            box_id__in=transportation.boxes.values_list("id", flat=True)
        )

    def _generate(self):
        goods = []

        conf = Configuration()
        for number, shipment in enumerate(
            self.shipments, start=self.transportation.ordering_starts_at
        ):
            first_package = shipment.packages.first()
            goods.append(
                {
                    "TR_NUMBER": number,
                    "DIRECTION": "1",  # constant
                    "QUANTITY_OF_GOODS": shipment.total_products_quantity,
                    "WEIGHT_GOODS": str(round(shipment.total_weight, 2)),
                    "INVOYS_PRICE": shipment.declared_price,
                    "CURRENCY_TYPE": shipment.declared_price_currency.number,
                    "NAME_OF_GOODS": shipment.declared_items_title,
                    "IDXAL_NAME": shipment.recipient.full_name,
                    "IDXAL_ADRESS": shipment.recipient.address
                    or shipment.recipient.real_recipient.address,
                    # "IXRAC_NAME": conf.company_name_for_manifest,
                    "IXRAC_NAME": ", ".join(
                        shipment.packages.values_list("seller", flat=True)
                    ),
                    "IXRAC_ADRESS": shipment.get_sender_address(),
                    "GOODS_TRAFFIC_FR": shipment.source_warehouse.country.number,
                    "GOODS_TRAFFIC_TO": shipment.destination_warehouse.country.number,
                    "QAIME": shipment.number,
                    "TRACKING_NO": first_package and first_package.tracking_code or "",
                    "FIN": shipment.recipient.id_pin,
                    "PHONE": shipment.recipient.phone_number,
                }
            )

        return {"GoodsInfo": goods}

    def generate(self, save_to_transportation=True, send=True) -> ContentFile:
        data = self.generate_raw(format_=self.FORMAT_XML)

        manifest_file = ContentFile(data)

        if save_to_transportation and self.transportation:
            self.transportation.xml_manifest.save(
                "%d_manifest.xml" % (self.transportation.id), manifest_file
            )
            self.transportation.xml_manifest_last_export_time = timezone.now()
            self.transportation.save(
                update_fields=["xml_manifest_last_export_time", "xml_manifest"]
            )

        if send:
            conf = Configuration()
            now = timezone.now()

            email = EmailMessage(
                "XML Manifest (ONTIME) - %s" % now.strftime("%Y/%m/%d %H:%M:%S"),
                "XML Manifest for transportation",
                settings.DEFAULT_FROM_EMAIL,
                [conf.manifest_report_email],
            )

            email.attach(
                "manifest_%s.xml" % (now.strftime("%Y_%m_%d")), data, "application/xml"
            )
            email.send()

        return manifest_file

    def generate_raw(self, format_=FORMAT_PYTHON, raise_error=False):
        manifest_data = self._generate()

        if not manifest_data:
            if raise_error:
                raise ManifestError
            return b""

        if format_ == self.FORMAT_XML:
            data = dicttoxml.dicttoxml(
                manifest_data,
                attr_type=False,
                root=False,
                custom_root="GoodsInfo",
                item_func=lambda x: "GOODS",
            )
            dom = parseString(data)
            return dom.toprettyxml()

        if format_ == self.FORMAT_JSON:
            return json.dumps(manifest_data)

        if format_ == self.FORMAT_PYTHON:
            return manifest_data


def group_items(iterable, group_size, remove_none_items=True):
    """Divides iterable into groups with `group_size`."""
    result = list(zip_longest(*(iter(iterable),) * group_size))
    if remove_none_items and result:
        result[-1] = tuple(filter(lambda el: el is not None, result[-1]))
    return result


def get_intervals_from_date_range(start_date, end_date, interval=None):
    assert start_date < end_date, "start_date must be earlier than end_date"
    if not interval:
        interval = datetime.timedelta(days=1)
    ranges = []
    current_date = start_date
    while current_date < end_date:
        next_date = current_date + interval
        ranges.append((current_date, next_date))
        current_date = next_date
    return ranges
