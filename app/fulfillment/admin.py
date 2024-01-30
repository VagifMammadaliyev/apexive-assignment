from django.shortcuts import redirect, reverse, render
from django.conf import settings
from django.urls import path, reverse
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import mark_safe
from django.db.models import Count
from django.contrib import messages
from django.contrib.contenttypes.admin import GenericStackedInline, GenericTabularInline
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from ontime.admin import admin
from domain.utils import XMLManifestGenerator
from domain.utils.documents import ManifestGenerator
from domain.utils.smart_customs import CustomsClient, filter_addable_shipments
from domain.exceptions.smart_customs import SmartCustomsError
from domain.logging.utils import log_action, CHANGE
from fulfillment import admin_filters as af
from fulfillment.forms import AdminShipmentForm
from fulfillment.utils import get_status_actions
from fulfillment.admin_utils import SoftDeletionAdmin, TranslatedSoftDeletionAdmin
from fulfillment import tasks as fulfillment_tasks
from fulfillment.models import (
    Address,
    AddressField,
    AdditionalService,
    Box,
    Comment,
    Order,
    Package,
    PackagePhoto,
    Product,
    ProductCategory,
    ProductType,
    ParentProductCategory,
    Status,
    TrackingStatus,
    StatusEvent,
    Shipment,
    Tariff,
    Transportation,
    Transaction,
    Warehouse,
    Assignment,
    ShoppingAssistantProfile,
    WarehousemanProfile,
    CashierProfile,
    CustomerServiceProfile,
    CourierProfile,
    PackageAdditionalService,
    ShipmentAdditionalService,
    PackageAdditionalServiceAttachment,
    ShipmentAdditionalServiceAttachment,
    WarehouseAdditionalService,
    Queue,
    QueuedItem,
    Monitor,
    Notification,
    ShipmentReceiver,
    Subscriber,
    ContactUsMessage,
    Ticket,
    TicketAttachment,
    TicketCategory,
    TicketComment,
    NotificationEvent,
    CourierArea,
    CourierRegion,
    CourierOrder,
    CourierTariff,
    CustomerServiceLog,
    Shop,
    OrderedProduct,
    Discount,
    PromoCode,
    PromoCodeBenefit,
    CustomsProductType,
)


class DiscountInline(GenericTabularInline):
    model = Discount
    extra = 0
    ct_fk_field = "object_id"
    ct_field = "object_type"
    classes = ["grp-collapse grp-closed"]
    readonly_fields = ["created_at", "updated_at"]


class TransactionInline(GenericStackedInline):
    model = Transaction
    extra = 0
    show_change_link = True
    ct_fk_field = "object_id"
    ct_field = "object_type"
    classes = ["grp-collapse grp-closed"]
    readonly_fields = ["completed_manually", "invoice_number"]
    autocomplete_fields = [
        "original_currency",
        "user",
        "from_balance_currency",
        "currency",
        "cashback_to",
        "parent",
    ]

    def has_delete_permission(self, *args, **kwargs):
        return False

    def get_max_num(self, request, obj=None, **kwargs):
        if isinstance(obj, Order):
            return 2

        return 1


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    search_fields = [
        "title__icontains",
        "codename__icontains",
        "country__name__icontains",
        "city__name__icontains",
        "country__code__icontains",
        "city__code__icontains",
    ]
    list_display = [
        "title",
        "codename",
        "country",
        "city",
        "is_universal",
        "is_consolidation_enabled",
        "does_consider_volume",
        "does_serve_dangerous_packages",
    ]
    list_filter = ["does_serve_dangerous_packages", "does_consider_volume"]
    autocomplete_fields = ["country", "city", "airport_city"]


class ChildTransactionInline(admin.StackedInline):
    readonly_fields = ["completed_manually"]
    model = Transaction
    extra = 0
    show_change_link = True
    fk_name = "parent"
    readonly_fields = [
        "discounted_amount",
        "discounted_amount_currency",
        "completed_manually",
        "invoice_number",
    ]
    autocomplete_fields = [
        "original_currency",
        "user",
        "from_balance_currency",
        "currency",
        "cashback_to",
        "parent",
    ]

    def has_delete_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, *args, **kwargs):
        return False


@admin.register(Transaction)
class TransactionAdmin(SoftDeletionAdmin):
    inlines = [ChildTransactionInline]
    list_display = [
        "invoice_number",
        "user",
        "parent",
        "amount",
        "currency",
        "purpose",
        "type",
        "object_type",
        "related_object_identifier",
        "completed",
        "completed_at",
        "created_at",
        "updated_at",
        "is_partial",
        "is_deleted",
        "deleted_at",
    ]
    readonly_fields = [
        "discounted_amount",
        "discounted_amount_currency",
        "completed_manually",
        "invoice_number",
    ]
    search_fields = [
        "parent__invoice_number",
        "invoice_number__icontains",
        "user__client_code__icontains",
        "user__full_phone_number__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "related_object_identifier__icontains",
    ]
    autocomplete_fields = ["currency", "parent", "user", "cashback_to"]
    list_filter = ["purpose", "type", "completed", "is_partial", "is_deleted"]
    ordering = ["-updated_at"]


@admin.register(Status)
class StatusAdmin(TranslationAdmin):
    list_display = [
        "codename",
        "display_name",
        "next",
        "prev",
        "order",
        "type",
    ]
    ordering = [
        "type",
        "order",
    ]
    list_filter = ["type"]
    search_fields = [
        "codename__icontains",
        "display_name__icontains",
    ]


