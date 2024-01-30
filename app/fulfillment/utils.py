import functools

from django.db import transaction
from django.contrib import messages

from domain.services import promote_status
from domain.services import promote_status
from fulfillment.models import Status


def get_status_actions(status_type):
    """
    Returns dynamically created actions for manipulating statuses
    of "fulfillment" objects.
    """
    actions = {}

    def __action__(modeladmin, request, queryset, status=None):
        instances = list(queryset.all())
        len_instances = len(instances)

        if len_instances > 100:
            modeladmin.message_user(
                request, "Too many objects selected!", messages.ERROR
            )

        with transaction.atomic():
            for instance in instances:
                promote_status(instance, to_status=status)

        modeladmin.message_user(request, "Updated selected items!", messages.SUCCESS)

    for status in Status.objects.filter(type=status_type):
        __partial_action__ = functools.partial(__action__, status=status)
        __func_name__ = "make_object_%s" % (status.codename)
        __verbose_name__ = "Change status to %s" % (status)
        __partial_action__.__name__ = __func_name__
        actions[__func_name__] = (
            __partial_action__,
            __func_name__,
            __verbose_name__,
        )

    return actions
