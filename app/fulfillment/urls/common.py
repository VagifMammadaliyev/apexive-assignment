from django.urls import path
from django.views.decorators.cache import cache_page
from fulfillment.views import common as views


urlpatterns = [
    path("warehouses/", views.WarehouseApiView.as_view(), name="warehouse-list"),
    path(
        "order-statuses/",
        cache_page(5 * 60)(views.OrderStatusListApiView.as_view()),
        name="order-status-list",
    ),
    path(
        "package-statuses/",
        cache_page(5 * 60)(views.PackageStatusListApiView.as_view()),
        name="package-status-list",
    ),
    path(
        "shipment-statuses/",
        cache_page(5 * 60)(views.ShipmentStatusListApiView.as_view()),
        name="shipment-status-list",
    ),
    path(
        "ticket-statuses/",
        cache_page(5 * 60)(views.TicketStatusListApiView.as_view()),
        name="ticket-status-list",
    ),
    path(
        "courier-order-statuses/",
        cache_page(5 * 60)(views.CourierOrderListApiView.as_view()),
        name="courier-order-status-list",
    ),
    path(
        "tariff-calculator/",
        views.TariffCalculatorApiView.as_view(),
        name="tariff-calculator",
    ),
    path(
        "product-categories/",
        views.ProductCategoryListApiView.as_view(),
        name="product-category-list",
    ),
    path(
        "product-categories/<int:category_pk>/product-types/",
        views.product_types_view,
        name="product-types-list",
    ),
    path(
        "additional-services/",
        views.AdditionalServiceListApiView.as_view(),
        name="additional-service-list",
    ),
    path("regions/", views.CourierRegionListApiView.as_view(), name="region-list"),
    path(
        "regions/<int:pk>/tariffs/",
        views.CourierTariffListApiView.as_view(),
        name="region-tariff-list",
    ),
    path("shops/", views.ShopListApiView.as_view(), name="shop-list"),
    # path("payment-methods/", views.payment_methods_view, name="payment-methods"),
]
