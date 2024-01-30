from rest_framework import routers

from content.views import admin as views

router = routers.SimpleRouter()
router.register("announcements", views.AnnouncementViewSet)
router.register("services", views.ServiceViewSet)
router.register("faq-categories", views.FAQCategoryViewSet)
router.register("faqs", views.FAQViewSet)
router.register("slider-items", views.SliderItemViewSet)

urlpatterns = []

urlpatterns += router.urls