class CommentInlineAdmin(TranslationTabularInline):
    model = Comment
    extra = 0
    autocomplete_fields = ["author"]
    classes = ["grp-collapse grp-closed"]


@admin.register(Order)
class OrderAdmin(SoftDeletionAdmin):
    inlines = [CommentInlineAdmin, DiscountInline, TransactionInline]
    search_fields = [
        "product_seller",
        "order_code__icontains",
        "external_order_code__icontains",
        "user__client_code__icontains",
        "user__full_phone_number__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "shop__name",
    ]
    list_display = [
        "order_code",
        "external_order_code",
        "status",
        "user",
        "source_country",
        "product_category",
        "product_type",
        "total_price",
        "total_price_currency",
        "remainder_price",
        "remainder_price_currency",
        "paid_amount",
        "is_paid",
        "is_oneclick",
        "created_at",
        "status_last_update_time",
        "deleted_at",
    ]
    autocomplete_fields = [
        "package",
        "user",
        "status",
        "source_country",
        "product_category",
        "product_type",
        "recipient",
        "commission_price_currency",
        "cargo_price_currency",
        "product_price_currency",
        "total_price_currency",
        "real_cargo_price_currency",
        "real_product_price_currency",
        "real_total_price_currency",
        "remainder_price_currency",
        "shop",
    ]
    list_select_related = True
    list_filter = [
        "status",
        "is_paid",
        "is_oneclick",
        "shop",
        "show_on_slider",
        af.RelatedPackageACFilter,
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "user",
                    "status",
                    "status_last_update_time",
                    "source_country",
                    "order_code",
                    "external_order_code",
                    "show_on_slider",
                    "package",
                ]
            },
        ),
        (
            "Product info",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "product_seller",
                    "product_seller_address",
                    "product_url",
                    "product_color",
                    "product_size",
                    "product_description",
                    "product_category",
                    "product_type",
                    "product_image",
                    "product_image_url",
                    "shop",
                ],
            },
        ),
        (
            "Pricing",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "commission_price",
                    "commission_price_currency",
                    "product_price",
                    "product_price_currency",
                    "cargo_price",
                    "cargo_price_currency",
                    "product_quantity",
                    "total_price",
                    "total_price_currency",
                    "is_paid",
                ],
            },
        ),
        (
            "Real pricing & Remainder",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "real_commission_price",
                    "real_commission_price_currency",
                    "real_product_price",
                    "real_product_price_currency",
                    "real_cargo_price",
                    "real_cargo_price_currency",
                    "real_product_quantity",
                    "real_total_price",
                    "real_total_price_currency",
                    "remainder_price",
                    "remainder_price_currency",
                    "paid_amount",
                ],
            },
        ),
        (
            "Other info",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "is_oneclick",
                    "recipient",
                    "description",
                    "extra",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                ],
            },
        ),
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "status_last_update_time",
    ]

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.update(get_status_actions(Status.ORDER_TYPE))
        return actions


@admin.register(Tariff)
class TariffAdmin(TranslatedSoftDeletionAdmin):
    list_display = [
        "title",
        "source_city",
        "destination_city",
        "price",
        "discounted_price",
        "min_weight",
        "max_weight",
        "price_currency",
        "is_per_kg",
        "is_dangerous",
        "is_fixed_price",
        "deleted_at",
    ]
    list_editable = [
        "min_weight",
        "max_weight",
        "is_per_kg",
        "is_dangerous",
        "is_fixed_price",
        "discounted_price",
        "price",
        "price_currency",
        "deleted_at",
    ]
    autocomplete_fields = ["source_city", "destination_city", "price_currency"]
    ordering = ["source_city", "is_dangerous", "min_weight"]
    list_filter = [
        "source_city",
        "destination_city",
        "is_fixed_price",
        "is_per_kg",
        "is_dangerous",
    ]


@admin.register(ProductType)
class ProductTypeAdmin(TranslationAdmin):
    list_display = ["name", "category", "is_active"]
    search_fields = ["name__icontains", "category__name__icontains"]
    autocomplete_fields = ["category"]


class ProductTypeInline(TranslationTabularInline):
    model = ProductType
    extra = 1


@admin.register(ProductCategory)
class ProductCategoryAdmin(TranslationAdmin):
    list_display = ["name", "parent", "is_active", "needs_description"]
    autocomplete_fields = ["parent"]
    inlines = [ProductTypeInline]
    search_fields = [
        "name__icontains",
    ]
    list_filter = [af.ParentCategoryFilter]


@admin.register(ParentProductCategory)
class ParentProductCategoryAdmin(TranslationAdmin):
    list_display = ["name"]
    search_fields = ["name"]


class ProductInlineAdmin(admin.TabularInline):
    model = Product
    autocomplete_fields = [
        "category",
        "type",
        "price_currency",
        "cargo_price_currency",
        "commission_price_currency",
        "order",
    ]
    extra = 0
    classes = ["grp-collapse grp-closed"]
    readonly_fields = ["photo_links"]

    def photo_links(self, product: Product):
        html = "<br>".join(
            f'<a href="{photo.file.url}">Photo #{i}</a>'
            for i, photo in enumerate(product.photos.all(), start=1)
        )
        return mark_safe(html)


