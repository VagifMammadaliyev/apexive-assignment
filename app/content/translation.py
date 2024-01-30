from modeltranslation.translator import register, TranslationOptions
from content.models import (
    Announcement,
    FAQ,
    FAQCategory,
    Service,
    SliderItem,
    FlatPage,
    FooterElement,
    SitePreset,
    FooterColumn,
)


@register(Announcement)
class AnnouncementTranslationOptions(TranslationOptions):
    fields = ["title", "body", "slug", "preview"]


@register(FAQ)
class FAQTranslationOptions(TranslationOptions):
    fields = ["question", "answer"]


@register(FAQCategory)
class FAQCategoryTranslationOptions(TranslationOptions):
    fields = ["name", "slug"]


@register(Service)
class ServiceTranslationOptions(TranslationOptions):
    fields = ["title", "slug", "description", "preview"]


@register(SliderItem)
class SliderItemTranslationOptions(TranslationOptions):
    fields = ["title", "description"]


@register(FlatPage)
class FlatPageTranslationOptions(TranslationOptions):
    fields = ["title", "slug", "body", "preview"]


@register(FooterElement)
class FooterElementTranslationOptions(TranslationOptions):
    fields = ["title"]


@register(SitePreset)
class SitePresetTranslationOptions(TranslationOptions):
    fields = [
        "about_text",
        "about_text_title",
        "about_text_preview",
        "main_office_address",
    ]


@register(FooterColumn)
class FooterColumnTranslationOptions(TranslationOptions):
    fields = ["title"]
