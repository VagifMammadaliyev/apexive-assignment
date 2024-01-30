from rest_framework import generics, permissions

from fulfillment.models import ContactUsMessage
from fulfillment.serializers.customer import ContactUsMessageWriteSerializer


class ContactUsMessageCreateApiView(generics.CreateAPIView):
    throttle_scope = "hardcore"
    queryset = ContactUsMessage.objects.all()
    serializer_class = ContactUsMessageWriteSerializer
    permission_classes = [permissions.AllowAny | permissions.IsAuthenticated]

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            return serializer.save(user=self.request.user)
        return super().perform_create(serializer)
