from django.utils import timezone
from rest_framework import generics, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from fulfillment.models import Notification
from fulfillment.filters import NotificationFilter
from fulfillment.serializers.customer import (
    NotificationSerializer,
    NotificationCompactSerializer,
)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def get_unseen_notifications_data_view(request):
    last_notification = (
        request.user.notifications.filter(must_be_seen_on_web=True)
        .order_by("-created_at")
        .only("created_at")
        .first()
    )

    return Response(
        {
            "unseen_count": request.user.notifications.filter(
                is_seen=False, must_be_seen_on_web=True
            ).count(),
            "last_notification_on": last_notification and last_notification.created_at,
        }
    )


class NotificationReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_class = NotificationFilter

    def get_object(self, *args, **kwargs):
        notification = super().get_object(*args, **kwargs)

        if not notification.is_seen:
            notification.seen_on = timezone.now()
            notification.is_seen = True
            notification.save(update_fields=["seen_on", "is_seen"])

        return notification

    def get_queryset(self):
        notifications = self.request.user.notifications.order_by(
            "is_seen", "-created_at"
        )

        return notifications.filter(must_be_seen_on_web=True)

    def filter_queryset(self, *args, **kwargs):
        qs = super().filter_queryset(*args, **kwargs)

        if "compact" in self.request.query_params:
            qs = qs[:10]

        return qs

    def paginate_queryset(self, *args, **kwargs):
        if "compact" in self.request.query_params:
            return None

        return super().paginate_queryset(*args, **kwargs)

    def get_serializer_class(self):
        if self.action == "list":
            return NotificationCompactSerializer
        return NotificationSerializer


@api_view(["POST"])
def mark_all_as_read(request):
    updated_count = request.user.notifications.filter(is_seen=False).update(
        is_seen=True, seen_on=timezone.now()
    )
    return Response({"status": "OK", "seen": updated_count})
