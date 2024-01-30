from __future__ import absolute_import, unicode_literals

from smtplib import SMTPException
from django.db import transaction as db_transaction
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone, translation
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.db.models import F
from celery import shared_task

from ontime.celery import QUEUES
from ontime.utils import fix_rich_text_image_url, FakeRequest
from domain.conf import Configuration
from domain.utils.autofill import AutoFiller
from domain.utils.smart_customs import CustomsClient, filter_addable_shipments
from poctgoyercin.utils import send_sms_to_customer
from poctgoyercin.exceptions import PoctGoyercinError
from fulfillment.models import (
    Notification,
    Order,
    Assignment,
    NotificationEvent,
    Shipment,
    OrderedProduct,
)


@shared_task(queue=QUEUES.NOTIFICATIONS)
def send_notification(notification_id):
    if not Configuration().are_notifications_enabled:
        return "Notifications are not enabled! Not sending... ID: %d" % (
            notification_id
        )

    sms_sent = False
    email_sent = False
    event = None
    errors = []

    event_id, object_id, object_type_id = (
        Notification.objects.filter(id=notification_id)
        .values_list("event_id", "object_id", "object_type_id")
        .first()
    )
    notifications = Notification.objects.select_for_update().filter(
        event_id=event_id, object_id=object_id, object_type_id=object_type_id
    )

    with db_transaction.atomic():
        notification = None
        for locked_notification in notifications:
            if locked_notification.id == notification_id:
                notification = locked_notification
                break
        if not notification:
            return "No notification found with id=%d" % notification_id
        event = notification.event
        if notification.lang_code:
            translation.activate(notification.lang_code)

        if notification.user_id:
            # Send sms
            if (
                not Notification.is_sms_already_sent(notification)
                and not notification.is_sms_sent
                and notification.user.phone_is_verified
                and notification.sms_text
            ):
                try:
                    send_sms_to_customer(notification.user, notification.sms_text)
                    notification.is_sms_sent = True
                    notification.sms_sent_on = timezone.now()
                    notification.save(update_fields=["is_sms_sent", "sms_sent_on"])
                    sms_sent = True
                except PoctGoyercinError as err:
                    errors.append(str(err))

            # Send e-mail
            if not Notification.is_email_already_sent(notification) and (
                notification.event_id
                and notification.event.reason
                == NotificationEvent.ON_USER_EMAIL_PREACTIVATE
                or (
                    not notification.is_email_sent
                    and notification.user.email_is_verified
                    and (notification.email_text or notification.email_text_simple)
                )
            ):
                try:
                    send_mail(
                        notification.email_subject,
                        notification.email_text_simple,
                        settings.DEFAULT_FROM_EMAIL,
                        [notification.user.email],
                        html_message=fix_rich_text_image_url(
                            FakeRequest(), notification.email_text
                        ),
                        fail_silently=False,
                    )
                    notification.is_email_sent = True
                    notification.email_sent_on = timezone.now()
                    notification.save(update_fields=["is_email_sent", "email_sent_on"])
                    email_sent = True
                except SMTPException as err:
                    errors.append(str(err))

    return (
        f"Email sent={email_sent}, sms sent={sms_sent} for notification {notification_id}."
        f" Errors={errors}. Event={event}"
    )


@shared_task(autoretry_for=(Exception,))
def assign_orders_to_operator(order_ids):
    from domain.services import get_assistant_with_minimum_workload

    assignments = []

    for order in Order.objects.filter(id__in=order_ids, as_assignment__isnull=True):
        lazy_assistant = get_assistant_with_minimum_workload(order.source_country_id)
        assignments.append(
            Assignment(
                assistant_profile=lazy_assistant,
                order=order,
            )
        )

    if assignments:
        Assignment.objects.bulk_create(assignments)


@shared_task
def send_manifest_by_email(transportation_id):
    """We need only transporation ID to export manifest data :)"""
    from domain.utils import XMLManifestGenerator, ManifestError

    generator = XMLManifestGenerator(transportation_id=transportation_id)
    manifest_data = generator.generate()


