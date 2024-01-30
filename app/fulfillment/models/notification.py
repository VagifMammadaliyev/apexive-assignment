from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import translation
from django.utils.translation import ugettext_lazy as _
from ckeditor_uploader.fields import RichTextUploadingField

from ontime import messages as msg
from customer.models import User as CustomUser
from fulfillment.models.abc import SoftDeletionModel
from fulfillment.models.order import Order
from fulfillment.models.package import Package
from fulfillment.models.shipment import Shipment
from fulfillment.models.transaction import Transaction

User = get_user_model()


class Notification(SoftDeletionModel):
    FOR_PAYMENT = "for_payment"
    FOR_ORDER = "for_order"
    FOR_SHIPMENT = "for_shipment"
    FOR_PACKAGE = "for_package"
    OTHER = "other"

    TYPES = (
        (FOR_PAYMENT, msg.FOR_PAYMENT),
        (FOR_ORDER, msg.FOR_ORDER),
        (FOR_SHIPMENT, msg.FOR_SHIPMENT),
        (FOR_PACKAGE, msg.FOR_PACKAGE),
        (OTHER, msg.OTHER),
    )

    event = models.ForeignKey(
        "fulfillment.NotificationEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        related_query_name="notification",
    )
    type = models.CharField(choices=TYPES, max_length=30)

    web_title = models.CharField(max_length=255, null=True, blank=True)
    web_text = models.TextField(null=True, blank=True)
    email_subject = models.CharField(max_length=255, null=True, blank=True)
    email_text_simple = models.TextField(null=True, blank=True)
    email_text = RichTextUploadingField(null=True, blank=True)
    sms_text = models.TextField(null=True, blank=True)

    # Related to web notification
    is_seen = models.BooleanField(default=False)
    seen_on = models.DateTimeField(null=True, blank=True)
    must_be_seen_on_web = models.BooleanField(default=True)

    is_sms_sent = models.BooleanField(default=False)
    sms_sent_on = models.DateTimeField(null=True, blank=True)
    is_email_sent = models.BooleanField(default=False)
    email_sent_on = models.DateTimeField(null=True, blank=True)

    object_id = models.CharField(max_length=15, db_index=True, null=True, blank=True)
    object_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        db_index=True,
        null=True,
        blank=True,
        limit_choices_to={
            "model__in": ["shipment", "order", "transaction", "package", "user"]
        },
    )
    related_object = GenericForeignKey("object_type", "object_id")
    related_object_identifier = models.CharField(
        max_length=50, db_index=True, null=True, blank=True
    )

    lang_code = models.CharField(max_length=5, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification"

    def __str__(self):
        return "Notification [%s type=%s]" % (self.user, self.type)

    @classmethod
    def is_sms_already_sent(cls, notification):
        return Notification.objects.filter(
            event_id=notification.event_id,
            object_id=notification.object_id,
            object_type_id=notification.object_type_id,
            is_sms_sent=True,
        ).exists()

    @classmethod
    def is_email_already_sent(cls, notification):
        return Notification.objects.filter(
            event_id=notification.event_id,
            object_id=notification.object_id,
            object_type_id=notification.object_type_id,
            is_email_sent=True,
        ).exists()


class NotificationEvent(models.Model):
    ON_USER_EMAIL_PREACTIVATE = "user_email_preactivate"
    ON_USER_BALANCE_TOPUP = "user_balance_topup"
    ON_PACKAGE_STATUS_PROBLEMATIC = "package_problematic"
    ON_PACKAGE_STATUS_FOREIGN = "package_foreign"
    ON_SHIPMENT_STATUS_TOBESHIPPED = "shipment_tobeshipped"
    ON_SHIPMENT_STATUS_ONTHEWAY = "shipment_ontheway"
    ON_SHIPMENT_STATUS_RECEIVED = "shipment_received"
    ON_SHIPMENT_STATUS_CUSTOMS = "shipment_customs"
    ON_SHIPMENT_STATUS_DONE = "shipment_done"
    ON_SHIPMENT_PAYMENT_CREATE = "payment_shipment_create"
    ON_ORDER_FULFILL = "order_fulfill"
    ON_ORDER_PAYMENT_CREATE = "paymnet_order_create"
    ON_ORDER_REJECT = "order_reject"
    ON_ORDER_COMMENT_CREATE = "order_comment"
    ON_ORDER_REMAINDER_REFUND = "order_remainder_refund"
    ON_ORDER_REMAINDER_CREATE = "order_remainder_create"
    ON_ORDER_REMAINDER_UPDATE = "order_remainder_update"
    ON_ORDER_EXTERNAL_CODE_ADD = "order_external_code_add"
    ON_INVITE_FRIEND_CASHBACK_OWNER = "invite_friend_cashback_o"
    ON_INVITE_FRIEND_CASHBACK_CONSUMER = "invite_friend_cashback_c"
    ON_COMMIT_TO_CUSTOMS = "smart_customs_commit"

    CLIENT_VARIABLES = [
        "client_code",
        "client_full_name",
        "client_email",
        "client_phone_number",
        "registered_promo_code",
        "registered_promo_code_client_full_name",
        "promo_code",
    ]

    PACKAGE_VARIABLES = [
        "package_tracking_code",
        "package_current_warehouse_title",
        "package_real_arrival_date",
        "package_destination_warehouse_title",
        "package_source_warehouse_title",
        "package_status_public_name",
    ]

    SHIPMENT_VARIABLES = [
        "shipment_status_public_name",
        "shipment_customs_tracking_status",
        "shipment_number",
        "shipment_current_warehouse_title",
        "shipment_source_warehouse_title",
        "shipment_destination_warehouse",
        "shipment_destination_user_address_title",
        "shipment_weight",
        "shipment_width",
        "shipment_length",
        "shipment_height",
    ]

    PAYMENT_VARIABLES = [
        "payment_owner",
        "payment_amount",
        "payment_amount_currency_symbol",
        "payment_amount_currency_code",
        "related_object_identifier",
    ]

    ORDER_VARIABLES = [
        "order_code",
        "order_external_code",
        "order_status_public_name",
        "order_last_comment",
        "order_product_url",
        "order_remainder_price",
        "order_remainder_price_currency_code",
        "order_remainder_price_currency_symbol",
    ]

    EMAIL_ACTIVATION_VARIABLES = ["activation_link", "sms_code"]

    REASON_VARIABLE_MAP = {
        ON_USER_EMAIL_PREACTIVATE: CLIENT_VARIABLES + EMAIL_ACTIVATION_VARIABLES,
        ON_PACKAGE_STATUS_PROBLEMATIC: CLIENT_VARIABLES + PACKAGE_VARIABLES,
        ON_PACKAGE_STATUS_FOREIGN: CLIENT_VARIABLES + PACKAGE_VARIABLES,
        ON_SHIPMENT_STATUS_TOBESHIPPED: CLIENT_VARIABLES + SHIPMENT_VARIABLES,
        ON_SHIPMENT_STATUS_ONTHEWAY: CLIENT_VARIABLES + SHIPMENT_VARIABLES,
        ON_SHIPMENT_STATUS_RECEIVED: CLIENT_VARIABLES + SHIPMENT_VARIABLES,
        ON_SHIPMENT_STATUS_CUSTOMS: CLIENT_VARIABLES + SHIPMENT_VARIABLES,
        ON_SHIPMENT_STATUS_DONE: CLIENT_VARIABLES + SHIPMENT_VARIABLES,
        ON_SHIPMENT_PAYMENT_CREATE: (
            CLIENT_VARIABLES + PAYMENT_VARIABLES + SHIPMENT_VARIABLES
        ),
        ON_ORDER_FULFILL: CLIENT_VARIABLES + ORDER_VARIABLES,
        ON_ORDER_PAYMENT_CREATE: CLIENT_VARIABLES + ORDER_VARIABLES + PAYMENT_VARIABLES,
        ON_ORDER_REJECT: CLIENT_VARIABLES + ORDER_VARIABLES + PAYMENT_VARIABLES,
        ON_ORDER_REMAINDER_CREATE: (
            CLIENT_VARIABLES + ORDER_VARIABLES + PAYMENT_VARIABLES
        ),
        ON_ORDER_REMAINDER_REFUND: (
            CLIENT_VARIABLES + ORDER_VARIABLES + PAYMENT_VARIABLES
        ),
        ON_ORDER_REMAINDER_UPDATE: (
            CLIENT_VARIABLES + ORDER_VARIABLES + PAYMENT_VARIABLES
        ),
        ON_ORDER_COMMENT_CREATE: CLIENT_VARIABLES + ORDER_VARIABLES,
        ON_ORDER_EXTERNAL_CODE_ADD: CLIENT_VARIABLES + ORDER_VARIABLES,
        ON_USER_BALANCE_TOPUP: CLIENT_VARIABLES + PAYMENT_VARIABLES,
        ON_INVITE_FRIEND_CASHBACK_CONSUMER: CLIENT_VARIABLES + PAYMENT_VARIABLES,
        ON_INVITE_FRIEND_CASHBACK_OWNER: CLIENT_VARIABLES + PAYMENT_VARIABLES,
        ON_COMMIT_TO_CUSTOMS: CLIENT_VARIABLES + SHIPMENT_VARIABLES,
    }

    REASONS = (
        (ON_USER_EMAIL_PREACTIVATE, _("İstifadəçi profildə e-poçt yazanda")),
        (ON_USER_BALANCE_TOPUP, _("İstifadəçi balansı uğurla artırdı")),
        (ON_PACKAGE_STATUS_PROBLEMATIC, _("Problemli bağlama yarandı")),
        (ON_PACKAGE_STATUS_FOREIGN, _("Bağlama xarici anbara daxil oldu")),
        (ON_SHIPMENT_STATUS_TOBESHIPPED, _("Göndərmə göndərilmək üçün hazır oldu")),
        (ON_SHIPMENT_STATUS_ONTHEWAY, _("Göndərmə hava limanına təhvil verildi")),
        (ON_SHIPMENT_STATUS_RECEIVED, _("Göndərmə yerli anbara daxil oldu")),
        (ON_SHIPMENT_STATUS_DONE, _("Göndərmə müştəriyə təhvil verildi")),
        (ON_SHIPMENT_STATUS_CUSTOMS, _("Göndərmə gömrükdə yoxlanışdan keçdi")),
        (
            ON_SHIPMENT_PAYMENT_CREATE,
            _("Göndərmənin qiyməti təyin olundu və ödəniş yarandı"),
        ),
        (ON_ORDER_FULFILL, _("Sifariş köməkçi tərəfindən verildi")),
        (ON_ORDER_PAYMENT_CREATE, _("Sifariş üçün ödəniş yarandı")),
        (ON_ORDER_REJECT, _("Sifariş köməkçi tərəfindən ləğv olundu")),
        (ON_ORDER_REMAINDER_REFUND, _("Sifarişin artıq ödənişi iadə edildi")),
        (ON_ORDER_REMAINDER_CREATE, _("Sifarişin qalıq ödənişi yarandı")),
        (ON_ORDER_REMAINDER_UPDATE, _("Sifarişin artıq ödənişi yeniləndi")),
        (ON_ORDER_COMMENT_CREATE, _("Sifarişə köməkçi tərəfindən rəy yazıldı")),
        (
            ON_ORDER_EXTERNAL_CODE_ADD,
            _("Sifarişə köməkçi tərəfindən mağaza sifariş kodu əlavə edildi"),
        ),
        (
            ON_INVITE_FRIEND_CASHBACK_CONSUMER,
            _("Promo kodu istifadə edib cashback qazandı"),
        ),
        (
            ON_INVITE_FRIEND_CASHBACK_OWNER,
            _("Promo kodu dostuna verib cashback qazandı"),
        ),
        (ON_COMMIT_TO_CUSTOMS, _("Gömrüyə bəyan olundu")),
    )

    FLAT_REASONS = [r[0] for r in REASONS]  # for easier iterating

    reason = models.CharField(choices=REASONS, max_length=50)

    title = models.CharField(max_length=255, null=True, blank=True)

    web_title = models.CharField(max_length=255, null=True, blank=True)
    web_text = models.TextField(null=True, blank=True)
    email_subject = models.CharField(max_length=255, null=True, blank=True)
    email_text_simple = models.TextField(null=True, blank=True)
    email_text = RichTextUploadingField(null=True, blank=True)
    sms_text = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "notification_event"
        unique_together = ["reason", "is_active"]

    def __str__(self):
        return "Notification event [reason=%s active=%s]" % (
            self.reason,
            self.is_active,
        )

    @classmethod
    def _get_order_context(cls, order: Order):
        last_comment = order.comments.order_by("id").last()

        return {
            "order_code": order.order_code,
            "order_last_comment": last_comment and last_comment.body or "<?>",
            "order_external_code": order.external_order_code,
            "order_status_public_name": order.status_id
            and order.status.display_name
            or "<?>",
            "order_product_url": order.product_url,
            "order_remainder_price": str(order.remainder_price),
            "order_remainder_price_currency_code": order.remainder_price_currency_id
            and order.remainder_price_currency.code,
            "order_remainder_price_currency_symbol": order.remainder_price_currency_id
            and order.remainder_price_currency.symbol,
        }

    @classmethod
    def _get_package_context(cls, package: Package):
        return {
            "package_tracking_code": package.tracking_code,
            "package_current_warehouse_title": package.current_warehouse_id
            and package.current_warehouse.title,
            "package_real_arrival_date": package.real_arrival_date.strftime("%Y/%m/%d")
            if package.real_arrival_date
            else "<?>",
            "package_destination_warehouse_title": package.shipment_id
            and package.shipment.destination_warehouse_id
            and package.shipment.destination_warehouse.title
            or "<?>",
            "package_source_warehouse_title": package.shipment_id
            and package.shipment.source_warehouse_id
            and package.shipment.source_warehouse.title
            or "<?>",
            "package_status_public_name": package.status_id
            and package.status.display_name
            or "<?>",
        }

    @classmethod
    def _get_shipment_context(cls, shipment: Shipment):
        return {
            "shipment_status_public_name": shipment.status_id
            and shipment.status.display_name
            or "<?>",
            "shipment_customs_tracking_status": shipment.tracking_status_id
            and shipment.tracking_status.mandatory_comment
            or (
                shipment.tracking_status_id
                and shipment.tracking_status.tracking_code_description
            )
            or "<?>",
            "shipment_number": shipment.number,
            "shipment_current_warehouse_title": shipment.current_warehouse_id
            and shipment.current_warehouse.title
            or "<?>",
            "shipment_source_warehouse_title": shipment.source_warehouse_id
            and shipment.source_warehouse.title
            or "<?>",
            "shipment_destination_warehouse": shipment.destination_warehouse_id
            and shipment.destination_warehouse.title
            or "<?>",
            "shipment_destination_user_address_title": shipment.recipient_id
            and shipment.recipient.address
            or "<?>",
            "shipment_weight": shipment.fixed_total_weight,
            "shipment_width": shipment.fixed_width,
            "shipment_length": shipment.fixed_length,
            "shipment_height": shipment.fixed_height,
        }

    @classmethod
    def _get_payment_context(cls, transaction: Transaction):
        return {
            "payment_owner": transaction.user.full_name,
            "payment_amount": str(transaction.amount),
            "payment_amount_currency_symbol": transaction.currency_id
            and transaction.currency.symbol
            or "<?>",
            "payment_amount_currency_code": transaction.currency_id
            and transaction.currency.code,
            "related_object_identifier": transaction.related_object_identifier,
        }

    @classmethod
    def _get_client_context(cls, client: CustomUser):
        promo_code = getattr(client, "promo_code", "<?>")
        return {
            "client_code": client.client_code,
            "client_full_name": client.full_name,
            "client_email": client.email,
            "client_phone_number": client.full_phone_number,
            "registered_promo_code": client.registered_promo_code_id
            and client.registered_promo_code.value
            or "<?>",
            "registered_promo_code_client_full_name": client.registered_promo_code_id
            and client.registered_promo_code.user.full_name
            or "<?>",
            "promo_code": promo_code and promo_code.value or "<?>",
        }

    @classmethod
    def get_context(cls, *instances):
        """
        TODO: This method should actually be on instance itself, may be...
        """
        context = {}

        for instance in instances:
            if isinstance(instance, dict):
                context.update(instance)  # just update the context
            if isinstance(instance, Order):
                context.update(cls._get_order_context(instance))
            elif isinstance(instance, Package):
                context.update(cls._get_package_context(instance))
            elif isinstance(instance, User):
                context.update(cls._get_client_context(instance))
            elif isinstance(instance, Transaction):
                context.update(cls._get_payment_context(instance))
            elif isinstance(instance, Shipment):
                context.update(cls._get_shipment_context(instance))
            else:
                pass  # ...we don't know how to extract context from other objects

        return context

    @classmethod
    def get_display_for_reason(cls, reason):
        for _reason, display_text in cls.REASONS:
            if _reason == reason:
                return display_text

        return None

    @property
    def sends_sms(self):
        return bool(self.sms_text)

    @property
    def sends_email(self):
        return bool(self.email_text_simple or self.email_text)
