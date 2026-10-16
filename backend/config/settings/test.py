from .base import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MONGO_DB_NAME = "lms_test"
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CELERY_TASK_ALWAYS_EAGER = True
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"login": "1000/min", "password_reset": "1000/min"},
}
FIELD_ENCRYPTION_KEY = (
    "dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktMTIzNDU="  # test only (32 bytes, base64)
)