class AdditionalServicePackageInlineAdmin(admin.TabularInline):
    model = AdditionalService.packages.through
    autocomplete_fields = [
        "service",
    ]
    extra = 0
    classes = ["grp-collapse grp-closed"]


class PackagePhotoInline(admin.TabularInline):
    model = PackagePhoto
    classes = ["grp-collapse grp-closed"]
    extra = 0


@admin.register(Package)
class PackageAdmin(SoftDeletionAdmin):
    inlines = [
        ProductInlineAdmin,
        PackagePhotoInline,
    ]
    autocomplete_fields = [
        "user",
        "shipment",
        "order",
        "status",
        "current_warehouse",
        "source_country",
    ]
    search_fields = [
        "admin_tracking_code__icontains",
        "seller",
        "user_tracking_code__icontains",
        "user__client_code__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "user__email__icontains",
        "user__full_phone_number__icontains",
        "shelf__iexact",
        "order__order_code",
        "order__external_order_code",
    ]
    list_select_related = True
    list_filter = ["status", "is_accepted", "is_serviced", "is_problematic"]
    list_display = [
        "user_tracking_code",
        "admin_tracking_code",
        "user",
        "status",
        "source_country",
        "shipment",
        "order",
        "current_warehouse",
        "shelf",
        "is_problematic",
        "is_serviced",
        "is_accepted",
        "is_by_assistant",
        "is_volume_considered",
        "size_and_dimensions",
        "deleted_at",
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "user",
                    "shipment",
                    "order",
                    "status",
                    "status_last_update_time",
                    "seller",
                    "seller_address",
                ],
            },
        ),
        (
            "Tracking & Stocking",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "user_tracking_code",
                    "admin_tracking_code",
                    "source_country",
                    "current_warehouse",
                    "is_accepted",
                    "arrival_date",
                    "real_arrival_date",
                    "shelf",
                    "delay_days",
                ],
            },
        ),
        (
            "Servicing",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "is_by_assistant",
                    "is_serviced",
                ],
            },
        ),
        (
            "Size & Dimensions",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "weight",
                    "is_volume_considered",
                    "height",
                    "width",
                    "length",
                ],
            },
        ),
        (
            "Other info",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "attachment",
                    "user_note",
                    "warehouseman_description",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                    "extra",
                ],
            },
        ),
    ]
    readonly_fields = [
        "status_last_update_time",
        "created_at",
        "updated_at",
        "delay_days",
    ]

    @mark_safe
    def size_and_dimensions(self, package):
        return "<br>".join(
            [
                "Weight: %s" % package.weight,
                "H/W/L: %s/%s/%s" % (package.height, package.width, package.length),
            ]
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.update(get_status_actions(Status.PACKAGE_TYPE))
        return actions


class AddressFieldInline(admin.TabularInline):
    model = AddressField
    extra = 0


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    autocomplete_fields = ["warehouse", "country"]
    inlines = [AddressFieldInline]
    list_display = [
        "warehouse",
        "country",
    ]


class PackageInlineAdmin(admin.StackedInline):
    show_change_link = True
    model = Package
    extra = 0
    classes = ["grp-collapse grp-closed"]

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, *args, **kwargs):
        return False


class StatusEventInline(TranslationTabularInline):
    model = StatusEvent
    extra = 0
    classes = ["grp-collapse grp-closed"]
    exclude = ["order", "package"]
    autocomplete_fields = [
        "from_status",
        "to_status",
    ]


class AdditionalServiceShipmentInlineAdmin(admin.TabularInline):
    model = AdditionalService.shipments.through
    extra = 0
    autocomplete_fields = ["service"]
    classes = ["grp-collapse grp-closed"]


class PromoCodeBenefitInline(GenericTabularInline):
    model = PromoCodeBenefit
    extra = 0
    ct_fk_field = "object_id"
    ct_field = "object_type"
    classes = ["grp-collapse grp-closed"]
    readonly_fields = ["created_at"]

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, *args, **kwargs):
        return False


