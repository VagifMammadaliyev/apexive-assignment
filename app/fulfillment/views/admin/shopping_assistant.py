from datetime import timedelta
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from django.db.models import (
    Prefetch,
    Q,
    CharField,
    Value as V,
    OuterRef,
    Exists,
    Min,
    Max,
)
from django.db import transaction as db_transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.contrib.admin.models import LogEntry, CHANGE, ContentType
from rest_framework import views, generics, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django_filters.rest_framework import DjangoFilterBackend

from ontime import messages as msg
from domain.logging.utils import log_generic_method
from domain.exceptions.logic import InvalidActionError
from domain.services import (
    set_remainder_price,
    promote_status,
    approve_remainder_price,
    create_packages_from_orders,
    create_package_from_orders,
    create_notification,
)
from customer.models import Role, Customer
from customer.permissions import IsOntimeAdminUser, IsShoppingAssistant
from fulfillment.models import (
    Order,
    Assignment,
    Status,
    Package,
    ShoppingAssistantProfile,
    NotificationEvent as EVENTS,
    Shop,
)
from fulfillment.serializers.admin import shopping_assistant as sa_serializers
from fulfillment.pagination import ShoppingAssistantPagination
from fulfillment.filters import AdminOrderFilter

User = get_user_model()


@api_view(["GET"])
@permission_classes([IsOntimeAdminUser])
def autocomplete_assistant_view(request):
    assistants = (
        ShoppingAssistantProfile.objects.annotate(
            full_name=Concat(
                "user__first_name", V(" "), "user__last_name", output_field=CharField()
            )
        )
        .filter(full_name__icontains=request.query_params.get("full_name", ""))
        .select_related("user")
    )

    return Response(
        sa_serializers.ShoppingAssistantAutocompleteSerializer(
            assistants, many=True
        ).data
    )


class AssignmentStatusListApiView(generics.ListAPIView):
    """Just statuses for orders except first one, when it is not paid."""

    pagination_class = None
    permission_classes = [IsShoppingAssistant | IsOntimeAdminUser]
    serializer_class = sa_serializers.StatusSerializer

    def get_queryset(self):
        return Status.objects.filter(type=Status.ORDER_TYPE)


class DashboardApiView(generics.ListAPIView):
    permission_classes = [IsShoppingAssistant | IsOntimeAdminUser]
    serializer_class = sa_serializers.OrderReadSerializer
    pagination_class = ShoppingAssistantPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = AdminOrderFilter

    def get_ordering_param(self):
        return self.request.query_params.get("ordering")

    def get_ordering(self):
        ordering = self.get_ordering_param()

        ordering_map = {
            "old": "as_assignment__created_at",
            "new": "-as_assignment__created_at",
        }

        return ordering_map.get(ordering, ordering_map.get("new"))

    def get_ordering_helper_func(self, ordering):
        """
        If ordering by new, then we must annotate by MAX(created_at),
        otherwise MIN(created_at).
        """
        if ordering == "old":
            return Min

        return Max

    def get_delay_days(self, default=None):
        """
        Parse `delay` in query_param that shows how much days related package is delayed.
        """
        delay = self.request.query_params.get("delay", default)

        if delay is not None:
            try:
                parsed_delay = int(delay)
                if parsed_delay > 0:
                    return parsed_delay
            except (ValueError, TypeError):
                return default

        return None

    def get_treshold(self):
        today = timezone.now().date()
        package_delay_time = self.get_delay_days()

        if package_delay_time is None:
            return None

        return today - timedelta(days=package_delay_time)

    def get_queryset(self):
        staff_user = self.request.user
        is_admin = staff_user.role.type == Role.ADMIN
        order_status_ids = self.request.query_params.getlist("status", [])
        status_query = (
            Q(status__id__in=order_status_ids)
            if order_status_ids and all(order_status_ids)
            else Q(status__codename__in=["paid", "processing"])
        )
        customer_id = self.request.query_params.get("customer")

        treshold = self.get_treshold()
        treshold_query = (
            Q(package__is_accepted=False, package__arrival_date__lte=treshold)
            if treshold
            else Q()
        )

        # ordering = self.get_ordering_param()
        # assigned_at_func = self.get_ordering_helper_func(ordering)

        orders = (
            Order.objects.filter(
                treshold_query,  # check that package is being delayed
                status_query,
                Q(as_assignment__assistant_profile__user=staff_user)
                if not is_admin  # this assistant's assignments if not admin
                else Q(
                    as_assignment__isnull=False
                ),  # otherwise all assignments must be returned
                Q(user_id=customer_id) if customer_id else Q(),
            )
            .order_by(self.get_ordering())
            .select_related("as_assignment__assistant_profile__user", "package")
        )

        keyword_query = self.request.query_params.get("q")
        if keyword_query:
            orders = orders.filter(
                Q(order_code__icontains=keyword_query)
                | Q(external_order_code__icontains=keyword_query)
                | Q(package__admin_tracking_code__icontains=keyword_query)
                | Q(package__user_tracking_code__icontains=keyword_query)
            )

        return orders

        # # Return all customer, if staff_user is admin
        # customers = Customer.objects.annotate(
        #     order_exists=Exists(order_subquery),
        #     assigned_at=assigned_at_func("order__as_assignment__created_at"),
        # ).filter(Q(id=customer_id) if customer_id else Q(), order_exists=True)

        # return customers.order_by(self.get_ordering()).prefetch_related(
        #     Prefetch(
        #         "orders",
        #         queryset=Order.objects.filter(
        #             treshold_query,
        #             status_query,
        #             Q(as_assignment__assistant_profile__user=staff_user)
        #             if not is_admin
        #             else Q(as_assignment__isnull=False),
        #         ).select_related("as_assignment__assistant_profile__user", "package"),
        #         to_attr="prefetched_orders",
        #     )
        # )


