from django.db.models import Q


def filter_by_archive_status(queryset, request):
    is_archived = "archived" in request.query_params
    queryset = queryset.filter(is_archived=is_archived)

    return queryset


class UserDeclaredFilterMixin:
    def _get_user_declared_filter(self):
        true_values = ["1", "true"]
        false_values = ["0", "false"]
        boolean_values = true_values + false_values
        is_declared_by_user = self.request.query_params.get("is_declared_by_user")
        if is_declared_by_user in boolean_values:
            return True if is_declared_by_user in true_values else False
        return None

    def filter_by_user_declared(self, shipments):
        is_user_declared = self._get_user_declared_filter()
        if is_user_declared is not None:
            return shipments.filter(
                (Q(is_declared_by_user=True) | Q(exclude_from_smart_customs=True))
                if is_user_declared
                else Q(is_declared_by_user=False) & Q(exclude_from_smart_customs=False)
            )
        return shipments