@shared_task
def save_image_link_for_orders(order_ids=None, all_orders=False):
    orders = Order.objects.none()
    if all_orders:
        orders = Order.objects.all()
    else:
        orders = Order.objects.filter(id__in=order_ids or [])

    for order in orders:
        if order.product_url:
            autofiller = AutoFiller(order=order)
            autofiller.save_image_to_order()


@shared_task
def save_ordered_products_in_shipment(shipment_ids=None):
    if not shipment_ids:
        shipment_ids = []

    shipments = Shipment.objects.filter(id__in=shipment_ids)

    ordered_products = []

    for shipment in shipments:
        for package in shipment.packages.filter(order__isnull=False):
            order: Order = package.order_id and package.order

            if order:
                ordered_product = OrderedProduct(
                    user=order.user,
                    order=order,
                    shipment=shipment,
                    user_description=order.description,
                    description=order.product_description,
                    url=order.product_url,
                    color=order.product_color,
                    size=order.product_size,
                    image=order.product_image_url,
                    country_id=order.source_country_id,
                    category_id=order.product_category_id,
                    price_currency_id=order.product_price_currency_id,
                    price=order.product_price,
                    shipping_price=shipment.total_price,
                    shipping_price_currency_id=shipment.total_price_currency_id,
                    shop_id=order.shop_id,
                    is_visible=order.show_on_slider,
                )
                ordered_products.append(ordered_product)

    if ordered_products:
        OrderedProduct.objects.bulk_create(ordered_products)

    return f"{len(ordered_products)} ordered products saved from {shipment}"


@shared_task
def apply_cashbacks_to_promo_code_owner_task(completed_transaction_id):
    from domain.services import apply_cashbacks_to_promo_code_owner

    apply_cashbacks_to_promo_code_owner(completed_transaction_id)


@shared_task
def mark_as_paid_task(ct_pk, instance_ids, admin_id=None):
    from domain.services import make_objects_paid

    try:
        ct = ContentType.objects.get(pk=ct_pk)
    except ContentType.DoesNotExist:
        return

    ct_class = ct.model_class()
    instances = ct_class.objects.filter(id__in=instance_ids)

    make_objects_paid(instances, user_id=admin_id)


@shared_task(queue=QUEUES.CUSTOMS)
def update_customs_product_types():
    client = CustomsClient()
    client.update_product_types()


@shared_task(queue=QUEUES.CUSTOMS)
def commit_to_customs(shipment_ids):
    client = CustomsClient()
    conf = Configuration()
    shipments = Shipment.objects.filter(
        is_declared_to_customs=False,
        id__in=shipment_ids,
        is_deleted_from_smart_customs=False,
        is_deleted_from_smart_customs_by_us=False,
    )
    shipments = conf.filter_customs_commitable_shipments(shipments)
    if shipments:
        client.commit_packages(shipments)
    else:
        print("no shipments to commit")


@shared_task(queue=QUEUES.CUSTOMS)
def delete_from_customs(shipment_ids, admin_id):
    client = CustomsClient()
    shipments = Shipment.objects.filter(
        is_declared_to_customs=True,
        id__in=shipment_ids,
        is_deleted_from_smart_customs_by_us=False,
    )
    for s in shipments.iterator():
        client.delete_package(s, admin_id)


@shared_task(queue=QUEUES.CUSTOMS)
def refresh_declared_packages():
    client = CustomsClient()
    client.refresh_packages_states_from_smart_customs()


@shared_task(queue=QUEUES.CUSTOMS)
def add_to_customs_box(shipment_ids):
    client = CustomsClient()
    shipments = filter_addable_shipments(Shipment.objects.filter(id__in=shipment_ids))
    client.add_to_boxes(shipments)


@shared_task(queue=QUEUES.CUSTOMS)
def depesh_to_customs(transportation_ids):
    shipments = Shipment.objects.filter(
        box__transportation_id__in=transportation_ids,
        box__transportation__airwaybill__isnull=False,
        is_depeshed=False,
        is_declared_by_user=True,
        is_deleted_from_smart_customs=False,
    ).select_related("box__transportation")
    client = CustomsClient()
    client.depesh_packages(shipments)
