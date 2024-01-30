from itertools import groupby
from functools import reduce

from django.db.models import Q
from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from rest_framework import generics, permissions, views
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

from ontime.utils import parse_int
from content.models import (
    Announcement,
    FAQ,
    FAQCategory,
    Service,
    SliderItem,
    FooterElement,
    FooterColumn,
    FlatPage,
    SitePreset,
)
from content.serializers.client import (
    AnnouncementSerializer,
    AnnouncementCompactSerializer,
    FAQSerializer,
    FAQCategorySerializer,
    ServiceSerializer,
    ServiceCompactSerializer,
    SliderItemSerializer,
    FooterColumnSerializer,
    FlatPageSerializer,
    SitePresetSerializer,
)


class AnnouncementListApiView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = AnnouncementCompactSerializer

    def get_queryset(self):
        announcements = Announcement.objects.order_by("-pinned", "-created_at")

        search = self.request.query_params.get("search")
        if search:
            announcements = announcements.filter(
                Q(title__unaccent__trigram_similar=search)
                | Q(title__unaccent__icontains=search),
            )

        pinned = self.request.query_params.get("pinned", None)
        if pinned in ["1", "true", "false", "0"]:
            pinned = pinned in ["1", "true"]
            announcements = announcements.filter(pinned=pinned)

        limit = parse_int(self.request.query_params.get("limit"))
        if limit and limit > -1:
            announcements = announcements[:limit]

        return announcements


def get_slug_query(value, field="slug", prepend_lookup=""):
    queries = []
    field_paths = []

    if prepend_lookup:
        field_paths.append(prepend_lookup)

    field_paths.append(field)

    path = "__".join(field_paths)

    for lang_code, lang_name in settings.LANGUAGES:
        queries.append(Q(**{"%s_%s" % (path, lang_code): value}))

    if queries:
        return reduce(lambda q1, q2: q1 | q2, queries)
    return Q(**{field: value})


class AnnouncementRetrieveApiView(generics.RetrieveAPIView):
    queryset = Announcement.objects.all()
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = AnnouncementSerializer

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(), get_slug_query(self.kwargs.get("slug"))
        )


class FAQListApiView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = FAQSerializer

    def get_queryset(self):
        faqs = FAQ.objects.order_by("display_order")

        category_slug = self.request.query_params.get("category")
        if category_slug:
            faqs = faqs.filter(get_slug_query(category_slug, prepend_lookup="category"))

        search = self.request.query_params.get("search")
        if search:
            faqs = faqs.filter(
                Q(question__unaccent__trigram_similar=search)
                | Q(question__unaccent__icontains=search),
            )

        limit = parse_int(self.request.query_params.get("limit"))
        if limit and limit > -1:
            faqs = faqs[:limit]

        return faqs


class FAQCategoryListApiView(generics.ListAPIView):
    pagination_class = None
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    serializer_class = FAQCategorySerializer
    queryset = FAQCategory.objects.all().order_by("display_order")


class ServiceListApiView(generics.ListAPIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    serializer_class = ServiceCompactSerializer
    queryset = Service.objects.all().order_by("-id")

    def get_queryset(self):
        services = super().get_queryset()

        search = self.request.query_params.get("search")
        if search:
            services = services.filter(
                Q(title__unaccent__trigram_similar=search)
                | Q(title__unaccent__icontains=search),
            )

        return services


class ServiceRetrieveApiView(generics.RetrieveAPIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    serializer_class = ServiceSerializer

    def get_object(self):
        return get_object_or_404(Service, get_slug_query(self.kwargs.get("slug")))


class SliderItemListApiView(generics.ListAPIView):
    pagination_class = None
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    serializer_class = SliderItemSerializer

    def get_queryset(self):
        slider_items = SliderItem.objects.filter(is_active=True).order_by("-created_at")

        limit = parse_int(self.request.query_params.get("limit"))
        if limit and limit > -1:
            return slider_items[: max(limit, 20)]

        return slider_items[:5]


class FooterApiView(generics.ListAPIView):
    authentication_classes = []
    pagination_class = None
    permission_classes = [permissions.AllowAny]
    serializer_class = FooterColumnSerializer
    queryset = FooterColumn.objects.order_by("display_order").prefetch_related(
        Prefetch("elements", queryset=FooterElement.objects.order_by("display_order"))
    )


class FlatPageRetrieveApiView(generics.RetrieveAPIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    serializer_class = FlatPageSerializer
    queryset = FlatPage.objects.all()

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(), get_slug_query(self.kwargs.get("slug"))
        )


class SitePresetApiView(generics.RetrieveAPIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    serializer_class = SitePresetSerializer

    def get_object(self):
        site_preset = SitePreset.objects.filter(is_active=True).last()
        if site_preset:
            return site_preset
        raise Http404


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def public_offer_view(request):
    offers_text = FlatPage.objects.filter(type=FlatPage.OFFER_TYPE).first()

    if not offers_text:
        raise Http404

    return Response(FlatPageSerializer(offers_text).data)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def terms_and_conditions_view(request):
    conditions_text = FlatPage.objects.filter(type=FlatPage.CONDITIONS_TYPE).first()

    if not conditions_text:
        raise Http404

    return Response(FlatPageSerializer(conditions_text).data)