class OrderRetrieveUpdateDestroyApiView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsShoppingAssistant | IsOntimeAdminUser]

    def get_serializer_class(self, *args, **kwargs):
        if self.request.method == "GET":
            return sa_serializers.OrderReadSerializer
        return sa_serializers.OrderWriteSerializer

    def get_object(self):
        orders = self.get_queryset()
        order = get_object_or_404(orders, order_code=self.kwargs.get("order_code"))

        if self.request.method in ["PATCH", "PUT"]:
            if not order.can_assistant_edit_order:
                raise InvalidActionError
        elif self.request.method == "DELETE":
            if not order.can_assistant_reject_order:
                raise InvalidActionError

        return order

    def get_queryset(self):
        staff_user = self.request.user
        orders = Order.objects.filter(as_assignment__isnull=False)

        if staff_user.role.type != Role.ADMIN:
            orders = orders.filter(as_assignment__assistant_profile__user=staff_user)

        return orders

    @db_transaction.atomic
    @log_generic_method
    def perform_update(self, serializer):
        old_order = self.get_object()
        order = serializer.save()

        # if any(
        #     field_name.startswith("real")
        #     for field_name in serializer.validated_data.keys()
        # ):
        #     set_remainder_price(order, staff_user=self.request.user)

        recalc_remainder = False

        for field_name in serializer.validated_data.keys():
            if field_name.startswith("real"):
                old_field_value = getattr(old_order, field_name, None)
                if old_field_value is not None:
                    new_field_value = serializer.validated_data.get(field_name)
                    if field_name.endswith("currency"):
                        if old_field_value.id != new_field_value.id:
                            recalc_remainder = True
                            break
                    elif Decimal(new_field_value) != Decimal(old_field_value):
                        recalc_remainder = True
                        break

        if recalc_remainder:
            set_remainder_price(order, staff_user=self.request.user)

        # Automatically set status to processing if external order code is added
        if (
            order.status.codename == "paid" and order.external_order_code
        ):  # ...check if not processing already
            promote_status(
                order,
                to_status=Status.objects.get(
                    type=Status.ORDER_TYPE, codename="processing"
                ),
            )
            LogEntry.objects.log_action(
                user_id=self.request.user.id,
                content_type_id=ContentType.objects.get_for_model(order).pk,
                object_id=order.id,
                object_repr=str(order),
                action_flag=CHANGE,
                change_message="Assistant started processing this order (added external order code)",
            )
            create_notification(order, EVENTS.ON_ORDER_EXTERNAL_CODE_ADD, [order.user])

    def perform_destroy(self, order):
        promote_status(
            order,
            Status.objects.get(type=Status.ORDER_TYPE, codename="deleted"),
            staff_user_id=self.request.user.id,
        )