@admin.register(Shipment)
class ShipmentAdmin(SoftDeletionAdmin):
    form = AdminShipmentForm
    list_select_related = True
    autocomplete_fields = [
        "user",
        "status",
        "current_warehouse",
        "source_warehouse",
        "destination_warehouse",
        "recipient",
        "declared_price_currency",
        "total_price_currency",
        "box",
        "queued_item",
        "tracking_status",
        "courier_order",
    ]
    search_fields = [
        "number__icontains",
        "user__client_code__icontains",
        "user__full_phone_number__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "courier_order__number__icontains",
        "reg_number",
    ]
    list_filter = [
        "is_paid",
        "is_declared_to_customs",
        "declared_to_customs_at",
        "is_depeshed",
        "is_added_to_box",
        "is_deleted_from_smart_customs",
        "is_deleted_from_smart_customs_by_us",
        "is_declared_by_user",
        "customs_payment_status_id",
        "is_oneclick",
        "confirmed_properties",
        "status",
        "created_at",
        "updated_at",
        "contains_batteries",
        af.CustomerACFilter,
        af.SourceWHACFilter,
        af.DestinationWHACFilter,
        af.CurrentWHACFilter,
        af.RelatedPackageACFilter,
        af.BoxACFilter,
        af.SmartCustomsCommitableFilter,
        af.ShipmentTransportFilter,
    ]
    list_display = [
        "number",
        "user",
        "status",
        "current_warehouse",
        "get_recipient",
        "destination_warehouse",
        "fixed_total_weight",
        "shelf",
        "declared_price",
        "declared_price_currency",
        "total_price",
        "total_price_currency",
        "is_paid",
        # "confirmed_properties",
        "created_at",
        # "updated_at",
        "deleted_at",
        "is_declared_by_user",
        "is_deleted_from_smart_customs",
        "is_deleted_from_smart_customs_by_us",
        "reg_number",
    ]
    ordering = [
        "-created_at",
    ]
    inlines = [
        PackageInlineAdmin,
        StatusEventInline,
        AdditionalServiceShipmentInlineAdmin,
        DiscountInline,
        TransactionInline,
        PromoCodeBenefitInline,
    ]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "user",
                    "status",
                    "tracking_status",
                    "status_last_update_time",
                    "number",
                ]
            },
        ),
        (
            "Transporting & Stocking",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "current_warehouse",
                    "source_warehouse",
                    "destination_warehouse",
                    "recipient",
                    "shelf",
                    "box",
                ],
            },
        ),
        (
            "Size & Dimensions & Other properties",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "fixed_total_weight",
                    "recalculate_total_price",
                    "is_volume_considered",
                    "fixed_height",
                    "fixed_width",
                    "fixed_length",
                    "confirmed_properties",
                    "contains_batteries",
                    "is_dangerous",
                ],
            },
        ),
        (
            "Pricing & Servicing",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "declared_items_title",
                    "declared_price",
                    "declared_price_currency",
                    "declared_at",
                    "total_price",
                    "total_price_currency",
                    "is_oneclick",
                    "is_paid",
                    "is_serviced",
                    "courier_order",
                ],
            },
        ),
        (
            "Other info",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "user_note",
                    "staff_note",
                    "queued_item",
                    "created_at",
                    "updated_at",
                    "extra",
                    "deleted_at",
                ],
            },
        ),
        (
            "Smart customs related",
            {
                "classes": ["grp-collapse grp-closed"],
                "fields": [
                    "is_declared_to_customs",
                    "declared_to_customs_at",
                    "is_depeshed",
                    "is_added_to_box",
                    "is_deleted_from_smart_customs_by_us",
                    "is_deleted_from_smart_customs",
                    "reg_number",
                    "is_declared_by_user",
                    "customs_payment_status_id",
                    "customs_payment_status_description",
                    "customs_goods_list_data",
                ],
            },
        ),
    ]
    readonly_fields = ["status_last_update_time", "created_at", "updated_at"]
    actions = [
        "mark_as_paid",
        "pre_declare_to_customs",
        "delete_from_customs",
        "add_to_boxes",
    ]

    def add_to_boxes(self, request, queryset):
        addable = filter_addable_shipments(queryset)
        if addable.count():
            self.message_user(
                request,
                f"{addable.count()} shipments will be added to box for customs",
                level=messages.SUCCESS,
            )
            fulfillment_tasks.add_to_customs_box.delay(
                list(addable.values_list("id", flat=True))
            )
        else:
            self.message_user(
                request,
                f"No shipment can be added to box for customs",
                level=messages.ERROR,
            )

    def pre_declare_to_customs(self, request, queryset):
        already_declared = queryset.filter(is_declared_to_customs=True)
        if already_declared.exists():
            bad_shipments_count = already_declared.count()
            if bad_shipments_count > 30:
                warning = "Some shipments already declared to customs, so they were not sent again"
            else:
                shipments = already_declared.values_list("number", flat=True)
                shipments = ", ".join(shipments)
                warning = f"{shipments} already declared to customs, so they were not sent again"
            self.message_user(request, warning, level=messages.WARNING)
        good_shipments = queryset.filter(
            is_declared_to_customs=False, status__codename="tobeshipped"
        )
        if good_shipments.exists():
            try:
                fulfillment_tasks.commit_to_customs(
                    list(good_shipments.values_list("id", flat=True))
                )
                self.message_user(
                    request, "Declared to customs successfully!", level=messages.SUCCESS
                )
            except SmartCustomsError as err:
                self.message_user(request, str(err), level=messages.ERROR)
        else:
            self.message_user(
                request, "No shipments was declared to customs", level=messages.ERROR
            )

    def delete_from_customs(self, request, queryset):
        non_declared = queryset.filter(is_declared_to_customs=False)
        if non_declared.exists():
            bad_shipments_count = non_declared.count()
            if bad_shipments_count > 30:
                warning = "Some shipments have not been declared to customs yet, skipping them..."
            else:
                shipments = non_declared.values_list("number", flat=True)
                shipments = ", ".join(shipments)
                warning = f"{shipments} have not been declared to customs yet, skipping them..."
            self.message_user(request, warning, level=messages.WARNING)
        declared = queryset.filter(is_declared_to_customs=True)
        if declared.exists():
            fulfillment_tasks.delete_from_customs.delay(
                list(declared.values_list("id", flat=True)), request.user.id
            )
            self.message_user(
                request,
                "Deleting shipments from customs database, this may take while...",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "No shipments was declared to customs, so deleting request was sent",
                level=messages.ERROR,
            )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj=obj))
        if obj and obj.is_paid:
            readonly_fields += [
                "total_price",
                "total_price_currency",
            ]
        return readonly_fields

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.update(get_status_actions(Status.SHIPMENT_TYPE))
        return actions

    def mark_as_paid(self, request, queryset):
        ct = ContentType.objects.get_for_model(self.model)
        fulfillment_tasks.mark_as_paid_task(
            ct.pk, list(queryset.values_list("id", flat=True)), request.user.id
        )
        self.message_user(
            request, message="Objects are being marked as paid, this may take a while"
        )

    def get_recipient(self, shipment):
        if not shipment.recipient_id:
            return ""

        recipient = shipment.recipient
        recipient_str = (
            f"{recipient.first_name} {recipient.last_name} (PIN: {recipient.id_pin})"
        )

        return recipient_str

    def get_urls(self):
        original_urls = super().get_urls()
        new_urls = [
            path(
                "fulfillment/shipment/refresh-package-states/",
                self.admin_site.admin_view(self.refresh_package_states),
                name="fulfillment_shipment_refresh_package_states",
            )
        ]
        return new_urls + original_urls

    def refresh_package_states(self, request):
        fulfillment_tasks.refresh_declared_packages.delay()
        self.message_user(request, "Refreshing package states...", level=messages.INFO)
        return redirect(request.META["HTTP_REFERER"])

    get_recipient.short_description = "recipient"


