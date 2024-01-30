from django.urls import path
from django.views.decorators.cache import cache_page

from content.views import client as views

urlpatterns = [
    path(
        "announcements/",
        views.AnnouncementListApiView.as_view(),
        name="announcement-list",
    ),
    path(
        "announcements/<slug:slug>/",
        cache_page(30 * 60)(views.AnnouncementRetrieveApiView.as_view()),
        name="announcement-retrieve",
    ),
    path(
        "faq-categories/",
        cache_page(5 * 60)(views.FAQCategoryListApiView.as_view()),
        name="faq-category-list",
    ),
    path("faqs/", cache_page(5 * 60)(views.FAQListApiView.as_view()), name="faq-list"),
    path("services/", views.ServiceListApiView.as_view(), name="service-list"),
    path(
        "services/<slug:slug>/",
        views.ServiceRetrieveApiView.as_view(),
        name="service-retrieve",
    ),
    path("slider/", views.SliderItemListApiView.as_view(), name="slider"),
    path(
        "footer/",
        views.FooterApiView.as_view(),
        name="footer-list",
    ),
    path(
        "flat-pages/<slug:slug>/",
        views.FlatPageRetrieveApiView.as_view(),
        name="flat-page-detail",
    ),
    path(
        "site-info/",
        cache_page(60 * 60)(views.SitePresetApiView.as_view()),
        name="site-info",
    ),
    path("public-offer-text/", views.public_offer_view, name="public-offer-text"),
    path(
        "terms-conditions-text/",
        views.terms_and_conditions_view,
        name="terms-conditions-text",
    ),
]
