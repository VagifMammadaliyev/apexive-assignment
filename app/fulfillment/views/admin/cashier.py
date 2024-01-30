from django.shortcuts import get_list_or_404, get_object_or_404
from rest_framework import views, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from domain.services import complete_payments
from fulfillment.models import Shipment, Transaction
from fulfillment.filters import ShipmentCashierFilter
from fulfillment.serializers.admin import cashier as cash_serializers
from customer.permissions import IsCashier, IsOntimeAdminUser


class CashierDashboardApiView(generics.ListAPIView):
    permission_classes = [IsOntimeAdminUser | IsCashier]
    serializer_class = cash_serializers.ShipmentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = ShipmentCashierFilter

    def get_queryset(self):
        cashier = self.request.user.cashier_profile

        return Shipment.objects.filter(
            current_warehouse=cashier.warehouse_id,
            status__codename__in=["done", "received"],
        )


# @api_view(["POST"])
# @permission_classes([IsCashier | IsOntimeAdminUser])
# def pay_for_shipment_view(request):
#     cashier = request.user.cashier_profile
#     invoice_numbers = request.data.get("invoice_numbers", [])
#     new_payment_type = request.data.get("payment_type", None)

#     transaction = complete_payments(
#         Transaction.objects.filter(
#             purpose=Transaction.SHIPMENT_PAYMENT,
#             completed=False,
#             invoice_number__in=invoice_numbers,
#         ),
#         override_type=new_payment_type,
#         callback=create_cashier_payment_log_callback,
#         callback_params={"staff_user_id": request.user.id},
#     )
#     return Response({"status": "OK"})