@admin.register(Assignment)
class AssignmentAdmin(SoftDeletionAdmin):
    search_fields = ["order__order_code", "assistant_profile__user__client_code"]
    list_display = [
        "assistant_profile",
        "order",
        "user",
        "is_completed",
        "created_at",
        "updated_at",
        "deleted_at",
    ]
    list_select_related = [
        "assistant_profile",
        "order__user",
    ]
    autocomplete_fields = ["order", "assistant_profile"]

    def user(self, assignment):
        return str(assignment.order.user)


class AssignmentInline(admin.TabularInline):
    autocomplete_fields = ["order"]
    model = Assignment
    extra = 0


@admin.register(ShoppingAssistantProfile)
class ShoppingAssistantProfileAdmin(admin.ModelAdmin):
    search_fields = [
        "user__client_code__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "user__email__icontains",
        "user__full_phone_number__icontains",
    ]
    list_display = ["user"]
    # inlines = [AssignmentInline]
    autocomplete_fields = ["user", "countries"]


@admin.register(WarehousemanProfile)
class WarehousemanProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "warehouse"]
    autocomplete_fields = ["user", "warehouse"]


class ShipmentInlineAdmin(admin.TabularInline):
    model = Shipment
    extra = 0
    autocomplete_fields = ["source_warehouse", "destination_warehouse"]
    fields = [
        "number",
        "source_warehouse",
        "destination_warehouse",
        "fixed_total_weight",
        "confirmed_properties",
        "is_added_to_box",
        "is_declared_by_user",
        "is_deleted_from_smart_customs",
    ]
    readonly_fields = [
        "number",
        "source_warehouse",
        "destination_warehouse",
        "is_added_to_box",
        "is_declared_by_user",
        "is_deleted_from_smart_customs",
    ]

    def has_add_permission(self, *args, **kwargs):
        return False


@admin.register(Box)
class BoxAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "transportation",
        "source_warehouse",
        "destination_warehouse",
        "total_weight",
        "shipments_count",
    ]
    inlines = [ShipmentInlineAdmin]
    autocomplete_fields = [
        "transportation",
        "source_warehouse",
        "destination_warehouse",
    ]
    search_fields = ["code__icontains"]
    readonly_fields = ["customs_state"]

    def customs_state(self, box: Box):
        all_shipment = box.shipments.count()
        added_to_boxes = box.shipments.filter(is_added_to_box=False).count()
        not_added_to_boxes = all_shipment - added_to_boxes
        data = (
            f"Total {all_shipment} shipments. {not_added_to_boxes} to sent to customs"
        )
        if added_to_boxes:
            data += ". <span style='color: red;'>Send them to prevent user from editing declarations!<span>"
        return mark_safe(f'<p style="font-weight: bold;">{data}</p>')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(shipments_count=Count("shipment"))

    def shipments_count(self, box):
        return box.shipments_count


@admin.register(CashierProfile)
class CashierProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "warehouse"]
    autocomplete_fields = ["warehouse", "user"]


@admin.register(AdditionalService)
class AdditionalServiceAdmin(TranslationAdmin):
    search_fields = ["title__icontains"]
    list_display = [
        "title",
        "type",
        "price",
        "price_currency",
        "needs_attachment",
        "needs_note",
    ]


@admin.register(WarehouseAdditionalService)
class WarehouseAdditionalServiceAdmin(admin.ModelAdmin):
    list_display = ["warehouse", "service"]
    autocomplete_fields = ["warehouse", "service"]
    search_fields = ["warehouse__codename__icontains", "service__title__icontains"]


class PackageAdditionalServiceAttachmentInline(admin.TabularInline):
    model = PackageAdditionalServiceAttachment
    extra = 0


@admin.register(PackageAdditionalService)
class PackageAdditionalServiceAdmin(admin.ModelAdmin):
    list_display = ["service", "package", "note"]
    autocomplete_fields = ["package", "service"]
    inlines = [PackageAdditionalServiceAttachmentInline]
    search_fields = [
        "package__user_tracking_code__icontains",
        "package__admin_tracking_code__icontains",
        "package__user__client_code__icontains",
        "package__user__first_name__icontains",
        "package__user__last_name__icontains",
        "package__user__email__icontains",
        "package__user__full_phone_number__icontains",
    ]


