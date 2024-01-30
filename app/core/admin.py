from django.shortcuts import redirect
from django.urls import path
from modeltranslation.admin import TranslationAdmin, TranslationStackedInline

from ontime.admin import admin
from core.models import (
    Country,
    Currency,
    CurrencyRateLog,
    City,
    MobileOperator,
    Configuration,
    OnlineShoppingDomain,
)


@admin.register(City)
class CityAdmin(TranslationAdmin):
    list_display = [
        "name",
        "code",
        "country",
        "is_default_destination",
        "is_default_source",
    ]
    autocomplete_fields = ["country"]
    search_fields = ["name__icontains", "country__name__icontains", "code__icontains"]


class CityInlineAdmin(TranslationStackedInline):
    model = City
    extra = 0


class OnlineShoppingDomainInline(admin.TabularInline):
    model = OnlineShoppingDomain
    extra = 0


@admin.register(Country)
class CountryAdmin(TranslationAdmin):
    list_display = [
        "name",
        "code",
        "number",
        "currency",
        "timezone",
        "local_time",
        "phone_code",
        "map_image",
        "is_default_destination",
        "is_default_source",
        "display_order",
        "is_smart_customs_enabled",
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "name",
                    "code",
                    "number",
                    "description",
                    "flag_image",
                    "map_image",
                    "timezone",
                    "currency",
                    "phone_code",
                ],
            },
        ),
        (
            "Business",
            {
                "fields": [
                    "is_base",
                    "is_active",
                    "is_default_source",
                    "is_default_destination",
                    "is_ordering_enabled",
                    "is_packages_enabled",
                    "ordering_disabled_message",
                    "packages_disabled_message",
                    "is_smart_customs_enabled",
                ]
            },
        ),
        (
            "Foreign address related",
            {"fields": ["display_order"]},
        ),
    ]
    ordering = ["display_order"]
    search_fields = ["name__icontains", "code__icontains"]
    inlines = [CityInlineAdmin, OnlineShoppingDomainInline]


class CurrencyRateLogInline(admin.TabularInline):
    model = CurrencyRateLog
    extra = 0
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
    max_num = 10

    def has_add_permission(self, *args, **kwargs):
        return False


@admin.register(Currency)
class CurrencyAdmin(TranslationAdmin):
    search_fields = ["name__icontains", "code__icontains"]
    list_display = ["name", "code", "number", "symbol", "rate", "rate_last_updated_at"]
    inlines = [CurrencyRateLogInline]
    change_list_template = "admin/currency/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "rates/refetch/",
                self.admin_site.admin_view(self.fetch_currency_rates_view),
                name="fetch_currency_rates",
            )
        ]
        return custom_urls + urls

    def fetch_currency_rates_view(self, reqeust):
        from core.tasks import fetch_currency_rates

        fetch_currency_rates()
        return redirect(reqeust.META["HTTP_REFERER"])

    def rate_last_updated_at(self, currency):
        log = currency.rate_logs.order_by("-created_at").first()
        return log and log.created_at or "Never"


@admin.register(MobileOperator)
class MobileOperatorAdmin(admin.ModelAdmin):
    list_display = ["name", "prefix", "country"]
    autocomplete_fields = ["country"]


@admin.register(Configuration)
class ConfigurationAdmin(TranslationAdmin):
    list_display = ["title", "is_active"]
    fieldsets = [
        (None, {"fields": ["title", "is_active"]}),
        ("Customers", {"fields": ["email_verification_url", "password_reset_url"]}),
        (
            "Ordering",
            {
                "fields": [
                    "order_commission_percentage",
                    "minimum_order_commission_price",
                    "minimum_order_commission_price_currency",
                    "order_commission_info_text",
                    "email_address_on_invoice",
                    "address_on_invoice",
                ]
            },
        ),
        (
            "Payment services",
            {
                "fields": [
                    "cybersource_redirect_url",
                    "paypal_redirect_url",
                    "paytr_redirect_url",
                ]
            },
        ),
        ("Notifications", {"fields": ["notifications_enabled"]}),
        (
            "Monthly limit / Customs related",
            {
                "fields": [
                    "manifest_reports_sent_to",
                    "manifest_company_name",
                    "monthly_spendings_treshold_currency",
                    "monthly_spendings_danger_treshold",
                    "monthly_spendings_warning_treshold",
                    "monthly_spendings_warning_message",
                    "monthly_spendings_danger_message",
                ]
            },
        ),
        (
            "Invite Friend - PROMO CODE",
            {
                "fields": [
                    "invited_friend_cashback_percentage",
                    "invited_friend_benefits_count",
                    "invite_friend_discount_appliable_models",
                ]
            },
        ),
        (
            "Common password related",
            {
                "fields": [
                    "common_password_is_enabled",
                    "common_password_expire_minutes",
                ]
            },
        ),
        (
            "Smart customs related",
            {
                "fields": [
                    "smart_customs_start_date",
                    "smart_customs_fail_silently",
                    "smart_customs_declarations_window_in_days",
                ]
            },
        ),
    ]
