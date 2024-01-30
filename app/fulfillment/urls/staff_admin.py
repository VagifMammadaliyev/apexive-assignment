from django.urls import path
from rest_framework import routers

from fulfillment.views.admin import shopping_assistant as sa_views

# from fulfillment.views.admin import customers as customer_views
from fulfillment.views.admin import staff_users as staff_views
from fulfillment.views.admin import warehouseman as wh_views
from fulfillment.views.admin import cashier as cash_views
from fulfillment.views.admin import queue as queue_views
from fulfillment.views.admin import customs as customs_views
from fulfillment.views.admin import customer_service as customer_service_views

router = routers.SimpleRouter()
# router.register("customers", customer_views.CustomerViewSet)
router.register("shopping-assistants", staff_views.ShoppingAssistantProfileViewSet)
router.register(
    "warehouseman/transportations",
    wh_views.TransportationViewSet,
    basename="transportation",
)
router.register("warehouseman/dashboard/boxes", wh_views.BoxViewSet, basename="box")
router.register(
    "customer-service/tickets", customer_service_views.TicketViewSet, basename="ticket"
)
router.register("shopping_assistant/shops", sa_views.ShopViewSet)

urlpatterns = [
    # Shopping assistant
    path(
        "shopping_assistant/dashboard/",
        sa_views.DashboardApiView.as_view(),
        name="shopping-assistant-dashboard",
    ),
    path(
        "shopping_assistant/orders/<str:order_code>/",
        sa_views.OrderRetrieveUpdateDestroyApiView.as_view(),
        name="order-detail-update-destroy",
    ),
    path(
        "shopping_assistant/orders/<str:order_code>/comments/",
        sa_views.comment_order_view,
        name="order-comment-list-create",
    ),
    path(
        "shopping_assistant/orders/<str:order_code>/approve-remainder/",
        sa_views.approve_remainder_price_view,
        name="order-approve-remainder",
    ),
    path(
        "shopping_assistant/packages/",
        sa_views.create_packages_from_orders_view,
        name="packages-from-orders-create",
    ),
    # path(
    #     "shopping_assistant/autocomplete-users/",
    #     sa_views.autocomplete_user_view,
    #     name="user-autocomplete",
    # ),
    path(
        "shopping_assistant/autocomplete-assistants/",
        sa_views.autocomplete_assistant_view,
        name="assistant-autocomplete",
    ),
    path(
        "assignments/<int:assignment_id>/reassign/",
        sa_views.reassign_shopping_assistant_view,
        name="reassign-assignments",
    ),
    path(
        "assignment-statuses/",
        sa_views.AssignmentStatusListApiView.as_view(),
        name="assignment-status-list",
    ),
    path(
        "assignments/<int:assignment_id>/start-processing/",
        sa_views.start_processing_order_view,
        name="start-processing-assignment",
    ),
    # Warehouseman
    path(
        "warehouseman/accept-package/",
        wh_views.accept_incoming_package_view,
        name="accept-package",
    ),
    path(
        "warehouseman/dashboard/packages/",
        wh_views.PackageDashboardApiView.as_view(),
        name="warehouseman-dashboard-for-packages",
    ),
    path(
        "warehouseman/dashboard/packages/<int:pk>/",
        wh_views.PackageRetrieveUpdateApiView.as_view(),
        name="warehouseman-package-detail-update",
    ),
    path(
        "warehouseman/dashboard/client-packages/",
        wh_views.PackageByClientApiView.as_view(),
        name="warehouseman-package-by-client",
    ),
    path(
        "warehouseman/dashboard/packages/<int:pk>/services/",
        wh_views.PackageOrderedServiceListApiView.as_view(),
        name="warehouseman-package-ordered-service-list",
    ),
    path(
        "warehouseman/dashboard/packages/<int:package_id>/services/<int:ordered_service_id>/mark-completed/",
        wh_views.mark_single_package_service_as_completed_view,
        name="warehouseman-package-mark-ordered-service",
    ),
    path(
        "warehouseman/dashboard/packages/<int:pk>/mark-serviced/",
        wh_views.mark_package_as_serviced_view,
        name="warehouseman-package-mark-serviced",
    ),
    path(
        "warehouseman/dashboard/shipments/",
        wh_views.ShipmentDashboardApiView.as_view(),
        name="warehouseman-dashboard-for-shipments",
    ),
    path(
        "warehouseman/dashboard/shipments/<str:number>/",
        wh_views.ShipmentRetrieveUpdateApiView.as_view(),
        name="warehouseman-shipment-detail-update",
    ),
    path(
        "warehouseman/dashboard/shipments/<str:number>/services/",
        wh_views.ShipmentOrderedServiceListApiView.as_view(),
        name="warehouseman-shipment-ordered-service-list",
    ),
    path(
        "warehouseman/dashboard/shipments/<str:number>/services/<int:ordered_service_id>/mark-completed/",
        wh_views.mark_single_shipment_service_as_completed_view,
        name="warehouseman-shipment-mark-ordered-service",
    ),
    path(
        "warehouseman/dashboard/shipments/<str:number>/mark-serviced/",
        wh_views.mark_shipment_as_serviced_view,
        name="warehouseman-shipment-mark-serviced",
    ),
    path(
        "warehouseman/dashboard/shipments/<str:number>/confirm/",
        wh_views.confirm_shipment_properties_view,
        name="confirm-shipment-properties",
    ),
    path(
        "warehouseman/dashboard/packages/problematic/",
        wh_views.ProblematicPackageCreateApiView.as_view(),
        name="warehouseman-problematic-package-create",
    ),
    path(
        "warehouseman/accepted-shipments/<str:number>/",
        wh_views.AcceptedShipmentReadApiView.as_view(),
        name="accepted-shipment-read",
    ),
    path(
        "warehouseman/accept-shipment/",
        wh_views.accept_incoming_shipment_view,
        name="accept-shipment",
    ),
    path(
        "warehouseman/dashboard/shipments/<str:number>/place/",
        wh_views.place_accepted_shipment,
        name="place-accepted-shipment",
    ),
    path(
        "shipment-statuses/",
        wh_views.ShipmentStatusListApiView.as_view(),
        name="warahouseman-shipment-statuses",
    ),
    path(
        "warehouseman/destination-warehouses/",
        wh_views.WarehouseListApiView.as_view(),
        name="dest-warehouse-list",
    ),
    path(
        "warehouseman/ordered-services/<int:pk>/",
        wh_views.OrderedServiceFulFillApiView.as_view(),
        name="fulfill-ordered-service",
    ),
    path(
        "warehouseman/transportation-cities/",
        wh_views.CityListApiView.as_view(),
        name="transportation-city-list",
    ),
    path(
        "warehouseman/dashboard/shipments/<str:number>/airway-bill/",
        wh_views.ShipmentAirwayBillApiView.as_view(),
        name="shipment-airway-bill",
    ),
    path(
        "warehouseman/transportations/<int:pk>/send-xml-manifest/",
        wh_views.ExportXMLManifestApiView.as_view(),
        name="transportation-send-xml-manifest",
    ),
    path(
        "warehouseman/transportations/<int:pk>/export-manifest/",
        wh_views.ExportManifestApiView.as_view(),
        name="trasnportation-export-manifest",
    ),
    path(
        "warehouseman/packages/<int:pk>/generate-invoice/",
        wh_views.PackageInvoiceApiView.as_view(),
        name="warehouseman-generate-package-invoice",
    ),
    path(
        "warehouseman/shipments/<str:number>/generate-invoice/",
        wh_views.ShipmentInvoiceApiView.as_view(),
    ),
    # Queue
    # path(
    #     "cashier/dashboard/",
    #     cash_views.CashierDashboardApiView.as_view(),
    #     name="cashier-dashboard",
    # ),
    path(
        "queues/cashier/pay/",
        queue_views.pay_for_shipment_view,
        name="pay-shipment",
    ),
    path(
        "monitor/customer-service/reserve/",
        queue_views.add_customer_to_service_queue_view,
        name="monitor-customer-service-queue-enter",
    ),
    path(
        "monitor/customer-shipments/",
        queue_views.CustomerShipmentListApiView.as_view(),
        name="monitor-customer-shipment-list-add-to-queue",
    ),
    path(
        "monitor/items/", queue_views.MonitorApiView.as_view(), name="monitor-item-list"
    ),
    path("queues/", queue_views.QueueListApiView.as_view(), name="queue-list"),
    path(
        "queues/<int:pk>/items/",
        queue_views.QueuedItemListApiView.as_view(),
        name="queued-item-list",
    ),
    path(
        "queues/<int:queue_pk>/items/<int:item_pk>/ready/",
        queue_views.complete_queued_item_view,
        name="queued-item-complete",
    ),
    path(
        "queues/<int:queue_pk>/items/<int:item_pk>/shipments/<str:shipment_number>/check/",
        queue_views.check_shipment_as_found_view,
        name="queued-item-shipment-check",
    ),
    path(
        "queues/<int:queue_pk>/items/<int:item_pk>/handover/",
        queue_views.handover_queued_item_view,
        name="queued-item-handover",
    ),
    path(
        "queues/<int:queue_pk>/items/<int:item_pk>/mark-serviced/",
        queue_views.mark_queued_customer_as_serviced_view,
        name="queued-item-mark-serviced",
    ),
    path(
        "queues/<int:queue_pk>/accept-next/",
        queue_views.accept_next_queued_item_view,
        name="queue-accept-next-item",
    ),
    path(
        "queues/<int:queue_pk>/can-get-next/",
        queue_views.can_get_next_item_view,
        name="queue-can-get-next",
    ),
    path(
        "queues/<int:queue_pk>/items/<int:item_pk>/receiver-info/",
        queue_views.ReceiverInfoApiView.as_view(),
        name="queue-receiver-info",
    ),
    path(
        "queues/customer-service/problem-logs/",
        queue_views.CustomerServiceLogListCreateApiView.as_view(),
        name="queue-customer-service-problem-log",
    ),
    # Customs manager
    path(
        "customs/boxes/<str:box_code>/",
        customs_views.BoxRetrieveApiView.as_view(),
        name="customs-box-detail",
    ),
    path(
        "customs/boxes/<str:box_code>/accept/",
        customs_views.accept_box_view,
        name="customs-accept-box",
    ),
    path(
        "customs/tracking/statuses/",
        customs_views.TrackingStatusListApiView.as_view(),
        name="customs-tracking-status-list",
    ),
    path(
        "customs/shipments/<str:number>/",
        customs_views.ShipmentRetrieveApiView.as_view(),
        name="customs-shipment-detail",
    ),
    path(
        "customs/shipments/<str:number>/accept/",
        customs_views.accept_shipment_view,
        name="customs-accept-shipment",
    ),
    path(
        "customer-service/ticket-categories/",
        customer_service_views.TicketCategoryListApiView.as_view(),
        name="cservice-ticket-category-list",
    ),
    path(
        "customer-service/ticket-statuses/",
        customer_service_views.TicketStatusListApiView.as_view(),
        name="cservice-ticket-status-list",
    ),
    path(
        "customer-service/tickets/<int:ticket_pk>/comments/",
        customer_service_views.TicketCommentListCreateApiView.as_view(),
        name="cservice-ticket-comment-list-create",
    ),
    path(
        "customer-service/customers/<int:user_pk>/related-items/",
        customer_service_views.AdminTicketRelatedObjectListApiView.as_view(),
        name="cservice-customer-related-item-list",
    ),
    # MISC
    path(
        "misc/gov-api/data-by-pin/",
        queue_views.fetch_customer_data_using_pin,
        name="misc-gov-pin-data",
    ),
]


urlpatterns += router.urls
