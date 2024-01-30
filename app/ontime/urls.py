from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("grappelli/", include("grappelli.urls")),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    path("cp/", admin.site.urls),
    path("cp/defender/", include("defender.urls")),
    path("payment-services/", include("fulfillment.urls.payment_service")),
    path("api/v1/auth/", include("customer.urls.client")),
    path("api/v1/core/", include("core.urls.client")),
    path("api/v1/core/", include("fulfillment.urls.core")),
    path("api/v1/cargo/", include("fulfillment.urls.common")),
    path("api/v1/customer/", include("fulfillment.urls.customer")),
    path("api/v1/content/", include("content.urls.client")),
    path("api/v1/admin/common/", include("fulfillment.urls.admin_common")),
    path("api/v1/admin/auth/", include("customer.urls.admin")),
    path("api/v1/admin/core/", include("core.urls.admin")),
    path("api/v1/admin/content/", include("content.urls.admin")),
    path("api/v1/admin/cargo/", include("fulfillment.urls.cargo_admin")),
    path("api/v1/admin/staff/", include("fulfillment.urls.staff_admin")),
]

if settings.DEVELOPMENT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if "rosetta" in settings.INSTALLED_APPS:
    urlpatterns += [path("translate/", include("rosetta.urls"))]
