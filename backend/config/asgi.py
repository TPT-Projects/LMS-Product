import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import OriginValidator  # noqa: E402
from django.conf import settings  # noqa: E402
from django.urls import path  # noqa: E402

from common.consumers import TenantConsumer  # noqa: E402

websocket_urlpatterns = [path("ws/tenant/", TenantConsumer.as_asgi())]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Only the frontend's origins may open a socket (same list as CORS).
        "websocket": OriginValidator(
            URLRouter(websocket_urlpatterns),
            ["*"] if settings.DEBUG else settings.CORS_ALLOWED_ORIGINS,
        ),
    }
)
