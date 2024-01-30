from modeltranslation.translator import register, TranslationOptions
from core.models import Country, Currency, City, Configuration


@register(Country)
class CountryTranslationOptions(TranslationOptions):
    fields = [
        "name",
        "description",
        "ordering_disabled_message",
        "packages_disabled_message",
    ]


@register(Currency)
class CurrencyTranslationOptions(TranslationOptions):
    fields = ["name"]


@register(City)
class CityTranslationOptions(TranslationOptions):
    fields = ["name"]


@register(Configuration)
class CityTranslationOptions(TranslationOptions):
    fields = [
        "order_commission_info_text",
        "monthly_spendings_warning_message",
        "monthly_spendings_danger_message",
    ]