class ShipmentAdditionalServiceAttachmentInline(admin.TabularInline):
    model = ShipmentAdditionalServiceAttachment
    extra = 0


@admin.register(ShipmentAdditionalService)
class ShipmentAdditionalServiceAdmin(admin.ModelAdmin):
    list_display = ["service", "shipment", "note"]
    inlines = [ShipmentAdditionalServiceAttachmentInline]
    autocomplete_fields = [
        "shipment",
        "service",
    ]
    search_fields = [
        "shipment__number__icontains",
        "shipment__user__client_code__icontains",
        "shipment__user__first_name__icontains",
        "shipment__user__last_name__icontains",
        "shipment__user__email__icontains",
        "shipment__user__full_phone_number__icontains",
    ]


class BoxInlineAdmin(admin.StackedInline):
    model = Box
    classes = ("grp-collapse grp-closed",)
    extra = 0
    show_change_link = True
    fields = [
        "code",
        "source_warehouse",
        "destination_warehouse",
        "total_weight",
        "shipments_count",
        "shipments",
    ]
    autocomplete_fields = ["source_warehouse", "destination_warehouse"]

    readonly_fields = ["shipments_count", "shipments"]

    def shipments_count(self, box):
        return box.shipments.count()

    def shipments(self, box):
        return mark_safe(
            "<br>".join(
                list(
                    '<a href="%s">%s</a> - %s'
                    % (
                        reverse(
                            "admin:fulfillment_shipment_change", args=[shipment_id]
                        ),
                        shipment_number,
                        full_name,
                    )
                    for shipment_id, shipment_number, full_name in box.shipments.values_list(
                        "id",
                        "number",
                        "recipient__full_name",
                    )
                )
            )
        )


@admin.register(Transportation)
class TransportationAdmin(admin.ModelAdmin):
    change_form_template = "admin/fulfillment/transportation/change_form.html"
    inlines = [BoxInlineAdmin]
    list_display = [
        "number",
        "source_city",
        "destination_city",
        "departure_time",
        "arrival_time",
        "box_count",
        "airwaybill",
    ]
    search_fields = [
        "number__icontains",
        "source_city__name__icontains",
        "destination_city__name__icontains",
    ]
    readonly_fields = ["xml_manifest_last_export_time", "manifest_last_export_time"]
    autocomplete_fields = ["source_city", "destination_city"]
    actions = ["depesh"]

    def depesh(self, request, queryset):
        fulfillment_tasks.depesh_to_customs.delay(
            list(queryset.values_list("id", flat=True))
        )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(box_count=Count("box"))

    def box_count(self, transportation):
        return transportation.box_count

    def get_urls(self):
        original_urls = super().get_urls()

        custom_urls = [
            path(
                "exports/transportations/<int:pk>/manifest/",
                self.admin_site.admin_view(self.export_manifest_view),
                name="core-admin-export-transportation-manifest",
            ),
            path(
                "exports/transportations/<int:pk>/manifest/send/",
                self.admin_site.admin_view(self.send_manifest_view),
                name="core-admin-send-transportation-manifest",
            ),
            path(
                "exports/transportations/<int:pk>/manifest/excell/",
                self.admin_site.admin_view(self.export_excell),
                name="core-admin-generate-excell-manifest",
            ),
        ]

        return custom_urls + original_urls

    def export_manifest_view(self, request, pk):
        generator = XMLManifestGenerator(transportation_id=pk)
        xml_data = generator.generate()
        return HttpResponse(xml_data, content_type="application/xhtml+xml")
        return redirect(reverse("admin:fulfillment_transportation_change", args=[pk]))

    def send_manifest_view(self, request, pk):
        generator = XMLManifestGenerator(transportation_id=pk)
        generator.generate(send=True)

        messages.add_message(
            request,
            messages.INFO,
            "Manifest is being sent to email you have set in configurations!",
        )
        return redirect(reverse("admin:fulfillment_transportation_change", args=[pk]))

    def export_excell(self, request, pk):
        generator = ManifestGenerator(transportation_id=pk)
        generator.generate_excell()

        messages.add_message(
            request,
            messages.INFO,
            "Manifest Excell is generated. See manifest file field of transportation",
        )
        log_action(
            CHANGE,
            request.user.pk,
            instance=Transportation.objects.get(pk=pk),
            message="Exported excel manifest from this admin panel (core)",
        )
        return redirect(reverse("admin:fulfillment_transportation_change", args=[pk]))


@admin.register(QueuedItem)
class QueuedItemAdmin(admin.ModelAdmin):
    actions_on_top = True
    search_fields = [
        "code__icontains",
        "warehouse__codename__icontains",
        "queue__code__icontains",
        "user__client_code__icontains",
        "user__full_phone_number__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
    ]
    autocomplete_fields = [
        "user",
        "warehouse",
        "queue",
    ]
    list_display = [
        "code",
        "warehouse",
        "queue",
        "dest_queue",
        "user",
        "for_cashier",
        "cashier_ready",
        "warehouseman_ready",
        "customer_service_ready",
        "ready",
    ]
    list_select_related = True


class QueuedItemInline(admin.TabularInline):
    model = QueuedItem
    fk_name = "queue"
    autocomplete_fields = [
        "user",
        "queue",
    ]
    readonly_fields = ["shipments"]
    extra = 0

    def shipments(self, queued_item):
        return ", ".join(queued_item.shipments.values_list("number", flat=True))


