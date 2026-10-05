"""
ASGI config for the Alfred backend.

HTTP requests are handled by Django's ASGI application.
WebSocket requests are routed through Django Channels.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

django_asgi_app = get_asgi_application()

from apps.notifications.routing import websocket_urlpatterns as notification_ws

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(notification_ws)
        ),
    }
)
