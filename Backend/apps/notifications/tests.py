from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from core.asgi import application

User = get_user_model()


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)
class NotificationWebSocketTests(TransactionTestCase):
    async def test_admin_can_connect_to_notification_socket(self):
        admin = await User.objects.acreate(
            email="admin-ws@example.com",
            full_name="Admin WS",
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        token = str(RefreshToken.for_user(admin).access_token)

        communicator = WebsocketCommunicator(
            application,
            f"/ws/notifications/?token={token}",
        )
        connected, _ = await communicator.connect()

        self.assertTrue(connected)
        message = await communicator.receive_json_from(timeout=2)
        self.assertEqual(message["type"], "connection_established")
        self.assertEqual(message["user_id"], str(admin.id))
        await communicator.disconnect()

    async def test_non_admin_cannot_connect_to_notification_socket(self):
        user = await User.objects.acreate(
            email="regular-ws@example.com",
            full_name="Regular WS",
            is_active=True,
        )
        token = str(RefreshToken.for_user(user).access_token)

        communicator = WebsocketCommunicator(
            application,
            f"/ws/notifications/?token={token}",
        )
        connected, _ = await communicator.connect()

        self.assertFalse(connected)