@admin.register(Queue)
class QueueAdmin(admin.ModelAdmin):
    list_display = ["code", "type", "warehouse", "queued_items_count"]
    inlines = [QueuedItemInline]
    autocomplete_fields = [
        "monitor",
        "warehouse",
    ]
    search_fields = ["code", "warehouse__codename__icontains"]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(queued_items_count=Count("queued_item"))
        )

    def queued_items_count(self, queue):
        return queue.queued_items_count


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = [
        "type",
        "code",
        "queues",
        "warehouse",
    ]
    autocomplete_fields = ["auth", "warehouse"]
    search_fields = [
        "auth__client_code",
        "code",
    ]

    def queues(self, monitor):
        return ", ".join(q.code for q in monitor.queues.all())


@admin.register(CustomerServiceProfile)
class CustomerServiceProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "warehouse"]
    autocomplete_fields = ["user", "warehouse"]


@admin.register(CourierProfile)
class CourierProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "city"]
    autocomplete_fields = ["user", "city"]


@admin.register(Notification)
class NotificationAdmin(TranslatedSoftDeletionAdmin):
    search_fields = [
        "related_object_identifier__icontains",
        "user__client_code__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "user__email__icontains",
        "user__full_phone_number__icontains",
    ]
    list_filter = ["is_seen", "object_type", "seen_on"]
    list_display = [
        "user",
        "is_seen",
        "seen_on",
        "object_type",
        "related_object_identifier",
        "created_at",
        "deleted_at",
    ]
    autocomplete_fields = ["user"]


@admin.register(ShipmentReceiver)
class ShipmentReceiverAdmin(admin.ModelAdmin):
    list_display = [
        "shipment",
        "first_name",
        "last_name",
        "phone_number",
        "is_real_owner",
    ]


@admin.register(TrackingStatus)
class TrackingStatusAdmin(admin.ModelAdmin):
    list_display = [
        "pl_number",
        "problem_code",
        "tracking_code",
        "tracking_condition_code",
        "tracking_code_description",
        "mandatory_comment",
        "final_status",
        "delivery_status",
        "tracking_condition_code_description",
        "problem_code_description",
        "tracking_code_explanation",
    ]
    search_fields = [
        "pl_number__icontains",
        "problem_code__icontains",
        "tracking_code__icontains",
        "tracking_condition_code__icontains",
    ]
    ordering = ["pl_number"]


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "user", "created_at"]
    ordering = ["-created_at"]


@admin.register(ContactUsMessage)
class ContactUsMessageAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone_number", "user", "created_at"]
    ordering = ["-created_at"]


@admin.register(TicketCategory)
class TicketCategoryAdmin(TranslationAdmin):
    search_fields = ["title__icontains"]
    list_display = [
        "title",
        "can_select_order",
        "can_select_package",
        "can_select_shipment",
        "can_select_payment",
    ]


@admin.register(TicketAttachment)
class TicketAttachmentAdmin(admin.ModelAdmin):
    autocomplete_fields = ["ticket", "comment"]
    list_display = ["ticket", "comment", "file", "created_at", "updated_at"]


class TicketCommentInlineAdmin(admin.TabularInline):
    show_change_link = True
    model = TicketComment
    extra = 0
    autocomplete_fields = ["author"]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    autocomplete_fields = ["category", "user"]
    search_fields = [
        "user__client_code__icontains",
        "number__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "user__full_phone_number__icontains",
        "category__title__icontains",
    ]
    inlines = [TicketCommentInlineAdmin]
    list_display = [
        "number",
        "category",
        "status",
        "related_object_identifier",
        "created_at",
        "updated_at",
        "status_last_update_time",
        "answered_by_admin",
    ]


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    search_fields = [
        "ticket__user__client_code__icontains",
        "ticket__number__icontains",
        "ticket__user__first_name__icontains",
        "ticket__user__last_name__icontains",
        "ticket__user__full_phone_number__icontains",
        "ticket__category__title__icontains",
        "author__client_code__icontains",
        "author__first_name__icontains",
        "author__last_name__icontains",
        "author__full_phone_number__icontains",
    ]
    autocomplete_fields = ["ticket", "author"]
    list_display = [
        "ticket",
        "author",
        "created_at",
        "updated_at",
    ]


@admin.register(NotificationEvent)
class NotificationEventAdmin(TranslationAdmin):
    list_display = ["title", "sends_email", "sends_sms", "seen_on_web", "is_active"]
    readonly_fields = ["variables"]

    def sends_email(self, event: NotificationEvent):
        return bool(event.email_text or event.email_text_simple)

    def sends_sms(self, event: NotificationEvent):
        return bool(event.sms_text)

    def seen_on_web(self, event: NotificationEvent):
        return bool(event.web_title)

    sends_email.boolean = True
    sends_sms.boolean = True
    seen_on_web.boolean = True

    def variables(self, event: NotificationEvent):
        html_lines = []

        for reason, variables in event.REASON_VARIABLE_MAP.items():
            html_lines.append(
                "<i style='color: red'>Reason: %s</i><br><p>%s</p><br>"
                % (
                    NotificationEvent.get_display_for_reason(reason),
                    "<br>".join(map(lambda v: "<span>{{%s}}</span>" % v, variables)),
                )
            )

        return mark_safe("".join(html_lines))