@api_view(["GET", "POST"])
@permission_classes([IsShoppingAssistant | IsOntimeAdminUser])
def comment_order_view(request, order_code):
    staff_user = request.user
    staff_user_query = (
        Q(as_assignment__assistant_profile__user=staff_user)
        if staff_user.role.type != Role.ADMIN
        else Q()
    )
    order = get_object_or_404(
        Order.objects.filter(staff_user_query), order_code=order_code
    )

    if request.method == "GET":
        return Response(
            sa_serializers.CommentReadSerializer(order.comments.all(), many=True).data
        )

    # POST method
    serializer = sa_serializers.CommentWriteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    comment = serializer.save(author=staff_user, order=order)
    create_notification(order, EVENTS.ON_ORDER_COMMENT_CREATE, [order, order.user])

    return Response(
        sa_serializers.CommentReadSerializer(comment).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsOntimeAdminUser | IsShoppingAssistant])
def approve_remainder_price_view(request, order_code):
    staff_user = request.user
    staff_user_query = (
        Q(as_assignment__assistant_profile__user=staff_user)
        if staff_user.role.type != Role.ADMIN
        else Q()
    )
    order = get_object_or_404(
        Order.objects.filter(staff_user_query), order_code=order_code
    )
    transaction = approve_remainder_price(staff_user, order)
    return Response({"status": "OK"}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsOntimeAdminUser | IsShoppingAssistant])
def create_packages_from_orders_view(request):
    serializer = sa_serializers.PackageWriteSerializer(
        data=request.data, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)

    staff_user = request.user

    orders = serializer.validated_data["orders"]
    package = create_package_from_orders(
        staff_user,
        orders,
        serializer.validated_data.get("admin_tracking_code", ""),
        serializer.validated_data.get("arrival_date", None),
    )

    return Response(
        sa_serializers.PackageReadSerializer(
            package,
        ).data,
        status=status.HTTP_201_CREATED,
    )


# This endpoint is not used currently
@api_view(["POST"])
@permission_classes([IsOntimeAdminUser])
def reassign_shopping_assistant_view(request, assignment_id):
    assistant_id = request.data.get("assistant_id")
    if (
        assistant_id
        and ShoppingAssistantProfile.objects.filter(id=assistant_id).exists()
    ):
        Assignment.objects.filter(id=assignment_id).update(
            assistant_profile_id=assistant_id
        )
    return Response({"status": "OK"})


@api_view(["POST"])
@permission_classes([IsOntimeAdminUser | IsShoppingAssistant])
@db_transaction.atomic
def start_processing_order_view(request, assignment_id):
    staff_user = request.user
    staff_user_query = (
        Q(as_assignment__assistant_profile__user=staff_user)
        if staff_user.role.type != Role.ADMIN
        else Q()
    )

    order = Order.objects.filter(
        staff_user_query,
        status__codename__in=["paid"],
        as_assignment__id=assignment_id,
    ).first()

    if order:
        promote_status(
            order,
            to_status=Status.objects.get(type=Status.ORDER_TYPE, codename="processing"),
        )
        LogEntry.objects.log_action(
            user_id=staff_user.id,
            content_type_id=ContentType.objects.get_for_model(order).pk,
            object_id=order.id,
            object_repr=str(order),
            action_flag=CHANGE,
            change_message="Assistant started processing this order",
        )

    return Response({"status": "OK"})


class ShopViewSet(viewsets.ModelViewSet):
    pagination_class = None
    queryset = Shop.objects.order_by("name")
    serializer_class = sa_serializers.ShopSerializer
    permission_classes = [IsShoppingAssistant | IsOntimeAdminUser]
