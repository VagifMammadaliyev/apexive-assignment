import os
import inspect
import types
import functools
import re

import redis
from slugify import slugify_ru
from django.urls import reverse
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import ugettext as _
from django.contrib.admin import ModelAdmin
from django.http import JsonResponse
from djangorestframework_camel_case.util import camelize_re, underscore_to_camel
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework.views import exception_handler as default_exception_handler
from rest_framework.response import Response

from ontime import messages as msg
from domain.exceptions.base import OnTimeException


def parse_int(number):
    try:
        return int(number)
    except (ValueError, TypeError):
        return None


def camel_case_to_snake_case(text):
    humps = re.sub("([A-Z][a-z]+)", r" \1", re.sub("([A-Z]+)", r" \1", text)).split()
    return "-".join(humps).lower()


def get_exception_type(exc):
    return camel_case_to_snake_case(exc.__class__.__name__)


def _normalize_validation_error(field_name, errors):
    field_name_camelized = re.sub(camelize_re, underscore_to_camel, field_name)
    normalized_errors = {"field": field_name_camelized}
    messages = []
    nested = False

    if isinstance(errors, dict):  # error of nested object (may be related object)
        nested = True
        messages = [_normalize_validation_error(f, e) for f, e in errors.items()]
    else:  # must be list, just an error for some field
        for err in errors:
            if isinstance(err, dict):
                messages.append(
                    [_normalize_validation_error(f, e) for f, e in err.items()]
                )
            else:
                messages.append(str(err))

    normalized_errors["nested"] = nested
    normalized_errors["messages"] = messages
    return normalized_errors


def exception_handler(exc, context):
    if isinstance(exc, OnTimeException):
        return Response(exc.serialize(), status=exc.status_code)

    response = default_exception_handler(exc, context)

    try:
        error_data = {}
        error_data["type"] = get_exception_type(exc)
        error_data["status"] = str(response.status_code)

        if isinstance(exc, ValidationError):
            if isinstance(response.data, dict):  # when error is only for one object
                error_data["errors"] = [
                    _normalize_validation_error(field_name, errors)
                    for field_name, errors in response.data.items()
                ]

            elif isinstance(response.data, list):  # when error is for multiple objects
                error_data["errors"] = []

                for object_error in response.data:
                    error_data["errors"].append(
                        [
                            _normalize_validation_error(field_name, errors)
                            for field_name, errors in object_error.items()
                        ]
                    )

            error_data["human"] = msg.DATA_IS_EMPTY_OR_INVALID

        elif "detail" in response.data:
            error_data["human"] = response.data["detail"]

        response.data = error_data
        if isinstance(exc, AuthenticationFailed):
            # Return JsonResponse instead of DRF's Response object
            response = JsonResponse(response.data, status=response.status_code)

    finally:  # return the default response if any exception raised during handling
        return response


def smart_slugify(text, lang_code=None):
    if lang_code and lang_code.lower() in ["ru", "ru-ru", "rus"]:
        return slugify_ru(text, to_lower=True)
    return slugify(text)  # default django slugify


def get_expanded_fields(fields, translation_fields):
    expanded_fields = []
    languages = [lang_code for lang_code, _ in settings.LANGUAGES]

    for field in fields:
        if field in translation_fields:
            expanded_fields += ["%s_%s" % (field, lang_code) for lang_code in languages]
        else:
            expanded_fields.append(field)

    return expanded_fields


def get_expanded_extra_kwargs(extra_kwargs, translation_fields):
    expanded_extra_kwargs = {}
    languages = [lang_code for lang_code, _ in settings.LANGUAGES]
    required_languages = settings.ADMIN_REQUIRED_TRANSLATION_LANGUAGES

    for field, kwargs in extra_kwargs.items():
        if field in translation_fields:
            for lang_code in languages:
                required = (
                    kwargs.get("required") == True and lang_code in required_languages
                )
                _kwargs = kwargs.copy()
                _kwargs.update(
                    {
                        "required": required,
                        "allow_blank": not required,
                        "allow_null": not required,
                    }
                )
                expanded_extra_kwargs["%s_%s" % (field, lang_code)] = _kwargs
        else:
            expanded_extra_kwargs[field] = kwargs

    return expanded_extra_kwargs


def get_redis_client(connection_pool=None):
    return redis.StrictRedis(
        connection_pool=connection_pool or settings.REDIS_CONNECTION
    )


def copy_func(func):
    """Copies func."""
    g = types.FunctionType(
        func.__code__,
        func.__globals__,
        name=func.__name__,
        argdefs=func.__defaults__,
        closure=func.__closure__,
    )
    g = functools.update_wrapper(g, func)
    g.__kwdefaults__ = func.__kwdefaults__
    return g


class FakeRequest:
    def build_absolute_uri(self, path):
        return os.path.join("https://core.ontime.az", path.lstrip("/"))


def fix_rich_text_image_url(request, text):
    if not text:
        return ""
    return text.replace(
        '"/media', '"' + request.build_absolute_uri(settings.MEDIA_URL).rstrip("/")
    )
