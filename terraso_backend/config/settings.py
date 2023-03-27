# Copyright © 2021-2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.
import base64
import os

import django
import structlog
from dj_database_url import parse as parse_db_url
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _
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
    "apps.story_map",
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
    "django.middleware.locale.LocaleMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "DIRS": [
            os.path.join(BASE_DIR, "custom_templates"),
            os.path.join(BASE_DIR, "apps", "notifications", "templates"),
        ],
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.restore_allowed",
            ],
        },
    },
]

LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

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
    # for some reason I cannot figure out, the .well-known/openid-configuration
    # endpoints always use http:// schema
    # easiest way to force https:// is to provide this explicitly
    "OIDC_ISS_ENDPOINT": config("OIDC_ISS_ENDPOINT", default="https://api.terraso.org/oauth/"),
    "PKCE_REQUIRED": False,
    "REQUEST_APPROVAL_PROMPT": "auto",
}

LANGUAGE_CODE = "en-us"
LANGUAGES = [
    ("es", _("Spanish")),
    ("en", _("English")),
]

TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

MEDIA_URL = "/media/"
STATIC_URL = "/static/"

EMAIL_FROM_NAME = config("EMAIL_FROM_NAME", default="Terraso")
EMAIL_FROM_ADDRESS = config("EMAIL_FROM_ADDRESS", default="info@terraso.org")

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
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

GRAPHENE = {
    "SCHEMA": "apps.graphql.schema.schema",
    "TESTING_ENDPOINT": "/graphql/",
}

WEB_CLIENT_URL = config("WEB_CLIENT_ENDPOINT", default="")
LOGIN_URL = f"{WEB_CLIENT_URL}/account"
AUTH_COOKIE_DOMAIN = config("AUTH_COOKIE_DOMAIN", default="")
CORS_ORIGIN_WHITELIST = config("CORS_ORIGIN_WHITELIST", default=[], cast=config.list)

API_ENDPOINT = config("API_ENDPOINT", default="")

AIRTABLE_API_KEY = config("AIRTABLE_API_KEY", default="")

GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET", default="")

APPLE_KEY_ID = config("APPLE_KEY_ID", default="")
APPLE_TEAM_ID = config("APPLE_TEAM_ID", default="")
APPLE_PRIVATE_KEY = config("APPLE_PRIVATE_KEY", default="").replace("\\n", "\n")
APPLE_CLIENT_ID = config("APPLE_CLIENT_ID", default="")

MICROSOFT_CLIENT_ID = config("MICROSOFT_CLIENT_ID", default="")
MICROSOFT_CLIENT_SECRET = config("MICROSOFT_CLIENT_SECRET", default="")
MICROSOFT_PRIVATE_KEY = config("MICROSOFT_PRIVATE_KEY", default="").strip()
MICROSOFT_CERTIFICATE_THUMBPRINT = base64.b64encode(
    bytes.fromhex(config("MICROSOFT_CERTIFICATE_THUMBPRINT", default="").strip())
).decode("utf-8")

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
PROFILE_IMAGES_BASE_URL = f"https://{PROFILE_IMAGES_S3_BUCKET}"

DATA_ENTRY_FILE_S3_BUCKET = config("DATA_ENTRY_FILE_S3_BUCKET", default="")
DATA_ENTRY_FILE_BASE_URL = f"https://{DATA_ENTRY_FILE_S3_BUCKET}"

# If types defined as None, then types are guessed from the file extension

DATA_ENTRY_DOCUMENT_TYPES = {
    ".doc": None,
    ".docx": None,
    ".pdf": None,
    ".ppt": None,
    ".pptx": None,
}

DATA_ENTRY_SPREADSHEET_TYPES = {
    ".csv": ["text/plain", "text/csv", "application/csv"],
    ".xls": None,
    ".xlsx": None,
}

DATA_ENTRY_GIS_TYPES = {
    ".geojson": ["text/plain", "application/json", "application/geo+json"],
    ".json": ["text/plain", "application/json", "application/geo+json"],
    ".gpx": ["text/plain", "text/xml", "application/xml", "application/gpx+xml"],
    ".kml": ["text/plain", "text/xml", "application/xml", "application/vnd.google-earth.kml+xml"],
    ".kmz": ["application/zip", "application/vnd.google-earth.kmz"],
    ".zip": ["application/zip"],
}

DATA_ENTRY_ACCEPTED_TYPES = (
    DATA_ENTRY_DOCUMENT_TYPES | DATA_ENTRY_SPREADSHEET_TYPES | DATA_ENTRY_GIS_TYPES
)

DB_BACKUP_S3_BUCKET = config("DB_BACKUP_S3_BUCKET", default="")

# DB Restore config
ALLOW_RESTORE_FROM_BACKUP = config("ALLOW_RESTORE_FROM_BACKUP", default="false").lower() == "true"
DB_RESTORE_CONFIG_FILE = config("DB_RESTORE_CONFIG_FILE", default="")
# Render service ID
DB_RESTORE_SOURCE_ID = config("DB_RESTORE_SOURCE_ID", default="")
DB_RESTORE_SOURCE_HOST = config("DB_RESTORE_SOURCE_HOST", default="")
DB_RESTORE_DEST_HOST = config("DB_RESTORE_DEST_HOST", default="")

AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="us-east-2")

EMAIL_BACKEND = "django_ses.SESBackend"
AWS_SES_ACCESS_KEY_ID = config("AWS_SES_ACCESS_KEY_ID", default="")
AWS_SES_SECRET_ACCESS_KEY = config("AWS_SES_SECRET_ACCESS_KEY", default="")

PLAUSIBLE_URL = config("PLAUSIBLE_URL", default="https://plausible.io/api/event")
RENDER_API_URL = config("RENDER_API_URL", default="https://api.render.com/v1/")
RENDER_API_TOKEN = config("RENDER_API_TOKEN", default="")

DATA_UPLOAD_MAX_MEMORY_SIZE = 70000000  # 70MB

STORY_MAP_MEDIA_S3_BUCKET = config("STORY_MAP_MEDIA_S3_BUCKET", default="")
STORY_MAP_MEDIA_BASE_URL = f"https://{STORY_MAP_MEDIA_S3_BUCKET}"