class ShipmentInlineAdmin(admin.StackedInline):
    model = Shipment
    extra = 0
    show_change_link = True

    def has_add_permission(self, *args, **kwargs):
        return False

    def has_change_permission(self, *args, **kwargs):
        return False


@admin.register(CourierOrder)
class CourierOrderAdmin(admin.ModelAdmin):
    inlines = [ShipmentInlineAdmin, DiscountInline, TransactionInline]
    list_display = [
        "number",
        "status",
        "user",
        "region",
        "tariff",
        "total_price",
        "total_price_currency",
        "is_paid",
        "created_at",
        "shipment_count",
    ]
    autocomplete_fields = [
        "user",
        "status",
    ]
    list_filter = [
        "status",
        "is_paid",
        "created_at",
        "region",
        "tariff",
    ]
    readonly_fields = ["created_at"]
    search_fields = [
        "user__client_code__icontains",
        "number__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "user__full_phone_number__icontains",
        "shipment__number__icontains",
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(shipment_count=Count("shipment"))

    def shipment_count(self, courier_order):
        return courier_order.shipment_count

    def save_model(self, request, obj, form, change):
        if change and not obj.is_paid:
            obj._must_recalculate = True

        super().save_model(request, obj, form, change)


class CourierRegionInlineAdmin(TranslationTabularInline):
    model = CourierRegion
    extra = 0


class CourierTariffInlineAdmin(TranslationTabularInline):
    model = CourierTariff
    extra = 0


@admin.register(CourierArea)
class CourierAreaAdmin(TranslationAdmin):
    inlines = [CourierRegionInlineAdmin, CourierTariffInlineAdmin]
    autocomplete_fields = ["city", "warehouse"]
    list_display = [
        "title",
        "city",
        "warehouse",
        # "price",
        # "discounted_price",
        # "price_currency",
    ]


@admin.register(CustomerServiceLog)
class CustomerServiceLogAdmin(admin.ModelAdmin):
    list_display = ["user", "person_description", "problem_description", "created_at"]
    autocomplete_fields = ["user"]
    search_fields = [
        "user__client_code__icontains",
        "user__first_name__icontains",
        "user__last_name__icontains",
        "user__full_phone_number__icontains",
    ]


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ["name", "address", "url", "logo", "is_active", "display_order"]
    search_fields = ["name", "url"]
    list_filter = ["is_active"]


@admin.register(OrderedProduct)
class OrderedProductAdmin(admin.ModelAdmin):
    list_filter = ["country", "shop", "is_visible"]
    autocomplete_fields = [
        "shop",
        "country",
        "user",
        "price_currency",
        "shipping_price_currency",
        "category",
        "order",
        "shipment",
    ]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__client_code",
        "user__email",
        "shop__name",
    ]
    list_select_related = True
    list_display = [
        "description",
        "user_description",
        "user",
        "country",
        "shop",
        "category",
        "color",
        "size",
        "price",
        "price_currency",
        "shipping_price",
        "shipping_price_currency",
        "is_visible",
    ]


@admin.register(PromoCodeBenefit)
class PromoCodeBenefitAdmin(SoftDeletionAdmin):
    list_display = [
        "consumer",
        "promo_code",
        "used_by_consumer",
        "used_by_owner",
        "related_object_identifier",
        "created_at",
        "updated_at",
        "deleted_at",
    ]
    search_fields = [
        "promo_code__user__first_name",
        "promo_code__user__last_name",
        "promo_code__user__client_code",
        "promo_code__user__email",
        "related_object_identifier",
    ]
    list_filter = [
        "created_at",
        "updated_at",
        "used_by_consumer",
        "used_by_owner",
        "deleted_at",
    ]
    autocomplete_fields = ["promo_code", "consumer", "cashback_amount_currency"]


class PromoCodeBenefitInline(admin.StackedInline):
    model = PromoCodeBenefit
    extra = 0
    max_num = 0
    autocomplete_fields = ["consumer", "promo_code"]


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ["value", "user", "created_at", "updated_at"]
    list_filter = [
        "created_at",
        "updated_at",
    ]
    inlines = [PromoCodeBenefitInline]
    autocomplete_fields = ["user"]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__client_code",
        "user__email",
        "value",
    ]


@admin.register(CustomsProductType)
class CustomsProductTypeAdmin(TranslationAdmin):
    list_display = [
        "name",
        "parent",
        "original_id",
        "is_deleted",
        "created_at",
        "updated_at",
    ]
    search_fields = ["name", "original_id"]
    list_filter = [
        "is_deleted",
        "parent",
    ]

    def get_urls(self):
        original_urls = super().get_urls()
        new_urls = [
            path(
                "fulfillment/customsproducttype/refetchproducttypes/",
                self.admin_site.admin_view(self.refetch_product_types),
                name="fulfillment_customsproducttype_refetch",
            )
        ]

        return new_urls + original_urls

    def refetch_product_types(self, request):
        from domain.exceptions.smart_customs import SmartCustomsError

        try:
            fulfillment_tasks.update_customs_product_types()
        except SmartCustomsError as err:
            self.message_user(request, str(err), level=messages.ERROR)
        else:
            self.message_user(
                request, "Successfully updated product types", level=messages.SUCCESS
            )

        return redirect(request.META["HTTP_REFERER"])
