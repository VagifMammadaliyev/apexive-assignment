from django_filters.rest_framework import FilterSet

from content.models import Announcement, FAQ, Service, SliderItem


class AnnouncementFilter(FilterSet):
    class Meta:
        model = Announcement
        fields = {
            "title": ["exact", "icontains", "contains"],
            "body": ["exact", "icontains", "contains"],
            "pinned": ["exact"],
            "slug": ["exact", "icontains", "contains"],
        }


class FAQFilter(FilterSet):
    class Meta:
        model = FAQ
        fields = {
            "category": ["exact"],
            "question": ["exact", "icontains", "contains"],
            "answer": ["exact", "icontains", "contains"],
        }


class ServiceFilter(FilterSet):
    class Meta:
        model = Service
        fields = {
            "title": ["exact", "icontains", "contains"],
            "slug": ["exact", "icontains", "contains"],
            "description": ["exact", "icontains", "contains"],
        }


class SliderItemFilter(FilterSet):
    class Meta:
        model = SliderItem
        fields = {
            "title": ["exact", "icontains", "contains"],
            "description": ["exact", "icontains", "contains"],
            "is_active": ["exact"],
        }
