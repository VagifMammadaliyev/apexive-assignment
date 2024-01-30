from django.urls import path, include
from rest_framework import routers

from fulfillment.views.admin import cargo as views

router = routers.SimpleRouter()
router.register("tariffs", views.TariffViewSet)
router.register("warehouses", views.WarehouseViewSet)
router.register("addresses", views.AddressViewSet)
router.register("product-types", views.ProductTypeViewSet)
router.register("product-categories", views.ProductCategoryViewSet)

nested_router = routers.SimpleRouter()
nested_router.register("fields", views.AddressFieldViewSet, basename="address-field")

urlpatterns = router.urls
urlpatterns += [path("addresses/<int:address_pk>/", include(nested_router.urls))]
