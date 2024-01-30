"""Security related utilities"""
from io import BytesIO

from PIL import Image
from django.conf import settings
from django.core.exceptions import ValidationError
from upload_validator import FileTypeValidator


def username_from_request(request):
    """Tries to get username from request object."""
    possible_username_fields = settings.DEFENDER_USERNAME_FORM_FIELDS
    username_value = None
    for possible_username_field in possible_username_fields:
        username_value = request.POST.get(possible_username_field)
        if username_value:
            username_value = username_value[:255]
            break
    return username_value


_image_file_validator = FileTypeValidator(allowed_types=["image/*"])
user_input_file_validator = FileTypeValidator(
    allowed_types=["image/*", "application/pdf"]
)


def _check_if_image(in_memory_file):
    try:
        _image_file_validator(in_memory_file)
        return True
    except ValidationError:
        return False


def validate_input_file(in_memory_file, validator=None):
    """
    Accepts In-Memory file as an argument.
    If `validator` is not specified validates against valid images and PDF
    files by default. Additional validation on image types are being done if
    first step validation succeeds.
    Returns boolean.
    """
    if not validator:
        validator = user_input_file_validator
    try:
        validator(in_memory_file)
    except ValidationError as err:
        return False

    if _check_if_image(in_memory_file):
        try:
            _in_memory_image = in_memory_file.read()
            image_data = BytesIO(_in_memory_image)
            image = Image.open(image_data)
            image.verify()
        except Exception as exc:
            return False
    return True
