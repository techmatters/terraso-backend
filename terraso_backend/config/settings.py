import os

import django
import structlog
from dj_database_url import parse as parse_db_url
from django.utils.encoding import force_str
from prettyconf import config

# Monkey patching force_text function to make the application work with Django
# 4.0. This is necessary until graphene-django fully supports the new Django
# version. This will probably be necessary until the following PR be merged.
# https://github.com/graphql-python/graphene-django/pull/1275
django.utils.encoding.force_text = force_str

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(os.path.abspath(BASE_DIR))

DEBUG = config("DEBUG", default=False, cast=config.boolean)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=config.list)
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS", default="https://*.terraso.org", cast=config.list
)

SECRET_KEY = config("SECRET_KEY")

SILENCED_SYSTEM_CHECKS = ["auth.W004"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "oauth2_provider",
    "corsheaders",
    "graphene_django",
    "rules",
    "storages",
    "safedelete",
    "apps.core",
    "apps.graphql",
    "apps.auth",
    "apps.shared_data",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.auth.middleware.JWTAuthenticationMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
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

WSGI_APPLICATION = "config.wsgi.application"

default_dburl = "sqlite:///" + os.path.join(BASE_DIR, "db.sqlite3")
DATABASES = {
    "default": config("DATABASE_URL", default=default_dburl, cast=parse_db_url),
}

AUTHENTICATION_BACKENDS = (
    "rules.permissions.ObjectPermissionBackend",
    "django.contrib.auth.backends.ModelBackend",
)

SAFE_DELETE_FIELD_NAME = "deleted_at"

AUTH_USER_MODEL = "core.User"

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

OAUTH2_PROVIDER = {
    "OIDC_ENABLED": True,
    "SCOPES": {
        "email": "User's email scope",
        "openid": "OpenID Connect scope",
        "profile": "User's information scope",
    },
    "OAUTH2_VALIDATOR_CLASS": "apps.auth.provider.oauth_validator.TerrasoOAuth2Validator",
    "OIDC_RSA_PRIVATE_KEY": config("OAUTH_OIDC_KEY", default="").replace("\\n", "\n"),
    "PKCE_REQUIRED": False,
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

MEDIA_URL = "/media/"
STATIC_URL = "/static/"

# don't allow "new" as a name, as the view route conflicts with the create route
DISALLOWED_NAMES_LIST = ["new"]

if not DEBUG:
    CDN_STATIC_DOMAIN = config("CDN_STATIC_DOMAIN")
    AWS_S3_CUSTOM_DOMAIN = CDN_STATIC_DOMAIN
    AWS_STORAGE_BUCKET_NAME = CDN_STATIC_DOMAIN
    STATIC_URL = f"{CDN_STATIC_DOMAIN}/"
    STATICFILES_STORAGE = "storages.backends.s3boto3.S3StaticStorage"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_formatter": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
        "plain_console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json_formatter",
        },
    },
    "loggers": {
        "": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django": {
            "handlers": ["console"],
            "level": "ERROR",
        },
    },
}

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    context_class=structlog.threadlocal.wrap_dict(dict),
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

GRAPHENE = {
    "SCHEMA": "apps.graphql.schema.schema",
}

WEB_CLIENT_URL = config("WEB_CLIENT_ENDPOINT", default="")
LOGIN_URL = f"{WEB_CLIENT_URL}/account"
AUTH_COOKIE_DOMAIN = config("AUTH_COOKIE_DOMAIN", default="")
CORS_ORIGIN_WHITELIST = config("CORS_ORIGIN_WHITELIST", default=[], cast=config.list)

AIRTABLE_API_KEY = config("AIRTABLE_API_KEY", default="")

GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default="")
GOOGLE_AUTH_REDIRECT_URI = config("GOOGLE_AUTH_REDIRECT_URI", default="")

APPLE_KEY_ID = config("APPLE_KEY_ID", default="")
APPLE_TEAM_ID = config("APPLE_TEAM_ID", default="")
APPLE_PRIVATE_KEY = config("APPLE_PRIVATE_KEY", default="").replace("\\n", "\n")
APPLE_CLIENT_ID = config("APPLE_CLIENT_ID", default="")
APPLE_AUTH_REDIRECT_URI = config("APPLE_AUTH_REDIRECT_URI", default="")

JWT_SECRET = config("JWT_SECRET")
JWT_ALGORITHM = config("JWT_ALGORITHM", default="HS512")
JWT_ACCESS_EXP_DELTA_SECONDS = config(
    "JWT_ACCESS_EXP_DELTA_SECONDS", default="360", cast=config.eval
)
JWT_REFRESH_EXP_DELTA_SECONDS = config(
    "JWT_REFRESH_EXP_DELTA_SECONDS", default="3600", cast=config.eval
)
JWT_ISS = config("JWT_ISS", default="https://terraso.org")

PROFILE_IMAGES_S3_BUCKET = config("PROFILE_IMAGES_S3_BUCKET", default="")
PROFILE_IMAGES_BASE_URL = config("PROFILE_IMAGES_BASE_URL", default="")

DATA_ENTRY_FILE_S3_BUCKET = config("DATA_ENTRY_FILE_S3_BUCKET", default="")
DATA_ENTRY_FILE_BASE_URL = config("DATA_ENTRY_FILE_BASE_URL", default="")

AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="us-east-2")
