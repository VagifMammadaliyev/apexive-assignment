from django.urls import path
from rest_framework import routers

from fulfillment.views.customer import order as order_views
from fulfillment.views.customer import balance as balance_views
from fulfillment.views.customer import package as package_views
from fulfillment.views.customer import shipment as shipment_views
from fulfillment.views.customer import misc as misc_views
from fulfillment.views.customer import recipient as recipient_views
from fulfillment.views.customer import payment as payment_views
from fulfillment.views.customer import notification as notification_views
from fulfillment.views.customer import subscription as subscription_views
from fulfillment.views.customer import contact_us as contact_us_views
from fulfillment.views.customer import ticket as ticket_views
from fulfillment.views.customer import courier as courier_views
from fulfillment.views import common as common_views

router = routers.SimpleRouter()
router.register("recipients", recipient_views.RecipientViewSet, basename="recipient")
router.register(
    "notifications",
    notification_views.NotificationReadOnlyViewSet,
    basename="notification",
)
router.register("ticketing", ticket_views.TicketViewSet, basename="ticket")

urlpatterns = [
    path(
        "ordered-products-slider/",
        common_views.OrderedProductListApiView.as_view(),
        name="ordered-product-slider",
    ),
    path(
        "orders/",
        order_views.OrderListCreateApiView.as_view(),
        name="order-list-create",
    ),
    path(
        "orders/<str:order_code>/",
        order_views.OrderRetrieveUpdateDestroyApiView.as_view(),
        name="order-retrieve-update-destroy",
    ),
    path(
        "orders/<str:order_code>/invoice/",
        order_views.order_invoice_view,
        name="order-invoice",
    ),
    path(
        "orders/<str:order_code>/timeline/",
        order_views.order_timeline_view,
        name="order-timeline",
    ),
    path(
        "orders/<str:order_code>/comments/",
        order_views.CommentListCreateApiView.as_view(),
        name="comment-list-create",
    ),
    path(
        "order/<str:order_code>/archive/",
        order_views.order_archive_view,
        name="order-archive",
    ),
    path(
        "order/archive/",
        order_views.order_bulk_archive_view,
        name="order-bulk-archive",
    ),
    path(
        "orders/calculator/commission-price/",
        order_views.calculate_commission_price_view,
        name="commission-price-calc",
    ),
    path(
        "orders/calculator/virtual-invoice/",
        order_views.create_virtual_invoice_view,
        name="order-virtual-invoice",
    ),
    path(
        "packages/",
        package_views.PackageListCreateApiView.as_view(),
        name="package-list",
    ),
    path(
        "packages/<str:tracking_code>/",
        package_views.PackageRetrieveUpdateDestroyApiView.as_view(),
        name="package-retrieve-update-destroy",
    ),
    path(
        "packages/<str:tracking_code>/timeline/",
        package_views.package_timeline_view,
        name="package-timeline",
    ),
    path(
        "package/<str:tracking_code>/archive/",
        package_views.package_archive_view,
        name="package-archive",
    ),
    path(
        "package/archive/",
        package_views.package_bulk_archive_view,
        name="package-bulk-archive",
    ),
    path(
        "shipments/",
        shipment_views.ShipmentListCreateApiView.as_view(),
        name="shipment-list",
    ),
    path(
        "shipments/<str:number>/",
        shipment_views.ShipmentRetrieveApiView.as_view(),
        name="shipment-retrieve-update-destroy",
    ),
    path(
        "shipments/<str:number>/invoice/",
        shipment_views.shipment_invoice_view,
        name="shipment-invoice",
    ),
    path(
        "shipments/<str:number>/timeline/",
        shipment_views.shipment_timeline_view,
        name="shipment-timeline",
    ),
    path(
        "shipments/<str:number>/delete/",
        shipment_views.ShipmentDeleteView.as_view(),
        name="shipment-delete",
    ),
    path(
        "shipment/<str:number>/archive/",
        shipment_views.shipment_archive_view,
        name="shipment-archive",
    ),
    path(
        "shipment/archive/",
        shipment_views.shipment_bulk_archive_view,
        name="shipment-bulk-archive",
    ),
    path(
        "shipment/<str:number>/check-smart-customs/",
        shipment_views.check_smart_customs_declaration,
        name="check_smart_customs",
    ),
    path("balance/", balance_views.balance_view, name="customer-balance"),
    path(
        "balance/cybersource/form-data/",
        balance_views.cybersource_payment_form,
        name="balance-cybersource-form-data",
    ),
    path(
        "balance/paypal/orders/",
        balance_views.set_up_paypal_transaction_view,
        name="balance-paypal-create-order",
    ),
    path(
        "balance/paytr/set-up/",
        balance_views.set_up_paytr_transaction_view,
        name="balance-paytr-setup",
    ),
    path(
        "balance/test-balance/",
        balance_views.test_cyber_add_balance_view,
        name="test-balance",
    ),
    path("dashboard/", misc_views.dashboard_view, name="customer-dashboard"),
    path("pay/", payment_views.payment_view, name="payment"),
    path("payments/", payment_views.PaymentListApiView.as_view(), name="payment-list"),
    path(
        "payments/<uuid:invoice_number>/",
        payment_views.PaymentDetailApiView.as_view(),
        name="payment-detail",
    ),
    path(
        "payments/multiple-invoices/",
        payment_views.multiple_payment_invoice_view,
        name="multiple-invoice",
    ),
    path(
        "payments/<uuid:invoice_number>/invoice/",
        payment_views.payment_invoice_view,
        name="payment-invoice",
    ),
    path(
        "payment/<uuid:invoice_number>/archive/",
        payment_views.payment_archive_view,
        name="payment-archive",
    ),
    path(
        "payment/archive/",
        payment_views.payment_bulk_archive_view,
        name="payment-bulk-archive",
    ),
    path(
        "recipients/bulk-delete/",
        recipient_views.bulk_delete_recipients_view,
        name="recipient-bulk-delete",
    ),
    path(
        "recipients/<int:pk>/set-as-billing/",
        recipient_views.set_billed_recipient_view,
        name="set-billed-recipient",
    ),
    path(
        "notification-data/",
        notification_views.get_unseen_notifications_data_view,
        name="notification-data",
    ),
    path(
        "notifications/mark-all-as-seen/",
        notification_views.mark_all_as_read,
        name="mark_all_as_seen",
    ),
    path(
        "subscribe/",
        subscription_views.SubscriberCreateApiView.as_view(),
        name="subscribe-newsletter",
    ),
    path(
        "contact-us/",
        contact_us_views.ContactUsMessageCreateApiView.as_view(),
        name="contact-us-form",
    ),
    path(
        "ticketing/categories/",
        ticket_views.TicketCategoryListApiView.as_view(),
        name="ticket-category-list",
    ),
    path(
        "ticketing/related-items/",
        ticket_views.TicketRelatedObjectListApiView.as_view(),
        name="ticket-related-object-list",
    ),
    path(
        "ticketing/<int:ticket_pk>/comments/",
        ticket_views.TicketCommentListCreateApiView.as_view(),
        name="ticket-comment-list-create",
    ),
    path(
        "ticket/<str:number>/archive/",
        ticket_views.ticket_archive_view,
        name="ticket-archive",
    ),
    path(
        "ticket/archive/",
        ticket_views.ticket_bulk_archive_view,
        name="ticket-bulk-archive",
    ),
    path(
        "courier-orders/",
        courier_views.CourierOrderListApiView.as_view(),
        name="courier-order-list",
    ),
    path(
        "courier-orders/<str:number>/",
        courier_views.CourierOrderDetailApiView.as_view(),
        name="courier-order-detail",
    ),
    path(
        "courier-orders/<str:number>/invoice/",
        courier_views.courier_order_invoice_view,
        name="courier-order-invoice",
    ),
    path(
        "courier-order/<str:number>/archive/",
        courier_views.courier_order_archive_view,
        name="courier-order-archive",
    ),
    path(
        "courier-order/archive/",
        courier_views.courier_order_bulk_archive_view,
        name="courier-order-bulk-archive",
    ),
    path(
        "partial-payments/<str:payment_service>/",
        payment_views.MakePaymentPartialApiView.as_view(),
        name="partial-payment-cybersource",
    ),
    path(
        "autofill-product/",
        misc_views.ProductAutofillApiView.as_view(),
        name="autofill-product",
    ),
    path("ulduzum/check/", payment_views.ulduzum_check_view, name="ulduzum-check"),
    path("ulduzum/cancel/", payment_views.ulduzum_cancel_view, name="ulduzum-cancel"),
    path(
        "promo-code/data/",
        misc_views.PromoCodeDataView.as_view(),
        name="promo-code-data",
    ),
]


urlpatterns += router.urls
