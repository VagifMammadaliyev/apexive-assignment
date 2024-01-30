from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from rest_framework import serializers

from fulfillment.models import (
    Assignment,
    Order,
    Product,
    Package,
    ShoppingAssistantProfile,
    Comment,
    Shop,
)
from fulfillment.serializers.common import (
    StatusSerializer,
    ProductCategoryCompactSerializer,
    ProductTypeExtraCompactSerializer,
)
from core.serializers.admin import (
    CurrencyCompactSerializer,
    CountryCompactSerializer,
    CountryReadSerializer,
)
from customer.serializers import BalanceSerializer
from customer.models import Customer, User, Recipient, Role


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ["id", "name", "address", "logo"]


class ShoppingAssistantAutocompleteSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")

    class Meta:
        model = ShoppingAssistantProfile
        fields = [
            "id",
            "first_name",
            "last_name",
        ]


class ProductReadSerializer(serializers.ModelSerializer):
    description = serializers.CharField(source="normalized_description", read_only=True)
    price_currency = CurrencyCompactSerializer(read_only=True)
    category = ProductCategoryCompactSerializer(read_only=True)
    type = ProductTypeExtraCompactSerializer(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "type",
            "description",
            "quantity",
            "url",
            "price",
            "price_currency",
        ]


class PackageReadSerializer(serializers.ModelSerializer):
    status = StatusSerializer(read_only=True)
    source_country = CountryCompactSerializer(read_only=True)
    products = ProductReadSerializer(many=True, read_only=True)

    class Meta:
        model = Package
        fields = [
            "id",
            "tracking_code",
            "seller",
            "status",
            "source_country",
            "products",
            "attachment",
            "arrival_date",
            "delay_days",
            # "user_note",
            "created_at",
            "status_last_update_time",
        ]


class PackageWriteSerializer(serializers.ModelSerializer):
    orders = serializers.ListField(
        child=serializers.CharField(), allow_null=False, allow_empty=False
    )
    tracking_code = serializers.CharField(
        max_length=40, source="admin_tracking_code", required=True, allow_blank=False
    )

    def validate_orders(self, order_codes):
        request = self.context["request"]
        staff_user = request.user
        staff_user_query = (
            Q(as_assignment__assistant_profile__user=staff_user)
            if staff_user.role.type != Role.ADMIN
            else Q()
        )
        orders = Order.objects.filter(
            staff_user_query,
            order_code__in=order_codes,
        ).prefetch_related("as_assignment")

        package_tracking_code = self.initial_data["tracking_code"]

        good_orders = []
        for order in orders:
            if not order.package_id or (
                order.package_id
                and order.package.tracking_code != package_tracking_code
            ):
                good_orders.append(order)

        if not good_orders:
            raise serializers.ValidationError("These orders already have packages")

        checkable_orders = list(
            Order.objects.filter(package__admin_tracking_code=package_tracking_code)
        ) + list(orders)

        one_click = [o.is_oneclick for o in checkable_orders]
        if not len(set(one_click)) == 1:
            raise serializers.ValidationError(
                "All orders must be either one-click or not one-click"
            )

        recipients_id = [
            o.recipient_id and o.recipient.real_recipient_id for o in checkable_orders
        ]
        if not len(set(recipients_id)) == 1:
            raise serializers.ValidationError(
                "All orders must have the same recipient id or not at all"
            )

        country = [o.source_country_id for o in checkable_orders]
        if not len(set(country)) == 1:
            raise serializers.ValidationError(
                "All orders must be related for the same country"
            )

        dest_wh = [o.destination_warehouse_id for o in checkable_orders]
        if not len(set(country)) == 1:
            raise serializers.ValidationError(
                "All orders must go to the same destination warehouse"
            )

        return orders

    class Meta:
        model = Package
        fields = ["orders", "tracking_code", "arrival_date", "seller"]


class OrderWriteSerializer(serializers.ModelSerializer):
    seller = serializers.CharField(source="product_seller", required=True)
    seller_address = serializers.CharField(
        source="product_seller_address", required=True
    )

    class Meta:
        model = Order
        fields = [
            # "source_country",
            "seller",
            "seller_address",
            "external_order_code",
            "product_category",
            "product_type",
            "product_description",
            "shop",
            "real_product_quantity",
            "real_product_price",
            "real_product_price_currency",
            "real_cargo_price",
            "real_cargo_price_currency",
            # "real_total_price",
            "real_total_price_currency",
        ]
        extra_kwargs = {"product_category": {"required": True}}

    def to_representation(self, instance):
        return OrderReadSerializer(instance).data

    def validate(self, data):
        product_category = data.get("product_category")
        product_type = data.get("product_type")
        product_desc = data.get("product_description")

        if product_category and product_category.needs_description and not product_desc:
            raise serializers.ValidationError(
                {
                    "product_description": "Product description must be specified for selected category"
                }
            )

        return data


class CommentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["body"]
        extra_kwargs = {
            "body": {"allow_blank": False, "allow_null": False, "required": True}
        }

    def validate(self, data):
        body = data.pop("body", "")

        # Fix languages for comment body
        for lang_code, lang_name in settings.LANGUAGES:
            data["body_%s" % lang_code] = body

        return data

    def to_representation(self, instance):
        return CommentReadSerializer(instance).data


class CommentReadSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "title", "body", "time"]

    def get_time(self, comment):
        return timezone.localtime(comment.created_at).strftime("%d/%m/%Y %H:%M")


class AssigneeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "first_name", "last_name"]


class AssignmentSerializer(serializers.ModelSerializer):
    # order = OrderReadSerializer(read_only=True)
    assignee = AssigneeSerializer(source="assistant_profile.user")

    class Meta:
        model = Assignment
        fields = [
            "id",
            "assignee",
            "created_at",
            "updated_at",
            "is_completed",
            # "order",
        ]


class CustomerSerializer(serializers.ModelSerializer):
    active_balance = BalanceSerializer()
    phone_number = serializers.CharField(source="full_phone_number")
    # assignments = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "client_code",
            "first_name",
            "last_name",
            "phone_number",
            "email",
            "active_balance",
            # "assignments",
        ]

    # def get_assignments(self, customer):
    #     assignments = [order.as_assignment for order in customer.prefetched_orders]
    #     return AssignmentSerializer(assignments, many=True).data


class RecipientCompactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipient
        fields = [
            "id",
            "title",
            "full_name",
            "id_pin",
            "phone_number",
            "address",
        ]


class OrderReadSerializer(serializers.ModelSerializer):
    assignment = AssignmentSerializer(read_only=True, source="as_assignment")
    customer = CustomerSerializer(read_only=True, source="user")
    status = StatusSerializer(read_only=True)
    source_country = CountryCompactSerializer(read_only=True)
    product_price_currency = CurrencyCompactSerializer(read_only=True)
    real_product_price_currency = CurrencyCompactSerializer(read_only=True)
    cargo_price_currency = CurrencyCompactSerializer(read_only=True)
    real_cargo_price_currency = CurrencyCompactSerializer(read_only=True)
    commission_price_currency = CurrencyCompactSerializer(read_only=True)
    total_price_currency = CurrencyCompactSerializer(read_only=True)
    real_total_price_currency = CurrencyCompactSerializer(read_only=True)
    remainder_price_currency = CurrencyCompactSerializer(read_only=True)
    product_category = ProductCategoryCompactSerializer(read_only=True)
    product_type = ProductTypeExtraCompactSerializer(read_only=True)
    package = PackageReadSerializer(read_only=True)
    comments = CommentReadSerializer(read_only=True, many=True)
    actions = serializers.SerializerMethodField()
    seller = serializers.CharField(source="product_seller", read_only=True)
    seller_address = serializers.CharField(
        source="product_seller_address", read_only=True
    )
    shop = ShopSerializer(read_only=True)
    recipient = RecipientCompactSerializer(
        read_only=True, source="recipient.real_recipient"
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "identifier",
            "order_code",
            "external_order_code",
            "customer",
            "assignment",
            "status",
            "is_paid",
            "source_country",
            "description",
            "seller",
            "seller_address",
            "shop",
            "recipient",
            "show_on_slider",
            "product_color",
            "product_size",
            "product_url",
            "product_quantity",
            "real_product_quantity",
            "product_description",
            "product_category",
            "product_type",
            "product_price",
            "real_product_price",
            "product_price_currency",
            "real_product_price_currency",
            "cargo_price",
            "real_cargo_price",
            "cargo_price_currency",
            "real_cargo_price_currency",
            "commission_price",
            "commission_price_currency",
            "paid_amount",
            "total_price",
            "real_total_price",
            "total_price_currency",
            "real_total_price_currency",
            "remainder_price",
            "remainder_price_currency",
            "created_at",
            "status_last_update_time",
            "user_note",
            "actions",
            "package",
            "comments",
        ]

    def get_actions(self, order: Order):
        return {
            "can_edit_order": order.can_assistant_edit_order,
            "can_reject_order": order.can_assistant_reject_order,
            "can_add_package": order.can_assistant_add_package,
            "can_start_processing": order.can_assistant_start_processing,
            "can_approve_remainder_price": order.can_assistant_approve_remainder_price,
        }


class ShoppingAssistantProfileSerializer(serializers.ModelSerializer):
    countries = CountryReadSerializer(many=True, read_only=True)

    class Meta:
        model = ShoppingAssistantProfile
        fields = ["countries"]
