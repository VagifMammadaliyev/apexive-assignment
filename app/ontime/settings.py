import ssl
import os
from datetime import timedelta

import redis
import sentry_sdk
from corsheaders.defaults import default_headers
from sentry_sdk.integrations.django import DjangoIntegration


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = "d!73u$_w_+epro2=i6_4!zy%9h$t3(b+8=_i6#(j+3x&(0m(*2"

DEBUG = os.environ.get("DEBUG", "True") == "True"
PROD = not DEBUG
DEVELOPMENT = os.environ.get("DEVELOPMENT", "False") == "True"

if DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [
        "core.ontime.az",
        "ontime.az",
        "www.ontime.az",
        "dev.ontime.az",
        "dev-cp.ontime.az",
        "dev-core.ontime.az",
    ]

AUTH_USER_MODEL = "customer.User"

INSTALLED_APPS = [
    "grappelli",
    "modeltranslation",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "knox",
    "rosetta",
    "ckeditor",
    "captcha",
    "defender",
    "ckeditor_uploader",
    "admin_auto_filters",
    "django_rest_resetpassword",
    "customer.apps.CustomerConfig",  # signals don't work otherwise :(
    "core",
    "fulfillment.apps.FulfillmentConfig",
    "content",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "domain.middleware.AdminLocaleMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    # "django.middleware.csrf.CsrfViewMiddleware",
    "domain.middleware.country_timezone_middleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "defender.middleware.FailedLoginMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ontime.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ontime.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get("POSTGRES_DB", "ontime_db"),
        "USER": os.environ.get("POSTGRES_USER", "ontime_user"),
        "PASSWORD": os.environ.get(
            "POSTGRES_PASSWORD",
            "b7RPc6dBk7Bxmf6fVldHG0Wek2vLVKOaqdY5kB4wZneKU8riQP4oR2wYcj2T2xEw",
        ),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5433"),
    }
}


if PROD:
    DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
    "DEFAULT_AUTHENTICATION_CLASSES": ("knox.auth.TokenAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": (
        "djangorestframework_camel_case.render.CamelCaseJSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "djangorestframework_camel_case.parser.CamelCaseFormParser",
        "djangorestframework_camel_case.parser.CamelCaseMultiPartParser",
        "djangorestframework_camel_case.parser.CamelCaseJSONParser",
    ),
    "JSON_UNDERSCOREIZE": {
        "no_underscore_before_number": True,
    },
    "EXCEPTION_HANDLER": "ontime.utils.exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "45/min",
        "user": "60/min",
        "hardcore": "8/min",
        "hard": "15/min",
        "easy": "18/min",
        "light": "25/min",
    },
}

REST_KNOX = {
    "TOKEN_TTL": timedelta(hours=24 * 30),
}

LANGUAGE_CODE = "az"

LANGUAGES = (
    (
        "az",
        "Azərbaycanca",
    ),
    (
        "ru",
        "Русский",
    ),
    ("en", "English"),
)

TIME_ZONE = "Asia/Baku"

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = "/static/"

STATIC_ROOT = os.path.join(BASE_DIR, "static")

MEDIA_URL = "/media/"

MEDIA_ROOT = os.path.join(BASE_DIR, "media")

LOCALE_PATHS = [os.path.join(BASE_DIR, "locale")]

EMAIL_HOST = "smtp.yandex.ru"
EMAIL_PORT = 465
EMAIL_HOST_USER = "support@ontime.az"
EMAIL_HOST_PASSWORD = "Support2950000"
EMAIL_USE_SSL = True
EMAIL_USE_TLS = False
DEFAULT_FROM_EMAIL = "Ontime.az <%s>" % "support@ontime.az"

# TODO: This is not poctgoyercin anymore, change it later!
POCTGOYERCIN_URL = "http://api.msm.az/sendsms"
POCTGOYERCIN_USER = "ontimeazapi"
POCTGOYERCIN_PASSWORD = "NqwFADbb"
POCTGOYERCIN_SENDER_NAME = "ONTIME.AZ"

REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", "6380")
_redis_protocol = "rediss" if PROD else "redis"
REDIS_CONNECTION_STRING = "{protocol}://:{password}@{host}:{port}/0".format(
    password=REDIS_PASSWORD, host=REDIS_HOST, port=REDIS_PORT, protocol=_redis_protocol
)
REDIS_CONNECTION = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    **(
        {"ssl_cert_reqs": ssl.CERT_REQUIRED, "connection_class": redis.SSLConnection}
        if PROD
        else {}
    )
)

CELERY_BROKER_URL = REDIS_CONNECTION_STRING
if PROD:
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

CELERY_TASK_IGNORE_RESULT = True

CELERY_TIMEZONE = "UTC"

if DEBUG:
    CORS_ORIGIN_ALLOW_ALL = True
