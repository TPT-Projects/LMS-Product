"""Settings shared by every environment. Values come from environment variables only."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")

INSTALLED_APPS = [
    "daphne",  # ASGI runserver: serves the WebSocket endpoint in development too
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "channels",
    # Local
    "apps.tenants",
    "apps.accounts",
    "apps.teams",
    "apps.statuses",
    "apps.contacts",
    "apps.enquiries",
    "apps.customfields",
    "apps.views",
    "apps.audit",
    "apps.notifications",
    "apps.importexport",
    "apps.meta_integration",
    "apps.integrations",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "common.tenancy.middleware.TenantContextMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Databases -------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        # Every request runs in one transaction, so the tenant set with
        # `set_config('app.tenant_id', ..., is_local=true)` can never leak
        # into another request on a reused connection.
        "ATOMIC_REQUESTS": True,
        "CONN_MAX_AGE": 60,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MONGO_URI = env("MONGO_URI")
MONGO_DB_NAME = env("MONGO_DB_NAME", default="lms")

# Leave REDIS_URL empty to run without Redis (local development): background jobs then run
# inline and live updates only reach browsers connected to the same server process.
REDIS_URL = env("REDIS_URL", default="")

# --- Auth ------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = 60 * 60  # 1 hour
INVITATION_TTL_DAYS = 7

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["common.tenancy.authentication.TenantJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["common.tenancy.permissions.IsTenantMember"],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "login": "10/min",
        "password_reset": "5/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_MINUTES", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# --- Channels / Celery -----------------------------------------------------
CHANNEL_LAYERS = {
    "default": (
        {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}
        if REDIS_URL
        else {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    )
}
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = None  # results are stored on our own models (e.g. ImportJob)
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=not REDIS_URL)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BEAT_SCHEDULE = {
    # Re-check recent leads of connected forms so a missed webhook is recovered (spec F2).
    "meta-backfill": {"task": "apps.meta_integration.tasks.backfill_all", "schedule": 15 * 60},
    # Due auto-calls, new Meta leads, Google Sheets rows, daily Exotel number refresh.
    "integrations-heartbeat": {"task": "apps.integrations.tasks.heartbeat_all", "schedule": 60},
}

# --- Meta (Facebook / Instagram lead ads) -------------------------------------------
META_APP_ID = env("META_APP_ID", default="")
META_APP_SECRET = env("META_APP_SECRET", default="")
META_WEBHOOK_VERIFY_TOKEN = env("META_WEBHOOK_VERIFY_TOKEN", default="")
META_GRAPH_VERSION = env("META_GRAPH_VERSION", default="") or "v21.0"

# WhatsApp Embedded Signup (the Make.com-style flow): Meta app > Facebook Login for Business >
# Configurations > create one with the "WhatsApp Embedded Signup" variation; paste its ID here.
META_WHATSAPP_CONFIG_ID = env("META_WHATSAPP_CONFIG_ID", default="")

# Google Sheets app (console.cloud.google.com > APIs & Services > Credentials > OAuth client).
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
# Public address of this API (used for the Facebook login return URL).
BACKEND_URL = env("BACKEND_URL", default="http://localhost:8000")
# Google returns its login popup here (add it as an authorised redirect URI in Google Cloud).
GOOGLE_OAUTH_REDIRECT_URI = env("GOOGLE_OAUTH_REDIRECT_URI", default="") or (
    f"{BACKEND_URL.rstrip('/')}/api/integrations/google/callback/"
)
# Facebook returns the login popup here; the backend finishes the login and closes the popup.
# Must match a "Valid OAuth Redirect URI" in the Meta app exactly.
META_OAUTH_REDIRECT_URI = env("META_OAUTH_REDIRECT_URI", default="") or (
    f"{BACKEND_URL.rstrip('/')}/api/meta/callback/"
)
META_OAUTH_SCOPES = [
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_metadata",  # subscribe the Page to lead webhooks
    "leads_retrieval",
    "pages_manage_ads",  # list a Page's Instant Forms (leadgen_forms)
    "business_management",  # list Pages owned through a Business Manager
    "ads_read",  # campaign, ad set and ad names on each lead
]
# Encrypts Meta tokens at rest. Generate with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", default="")
CELERY_TASK_ACKS_LATE = True
CELERY_TIMEZONE = "UTC"

# --- Email -----------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="LMS <no-reply@localhost>")
# No SMTP host configured -> emails (invites, password resets) print in the API console.
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)

# --- i18n / time -----------------------------------------------------------
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"  # always store UTC; convert to the workspace timezone for display
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Files (attachments) -------------------------------------------------------
# S3-compatible storage when S3_BUCKET is set, local disk otherwise (development).
# Files are never public: downloads go through a permission-checked endpoint
# that streams the file (local) or redirects to a short-lived signed URL (S3).
MEDIA_ROOT = BASE_DIR / "media"
S3_BUCKET = env("S3_BUCKET", default="")
if S3_BUCKET:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": S3_BUCKET,
                "endpoint_url": env("S3_ENDPOINT", default="") or None,
                "access_key": env("S3_ACCESS_KEY", default=""),
                "secret_key": env("S3_SECRET_KEY", default=""),
                "region_name": env("S3_REGION", default="") or None,
                "default_acl": "private",
                "querystring_auth": True,
                "querystring_expire": 300,
                "file_overwrite": False,
            },
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
ATTACHMENT_MAX_BYTES = env.int("ATTACHMENT_MAX_BYTES", default=10 * 1024 * 1024)
ATTACHMENT_ALLOWED_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
    "text/csv",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]
VOICE_NOTE_MAX_BYTES = env.int("VOICE_NOTE_MAX_BYTES", default=10 * 1024 * 1024)
VOICE_NOTE_MAX_SECONDS = 10 * 60
VOICE_NOTE_ALLOWED_TYPES = [
    "audio/webm",  # Chrome, Edge, Firefox
    "audio/ogg",
    "audio/mp4",  # Safari
    "audio/mpeg",
    "audio/wav",
    "audio/x-m4a",
    "video/webm",  # some browsers label audio-only WebM this way
]
IMPORT_MAX_BYTES = env.int("IMPORT_MAX_BYTES", default=20 * 1024 * 1024)
IMPORT_MAX_ROWS = env.int("IMPORT_MAX_ROWS", default=50_000)
IMPORT_LIVE_LIMIT = 100  # spec: up to 100 rows run live, more run in the background
DATA_UPLOAD_MAX_MEMORY_SIZE = max(ATTACHMENT_MAX_BYTES, IMPORT_MAX_BYTES) + 1024 * 1024

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
