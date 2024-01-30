import inspect
import functools

from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from rest_framework.serializers import Serializer
from rest_framework.viewsets import GenericViewSet

from ontime.utils import copy_func
from domain.logging.constants import PERFORMING_METHOD_NAMES, ActionLevel


def extract_changes(data_dict):
    changes = []

    for field_name, field_value in data_dict.items():
        if isinstance(field_value, dict):
            continue
        changes.append(
            {"changed": {"fields": ["%s -> %s" % (field_name, field_value)]}}
        )

    return changes


def generate_change_message(serializer) -> list:
    return extract_changes(serializer.validated_data)


def log_action(action_flag, user_id, instance=None, serializer=None, message=None):
    instance = instance or serializer.instance

    change_message = ""
    if action_flag == CHANGE and serializer:
        change_message = generate_change_message(serializer)
    elif action_flag == ADDITION:
        change_message = "Added"
    elif action_flag == DELETION:
        change_message = "Deleted"
    else:
        change_message = message

    log_entry = LogEntry.objects.log_action(
        user_id=user_id,
        content_type_id=ContentType.objects.get_for_model(instance).pk,
        object_id=instance.id,
        object_repr=str(instance),
        action_flag=action_flag,
        change_message=change_message,
    )

    action_level = ActionLevel[action_flag]

    if action_level == ActionLevel.DANGER:
        # Notify about dangerous action
        print("DANGEROUS ACTION %s" % log_entry)


def log_generic_method(performing_function):
    """
    Wraps generic viewset function so it can log changed data.

    This decorator handles two cases:
        1. When method takes serializer argument -> it is addition or change
        2. When method takes only instance -> it is deletion
    """

    @functools.wraps(performing_function)
    def wrapped(view, *args, **kwargs):
        result = performing_function(view, *args, **kwargs)

        if len(args) and isinstance(args[0], Serializer):  # ...addition or change
            flag = ADDITION if view.request.method == "POST" else CHANGE
            serializer = args[0]

            # We assume that view is for admin therefore user will always present
            log_action(flag, view.request.user.id, serializer=serializer)

        elif len(args) == 1:  # ...deletion
            instance = args[0]
            log_action(DELETION, view.request.user.id, instance=instance)

        return result

    return wrapped


def generic_logging(klass):
    """
    Wraps performing generic methods of ModelViewSet using log_generic_method decorator.
    """

    assert inspect.isclass(klass) and issubclass(klass, GenericViewSet), (
        "Can wrap only subclasses of %s class" % GenericViewSet.__name__
    )

    methods = [
        getattr(klass, method_name, None) for method_name in PERFORMING_METHOD_NAMES
    ]

    for method in methods:
        if method and hasattr(method, "__name__"):
            copy_method = copy_func(method)
            setattr(klass, method.__name__, log_generic_method(copy_method))

    return klass
