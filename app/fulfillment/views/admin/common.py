from django.db.models import Q, Value as V, Exists, OuterRef, CharField
from django.db.models.functions import Concat
from django.contrib.auth import get_user_model
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from customer.permissions import IsOntimeStaffUser
from customer.models import Recipient
from fulfillment.models import Order, Package
from fulfillment.serializers.admin import common as common_serializers

User = get_user_model()


@api_view(["GET"])
@permission_classes([IsOntimeStaffUser])
def autocomplete_user_view(request):
    query = request.query_params.get("q", "")

    first_last_name_query = Q(first_last_name__icontains=query)
    last_first_name_query = Q(last_first_name__icontains=query)
    last_name_query = Q(last_name__icontains=query)
    client_code_query = Q(client_code__icontains=query)
    phone_number_query = Q(full_phone_number__icontains=query)
    order_subquery = Order.objects.filter(order_code__icontains=query)
    order_code_query = Exists(
        order_subquery.filter(user__id=OuterRef("pk")).values("pk")
    )
    package_subquery = Package.objects.filter(
        Q(user_tracking_code__icontains=query) | Q(admin_tracking_code__icontains=query)
    )
    tracking_code_query = Exists(
        package_subquery.filter(user__id=OuterRef("pk")).values("pk")
    )

    users = User.objects.annotate(
        first_last_name=Concat(
            "first_name", V(" "), "last_name", output_field=CharField()
        ),
        last_first_name=Concat(
            "last_name", V(" "), "first_name", output_field=CharField()
        ),
        package_exists=tracking_code_query,
        order_exists=order_code_query,
    ).filter(
        first_last_name_query
        | last_first_name_query
        | last_name_query
        | phone_number_query
        | client_code_query
        | Q(package_exists=True)
        | Q(order_exists=True),
        is_active=True,
    )

    return Response(
        common_serializers.UserAutocompleteSerializer(users, many=True).data
    )


class CustomerRecipientListApiView(generics.ListAPIView):
    permission_classes = [IsOntimeStaffUser]
    pagination_class = None
    serializer_class = common_serializers.RecipientSerializer

    def get_queryset(self):
        return Recipient.objects.filter(
            user=self.kwargs.get("customer_pk"), is_deleted=False
        )
