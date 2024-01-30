from modeltranslation.translator import register, TranslationOptions
from fulfillment.models import (
    AdditionalService,
    Status,
    TrackingStatus,
    Tariff,
    ParentProductCategory,
    ProductCategory,
    ProductType,
    Comment,
    StatusEvent,
    CourierArea,
    CourierRegion,
    Notification,
    NotificationEvent,
    TicketCategory,
    CourierTariff,
    CustomsProductType,
)


@register(Status)
class StatusTranslationOptions(TranslationOptions):
    fields = ["display_name"]


@register(Tariff)
class TariffTranslationOptions(TranslationOptions):
    fields = ["title"]


@register(ProductCategory)
class ProductCategoryTranslationOptions(TranslationOptions):
    fields = ["name"]


@register(ParentProductCategory)
class ParentProductCategoryTranslationOptions(TranslationOptions):
    fields = ["name"]


@register(ProductType)
class ProductTypeTranslationOptions(TranslationOptions):
    fields = ["name"]


@register(Comment)
class CommentTranslationOptions(TranslationOptions):
    fields = ["body"]


@register(StatusEvent)
class StatusEventTranslationOptions(TranslationOptions):
    fields = ["message"]


@register(AdditionalService)
class AdditionalServiceTranslationOptions(TranslationOptions):
    fields = ["title", "description"]


@register(CourierArea)
class CourierAreaTranslationOptions(TranslationOptions):
    fields = ["title"]


@register(CourierRegion)
class CourierRegionTranslationOptions(TranslationOptions):
    fields = ["title"]


@register(CourierTariff)
class CourierTariffTranslationOptions(TranslationOptions):
    fields = ["title"]


@register(Notification)
class NotificationTranslationOptions(TranslationOptions):
    fields = [
        "web_title",
        "web_text",
        "email_subject",
        "email_text_simple",
        "email_text",
        "sms_text",
    ]


@register(NotificationEvent)
class NotificationEventTranslationOptions(TranslationOptions):
    fields = [
        "web_title",
        "web_text",
        "email_subject",
        "email_text_simple",
        "email_text",
        "sms_text",
    ]


@register(TrackingStatus)
class TrackingStatusTranslationOptions(TranslationOptions):
    fields = [
        "problem_code_description",
        "tracking_code_description",
        "tracking_code_explanation",
        "tracking_condition_code_description",
        "mandatory_comment",
    ]


@register(TicketCategory)
class TicketCategoryTranslationOptions(TranslationOptions):
    fields = ["title"]


@register(CustomsProductType)
class CustomsProductTypeTranslationOptions(TranslationOptions):
    fields = ["name"]
