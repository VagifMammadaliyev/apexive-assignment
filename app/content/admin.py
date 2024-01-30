from django.utils.html import format_html
from django.db.models import Count, Prefetch
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from ontime.admin import admin
from content.models import (
    Announcement,
    FAQ,
    FAQCategory,
    Service,
    SliderItem,
    FlatPage,
    FooterElement,
    FooterColumn,
    SitePreset,
)


@admin.register(Announcement)
class AnnouncementAdmin(TranslationAdmin):
    list_display = ["title", "slug", "created_at", "image", "pinned"]
    ordering = ["-pinned", "-created_at"]
    exclude = ["slug"]


@admin.register(FAQ)
class FAQAdmin(TranslationAdmin):
    list_display = [
        "question",
        "answer",
        "category",
        "display_order",
    ]
    list_select_related = True
    autocomplete_fields = ["category"]
    ordering = ["display_order"]


class FAQInline(TranslationTabularInline):
    model = FAQ
    extra = 0


@admin.register(FAQCategory)
class FAQCategory(TranslationAdmin):
    list_display = [
        "name",
        "faqs_count",
        "display_order",
    ]
    exclude = ["slug"]
    inlines = [FAQInline]
    search_fields = ["name__icontains"]
    ordering = ["display_order"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(faqs_count=Count("faq"))

    def faqs_count(self, category):
        return category.faqs_count


@admin.register(Service)
class ServiceAdmin(TranslationAdmin):
    list_display = ["title", "slug", "preview", "image"]
    exclude = ["slug"]


@admin.register(SliderItem)
class SliderItemAdmin(TranslationAdmin):
    list_display = ["title", "link", "is_active", "background_image"]


@admin.register(FlatPage)
class FlatPageAdmin(TranslationAdmin):
    search_fields = ["title__icontains", "slug__icontains", "body__icontains"]
    list_filter = ["type"]
    readonly_fields = ["slug"]
    list_display = ["title", "slug", "type"]


class FooterElemenInline(TranslationTabularInline):
    model = FooterElement
    extra = 0
    max_num = 10
    ordering = ["display_order"]


@admin.register(FooterColumn)
class FooterColumnAdmin(TranslationAdmin):
    search_fields = ["title__icontains"]
    list_display = ["title", "elements", "display_order"]
    ordering = ["display_order"]
    inlines = [FooterElemenInline]

    def elements(self, column):
        items = column.prefetched_elements
        return format_html("<br>".join(item.title for item in items))

    def get_queryset(self, request, *args, **kwargs):
        return (
            super()
            .get_queryset(request, *args, **kwargs)
            .prefetch_related(
                Prefetch(
                    "elements",
                    to_attr="prefetched_elements",
                    queryset=FooterElement.objects.all().order_by("display_order"),
                )
            )
        )


@admin.register(SitePreset)
class SitePresetAdmin(TranslationAdmin):
    search_fields = ["title"]
    list_display = ["title", "emails", "phone_numbers", "is_active"]
