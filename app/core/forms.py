from django import forms
from django.contrib.admin.forms import (
    AuthenticationForm,
)
from django.conf import settings

from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV3


class AuthFormWithCaptcha(AuthenticationForm):
    captcha = ReCaptchaField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        recaptcha_widget = ReCaptchaV3(
            attrs={"data-sitekey": settings.RECAPTCHA_PUBLIC_KEY}
        )
        self.fields["captcha"].widget = recaptcha_widget
