from rest_framework import serializers

from ontime.utils import fix_rich_text_image_url
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


class AnnouncementCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["slug", "title", "image", "preview", "created_at", "pinned"]


class AnnouncementSerializer(serializers.ModelSerializer):
    body = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ["slug", "title", "image", "preview", "body", "created_at", "pinned"]

    def get_body(self, announcement: Announcement):
        return fix_rich_text_image_url(self.context["request"], announcement.body)


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["id", "question", "answer"]


class FAQCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQCategory
        fields = ["name", "slug"]


class ServiceSerializer(serializers.ModelSerializer):
    description = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = ["id", "slug", "preview", "title", "image", "description"]

    def get_description(self, service: Service):
        return fix_rich_text_image_url(self.context["request"], service.description)


class ServiceCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "slug", "preview", "title", "image", "preview"]


class SliderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SliderItem
        fields = ["id", "title", "description", "link", "background_image"]


class FooterElementSerializer(serializers.ModelSerializer):
    flat_page_slug = serializers.SlugField(source="flat_page.slug", read_only=True)
    active_field_name = serializers.SerializerMethodField()

    class Meta:
        model = FooterElement
        fields = [
            "title",
            "active_field_name",
            "raw_link",
            "flat_page_slug",
        ]

    def get_active_field_name(self, footer_element):
        if footer_element.raw_link:
            return "raw_link"
        elif footer_element.flat_page_id:
            return "flat_page_slug"
        return None


class FooterColumnSerializer(serializers.ModelSerializer):
    elements = FooterElementSerializer(many=True, read_only=True)

    class Meta:
        model = FooterColumn
        fields = [
            "title",
            "elements",
        ]


class FlatPageSerializer(serializers.ModelSerializer):
    body = serializers.SerializerMethodField()

    class Meta:
        model = FlatPage
        fields = ["title", "slug", "body", "preview"]

    def get_body(self, flat_page: FlatPage):
        return fix_rich_text_image_url(self.context["request"], flat_page.body)


class SitePresetSerializer(serializers.ModelSerializer):
    emails = serializers.SerializerMethodField()
    phone_numbers = serializers.SerializerMethodField()

    class Meta:
        model = SitePreset
        fields = [
            "about_text_title",
            "about_text",
            "about_text_preview",
            "main_office_address",
            "emails",
            "phone_numbers",
        ]

    def get_phone_numbers(self, site_preset: SitePreset):
        if site_preset.phone_numbers:
            return list(map(lambda s: s.strip(), site_preset.phone_numbers.split(",")))
        return None

    def get_emails(self, site_preset: SitePreset):
        if site_preset.emails:
            return list(map(lambda s: s.strip(), site_preset.emails.split(",")))
        return None
