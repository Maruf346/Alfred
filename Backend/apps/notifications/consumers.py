"""
notifications/consumers.py

WebSocket consumer for real-time notification delivery to platform
administrators.

Regular app users receive notifications through REST polling and do not use
this socket.

Connection:
    ws://host/ws/notifications/?token=<access_token>

Incoming client actions:
    { "action": "mark_read", "notification_id": "<uuid>" }
    { "action": "ping" }

Outgoing server events:
    { "type": "connection_established", "user_id": "...", "message": "..." }
    { "type": "notification", "notification_type": "...", "title": "...", ... }
    { "type": "mark_read_response", "notification_id": "...", "success": true }
    { "type": "pong" }
"""

import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer used by the admin dashboard.

    On connect:
    1. Extract the JWT from the query string.
    2. Validate the token and load the user.
    3. Reject non-admin connections with close code `4003`.
    4. Join the user-specific channel group: `user_<uuid>`.
    """

    async def connect(self):
        token = self._extract_token()
        self.user = await self._get_user_from_token(token)

        if not self.user or isinstance(self.user, AnonymousUser):
            logger.warning("WebSocket rejected due to unauthenticated connection attempt.")
            await self.close(code=4001)
            return

        if not await self._is_admin(self.user):
            logger.warning(
                "WebSocket rejected because non-admin user %s attempted connection.",
                self.user.email,
            )
            await self.close(code=4003)
            return

        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info("Admin WebSocket connected: %s", self.user.email)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection_established",
                    "message": "Connected to Alfred AI notification service",
                    "user_id": str(self.user.id),
                }
            )
        )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            logger.info(
                "Admin WebSocket disconnected: %s (code=%s)",
                getattr(self, "user", {}).email if hasattr(self, "user") else "unknown",
                close_code,
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.warning("WebSocket received invalid JSON and ignored it.")
            return

        action = data.get("action")

        if action == "mark_read":
            notification_id = data.get("notification_id")
            if notification_id:
                success = await self._mark_notification_read(notification_id)
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "mark_read_response",
                            "notification_id": notification_id,
                            "success": success,
                        }
                    )
                )
        elif action == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))
        else:
            logger.debug("Unknown WebSocket action received: %s", action)

    async def notification_message(self, event):
        """
        Forward a notification event from the channel layer to the connected
        WebSocket client.
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "notification",
                    "notification_id": event.get("notification_id"),
                    "notification_type": event.get("notification_type"),
                    "title": event["title"],
                    "body": event["body"],
                    "data": event.get("data", {}),
                    "priority": event.get("priority", "normal"),
                    "timestamp": event.get("timestamp"),
                }
            )
        )

    def _extract_token(self) -> str:
        """Parse the JWT from `?token=<value>` in the WebSocket query string."""
        qs = self.scope.get("query_string", b"").decode()
        for part in qs.split("&"):
            if part.startswith("token="):
                return part[len("token=") :]
        return ""

    @database_sync_to_async
    def _get_user_from_token(self, token: str):
        """Validate the JWT and return the authenticated user if valid."""
        if not token:
            return AnonymousUser()
        try:
            UntypedToken(token)
            from rest_framework_simplejwt.authentication import JWTAuthentication

            jwt_auth = JWTAuthentication()
            validated = jwt_auth.get_validated_token(token)
            return jwt_auth.get_user(validated)
        except (InvalidToken, TokenError):
            return AnonymousUser()

    @database_sync_to_async
    def _is_admin(self, user) -> bool:
        """Return True when the authenticated user is a platform administrator."""
        return getattr(user, "is_staff", False) and getattr(user, "is_superuser", False)

    @database_sync_to_async
    def _mark_notification_read(self, notification_id: str) -> bool:
        """Mark a notification as read for the connected admin user."""
        from django.utils import timezone

        from .models import Notification

        try:
            notification = Notification.objects.get(id=notification_id, user=self.user)
            if not notification.is_read:
                notification.is_read = True
                notification.read_at = timezone.now()
                notification.save(update_fields=["is_read", "read_at"])
            return True
        except Notification.DoesNotExist:
            return False
