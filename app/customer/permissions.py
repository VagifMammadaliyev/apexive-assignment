from rest_framework import permissions

from customer.models import Role
from fulfillment.models import Monitor


class IsOntimeStaffUser(permissions.IsAdminUser):
    role_type = None

    def has_ontime_permission(self, request, view):
        if self.role_type:
            return request.user.role.type == self.role_type
        return True

    def has_permission(self, request, view):
        return bool(
            super().has_permission(request, view)
            and self.has_ontime_permission(request, view)
        )


class IsOntimeAdminUser(IsOntimeStaffUser):
    role_type = Role.ADMIN


class IsContentManager(IsOntimeStaffUser):
    role_type = Role.CONTENT_MANAGER


class IsShoppingAssistant(IsOntimeStaffUser):
    role_type = Role.SHOPPING_ASSISTANT


class IsWarehouseman(IsOntimeStaffUser):
    role_type = Role.WAREHOUSEMAN


class IsCashier(IsOntimeStaffUser):
    role_type = Role.CASHIER


class IsMonitor(IsOntimeStaffUser):
    role_type = Role.MONITOR


class IsCustomerMonitor(IsMonitor):
    """Monitor used by customer to select his shipments."""

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            monitor = getattr(request.user, "as_monitor")
            if monitor:
                return monitor.type == Monitor.FOR_CUSTOMER

        return False


class IsQueueMonitor(IsMonitor):
    """Monitor placed at the top of queue to show customer whether he can approach"""

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            monitor = getattr(request.user, "as_monitor")
            if monitor:
                return monitor.type == Monitor.FOR_QUEUE

        return False


class IsCustomerService(IsOntimeStaffUser):
    role_type = Role.CUSTOMER_SERVICE


class IsCustomsAgent(IsOntimeStaffUser):
    role_type = Role.CUSTOMS_AGENT
