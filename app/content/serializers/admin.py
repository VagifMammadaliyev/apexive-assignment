from rest_framework import serializers

from ontime.utils import get_expanded_extra_kwargs, get_expanded_fields
from content.models import Announcement, Service, FAQ, FAQCategory, SliderItem
from content.translation import (
    AnnouncementTranslationOptions,
    ServiceTranslationOptions,
    FAQCategoryTranslationOptions,
    FAQTranslationOptions,
    SliderItemTranslationOptions,
)


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = [
            "id",
            "slug",
            "title",
            "image",
            "body",
            "preview",
            "pinned",
            "created_at",
        ]
        extra_kwargs = {
            "slug": {"read_only": True},
            "body": {"required": True},
            "title": {"required": True},
            "preview": {"required": True},
        }


class AnnouncementTranslatedSerializer(AnnouncementSerializer):
    class Meta(AnnouncementSerializer.Meta):
        fields = get_expanded_fields(
            AnnouncementSerializer.Meta.fields, AnnouncementTranslationOptions.fields
        )
        extra_kwargs = get_expanded_extra_kwargs(
            AnnouncementSerializer.Meta.extra_kwargs,
            AnnouncementTranslationOptions.fields,
        )


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "preview",
            "image",
        ]

        extra_kwargs = {
            "title": {"required": True},
            "slug": {"read_only": True},
            "description": {"required": True},
            "preview": {"required": True},
        }


class ServiceTranslatedSerializer(ServiceSerializer):
    class Meta(ServiceSerializer.Meta):
        fields = get_expanded_fields(
            ServiceSerializer.Meta.fields,
            ServiceTranslationOptions.fields,
        )
        extra_kwargs = get_expanded_extra_kwargs(
            ServiceSerializer.Meta.extra_kwargs,
            ServiceTranslationOptions.fields,
        )


class FAQCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQCategory
        fields = ["id", "name", "slug"]
        extra_kwargs = {"name": {"required": True}, "slug": {"read_only": True}}


class FAQCategoryTranslatedSerializer(FAQCategorySerializer):
    class Meta(FAQCategorySerializer.Meta):
        fields = get_expanded_fields(
            FAQCategorySerializer.Meta.fields, FAQCategoryTranslationOptions.fields
        )
        extra_kwargs = get_expanded_extra_kwargs(
            FAQCategorySerializer.Meta.extra_kwargs,
            FAQCategoryTranslationOptions.fields,
        )


class FAQCategoryCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQCategory
        fields = ["id", "name"]


class FAQReadSerializer(serializers.ModelSerializer):
    category = FAQCategoryCompactSerializer(read_only=True)

    class Meta:
        model = FAQ
        fields = ["id", "category", "question", "answer"]


class FAQTranslatedReadSerializer(FAQReadSerializer):
    class Meta(FAQReadSerializer.Meta):
        fields = get_expanded_fields(
            FAQReadSerializer.Meta.fields, FAQTranslationOptions.fields
        )


class FAQWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = get_expanded_fields(
            ["id", "category", "question", "answer"], FAQTranslationOptions.fields
        )
        extra_kwargs = get_expanded_extra_kwargs(
            {
                "question": {"required": True},
                "answer": {"required": True},
            },
            FAQTranslationOptions.fields,
        )

    def to_representation(self, instance):
        return FAQReadSerializer(instance).data


class SliderItemReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SliderItem
        fields = ["id", "title", "description", "background_image", "link", "is_active"]


class SliderItemTranslatedReadSerializer(SliderItemReadSerializer):
    class Meta(SliderItemReadSerializer.Meta):
        fields = get_expanded_fields(
            SliderItemReadSerializer.Meta.fields, SliderItemTranslationOptions.fields
        )


class SliderItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SliderItem
        fields = get_expanded_fields(
            ["title", "description", "background_image", "link", "is_active"],
            SliderItemTranslationOptions.fields,
        )
        extra_kwargs = get_expanded_extra_kwargs(
            {
                "title": {"required": True},
                "background_image": {"required": True},
            },
            SliderItemTranslationOptions.fields,
        )

    def to_representation(self, instance):
        return SliderItemTranslatedReadSerializer(instance).data
