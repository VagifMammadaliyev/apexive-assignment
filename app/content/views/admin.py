from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend

from domain.logging.utils import generic_logging
from content.models import Announcement, Service, FAQ, FAQCategory, SliderItem
from content.serializers import admin as content_serializers
from content import filters
from customer.permissions import IsContentManager, IsOntimeAdminUser


@generic_logging
class AnnouncementViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.AnnouncementFilter
    permission_classes = [IsContentManager | IsOntimeAdminUser]
    queryset = Announcement.objects.order_by("-pinned", "-created_at")
    serializer_class = content_serializers.AnnouncementTranslatedSerializer

    def get_serializer_class(self, *args, **kwargs):
        if self.action == "list":
            return content_serializers.AnnouncementSerializer
        return super().get_serializer_class(*args, **kwargs)


@generic_logging
class ServiceViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.ServiceFilter
    permission_classes = [IsContentManager | IsOntimeAdminUser]
    queryset = Service.objects.all()
    serializer_class = content_serializers.ServiceTranslatedSerializer

    def get_serializer_class(self, *args, **kwargs):
        if self.action == "list":
            return content_serializers.ServiceSerializer
        return super().get_serializer_class(*args, **kwargs)


@generic_logging
class FAQCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsContentManager | IsOntimeAdminUser]
    queryset = FAQCategory.objects.all()
    serializer_class = content_serializers.FAQCategoryTranslatedSerializer

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self, *args, **kwargs):
        if self.action == "list":
            return content_serializers.FAQCategorySerializer
        return super().get_serializer_class(*args, **kwargs)


@generic_logging
class FAQViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.FAQFilter
    permission_classes = [IsContentManager | IsOntimeAdminUser]
    queryset = FAQ.objects.order_by("category")

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if self.action == "list":
                return content_serializers.FAQReadSerializer
            return content_serializers.FAQTranslatedReadSerializer
        return content_serializers.FAQWriteSerializer


@generic_logging
class SliderItemViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_class = filters.SliderItemFilter
    permission_classes = [IsContentManager | IsOntimeAdminUser]
    queryset = SliderItem.objects.order_by("-created_at")

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            if self.action == "list":
                return content_serializers.SliderItemReadSerializer
            return content_serializers.SliderItemTranslatedReadSerializer
        return content_serializers.SliderItemWriteSerializer
