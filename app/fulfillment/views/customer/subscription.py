from django.db import IntegrityError
from rest_framework import generics, permissions

from fulfillment.models import Subscriber
from fulfillment.serializers.customer import SubscriberWriteSerializer


class SubscriberCreateApiView(generics.CreateAPIView):
    throttle_scope = "hard"
    permission_classes = [permissions.IsAuthenticated | permissions.AllowAny]
    queryset = Subscriber.objects.all()
    serializer_class = SubscriberWriteSerializer

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            try:
                serializer.save(user=self.request.user)
            except IntegrityError:
                pass  # ...create subscriber without user
        return super().perform_create(serializer)