else:
    CORS_ORIGIN_WHITELIST = [
        "https://www.ontime.az",
        "https://ontime.az",
        "https://cp.ontime.az",
        "http://cp.ontime.az",
        "https://dev.ontime.az",  # FIXME: Remove this origin later
        "http://ontime.global",
        "https://ontime.global",
    ]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = list(default_headers) + ["accept-language"]

GRAPPELLI_ADMIN_TITLE = "Ontime"
CKEDITOR_UPLOAD_PATH = "ckeditor/uploads/"
CKEDITOR_MEDIA_USE_FULL_URL = True
CKEDITOR_CONFIGS = {
    "default": {
        # 'skin': 'office2013',
        "toolbar_Basic": [["Source", "-", "Bold", "Italic"]],
        "toolbar_YourCustomToolbarConfig": [
            {
                "name": "document",
                "items": [
                    "Source",
                    "-",
                    "Save",
                    "NewPage",
                    "Preview",
                    "Print",
                    "-",
                    "Templates",
                ],
            },
            {
                "name": "clipboard",
                "items": [
                    "Cut",
                    "Copy",
                    "Paste",
                    "PasteText",
                    "PasteFromWord",
                    "-",
                    "Undo",
                    "Redo",
                ],
            },
            {"name": "editing", "items": ["Find", "Replace", "-", "SelectAll"]},
            {
                "name": "forms",
                "items": [
                    "Form",
                    "Checkbox",
                    "Radio",
                    "TextField",
                    "Textarea",
                    "Select",
                    "Button",
                    "ImageButton",
                    "HiddenField",
                ],
            },
            "/",
            {
                "name": "basicstyles",
                "items": [
                    "Bold",
                    "Italic",
                    "Underline",
                    "Strike",
                    "Subscript",
                    "Superscript",
                    "-",
                    "RemoveFormat",
                ],
            },
            {
                "name": "paragraph",
                "items": [
                    "NumberedList",
                    "BulletedList",
                    "-",
                    "Outdent",
                    "Indent",
                    "-",
                    "Blockquote",
                    "CreateDiv",
                    "-",
                    "JustifyLeft",
                    "JustifyCenter",
                    "JustifyRight",
                    "JustifyBlock",
                    "-",
                    "BidiLtr",
                    "BidiRtl",
                    "Language",
                ],
            },
            {"name": "links", "items": ["Link", "Unlink", "Anchor"]},
            {
                "name": "insert",
                "items": [
                    "Image",
                    "Flash",
                    "Table",
                    "HorizontalRule",
                    "Smiley",
                    "SpecialChar",
                    "PageBreak",
                    "Iframe",
                ],
            },
            "/",
            {"name": "styles", "items": ["Styles", "Format", "Font", "FontSize"]},
            {"name": "colors", "items": ["TextColor", "BGColor"]},
            {"name": "tools", "items": ["Maximize", "ShowBlocks"]},
            {"name": "about", "items": ["About"]},
            "/",  # put this to force next toolbar on new line
            {
                "name": "yourcustomtools",
                "items": [
                    # put the name of your editor.ui.addButton here
                    "Preview",
                    "Maximize",
                ],
            },
        ],
        "toolbar": "YourCustomToolbarConfig",  # put selected toolbar config here
        # 'toolbarGroups': [{ 'name': 'document', 'groups': [ 'mode', 'document', 'doctools' ] }],
        # 'height': 291,
        # 'width': '100%',
        # 'filebrowserWindowHeight': 725,
        # 'filebrowserWindowWidth': 940,
        # 'toolbarCanCollapse': True,
        # 'mathJaxLib': '//cdn.mathjax.org/mathjax/2.2-latest/MathJax.js?config=TeX-AMS_HTML',
        "tabSpaces": 4,
        "extraPlugins": ",".join(
            [
                "uploadimage",  # the upload image feature
                # your extra plugins here
                "div",
                "autolink",
                "autoembed",
                "embedsemantic",
                "autogrow",
                # 'devtools',
                "widget",
                "lineutils",
                "clipboard",
                "dialog",
                "dialogui",
                "elementspath",
            ]
        ),
    }
}


DJANGO_REST_MULTITOKENAUTH_RESET_TOKEN_EXPIRY_TIME = 3
DJANGO_REST_RESETPASSWORD_NO_INFORMATION_LEAKAGE = True

# ====================
# Application settings
# ====================

ADMIN_REQUIRED_TRANSLATION_LANGUAGES = ["az", "ru"]

USER_BALANCE_CURRENCY_CODE = "USD"


