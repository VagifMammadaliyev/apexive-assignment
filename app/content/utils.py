from django.utils import translation
from django.conf import settings

from ontime.utils import smart_slugify


def slugify_translated_fields(instance, field_name, slug_field_name="slug"):
    for lang_code, _ in settings.LANGUAGES:
        with translation.override(lang_code):
            setattr(
                instance,
                "%s_%s" % (slug_field_name, lang_code),
                smart_slugify(getattr(instance, field_name), lang_code=lang_code),
            )