# Cybersource Secure acceptance settings
CYBERSOURCE_SECRET_KEY = os.environ.get(
    "CYBERSOURCE_SECRET_KEY",
    "985e2238e6874236a9b08eccb2d9a379c7800fbfa50e440fbc4851a61a930bb6d6d681756f534582822d3"
    "72809bdba124c0429c017ca4ecbaf309ef1fe0d9786d29ec3c43591450291547ac7d4d538c26292daa72f"
    "63451f9b1c4f3dbe27f90388e5705ba57f45bc9dbc492c1abf28b32a00055eba264c77ab10eb500b18fc8e",
)
CYBERSOURCE_ACCESS_KEY = os.environ.get(
    "CYBERSOURCE_ACCESS_KEY", "f6ad3286b1ab3cb29c79e076957c0f30"
)
CYBERSOURCE_PROFILE_ID = os.environ.get(
    "CYBERSOURCE_PROFILE_ID", "FD762FCB-9D5C-4ACA-8297-AC0F9BC84FB0"
)
CYBERSOURCE_URL = os.environ.get(
    "CYBERSOURCE_URL", "https://testsecureacceptance.cybersource.com/pay"
)
CYBERSOURCE_CURRENCY_CODE = os.environ.get("CYBERSOURCE_CURRENCY_CODE", "USD")


# Paypal related creds and variables
PAYPAL_CLIENT = os.environ.get(
    "PAYPAL_CLIENT",
    "AY_AEHaJIgFGVUjJMWLSxksBm94IRcqpUEnCV2lcNc-ZrM0ixgLO6ye_lwXvpDYJW8N7D9ukWls9cMXP",
)
PAYPAL_SECRET = os.environ.get(
    "PAYPAL_SECRET",
    "EDudMvYe_C_mXHyInvYZrsNT0FS8laZckrIAuRFYhGwrkDQk7gj0ESI4nzKpNhl5hsi-vLcpaScgWGYg",
)
PAYPAL_OAUTH_API = os.environ.get(
    "PAYPAL_OAUTH_API",
    "https://api.sandbox.paypal.com/v1/oauth2/token/",
)
PAYPAL_ORDER_API = os.environ.get(
    "PAYPAL_ORDER_API",
    "https://api.sandbox.paypal.com/v2/checkout/orders/",
)
PAYPAL_CURRENCY_CODE = os.environ.get("PAYPAL_CURRENCY_CODE", "USD")

PAYTR_MERCHANT_SECRET_ID = os.environ.get(
    "PAYTR_MERCHANT_SECRET_ID",
    "233972",
)
PAYTR_MERCHANT_KEY = os.environ.get(
    "PAYTR_MERCHANT_KEY",
    "PwCzpR8ZboNBJnED",
)
PAYTR_MERCHANT_SECRET_SALT = os.environ.get(
    "PAYTR_MERCHANT_SECRET_SALT",
    "6YApQuAZtF895k1F",
)

# Sentry
if PROD:
    sentry_sdk.init(
        dsn="https://274d5c9c440b4f35b49ca1cbe6991357@o446476.ingest.sentry.io/5691877",
        integrations=[DjangoIntegration()],
        send_default_pii=True,
    )

ONTIME_PROXY_URL = os.getenv("ONTIME_PROXY_URL", "http://207.154.197.120")
ONTIME_PROXY_TOKEN = os.getenv(
    "ONTIME_PROXY_TOKEN",
    (
        "4a66808ee9b24844468463668d4a77c90dc306e0f7e3b5acc0867fd9b6a0a49"
        "81e0ef232f039f4f484718e70498e25451aac353c1f5dd32b23542f6cc6e6a647"
    ),
)

if DEBUG:
    CUSTOMS_API_BASE_URL = "https://ecarrier-fbusiness.customs.gov.az:7540"
else:
    CUSTOMS_API_BASE_URL = "https://ecarrier-fbusiness.customs.gov.az:7545"
CUSTOMS_API_TOKEN = os.getenv(
    "ONTIME_CUSTOMS_API_TOKEN", "C18F5523BE5BE201031A894EC2C27626041AAAF1"
)

RECAPTCHA_PUBLIC_KEY = os.getenv(
    "RECAPTHCA_PUBLIC_KEY", "6Ld1xVsaAAAAAH56W2MpIV8sC_3rWlG6jAvQQMOx"
)
RECAPTCHA_PRIVATE_KEY = os.getenv(
    "RECAPTHCA_PRIVATE_KEY", "6Ld1xVsaAAAAAKzgDgUH8oJ0wws06IpuKhzYGax0"
)

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_CONNECTION_STRING,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "django_cache",
    }
}

DEFENDER_LOGIN_FAILURE_LIMIT = 5
DEFENDER_BEHIND_REVERSE_PROXY = True
DEFENDER_USERNAME_FORM_FIELDS = ["username"]
DEFENDER_REDIS_NAME = "default"
DEFENDER_DISABLE_IP_LOCKOUT = True
DEFENDER_GET_USERNAME_FROM_REQUEST_PATH = "core.utils.security.username_from_request"
