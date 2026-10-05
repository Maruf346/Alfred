from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai_gateway.client import AlfredAIError
from apps.users.models import SubscriptionPlan, User

from .models import ChatMessage, Conversation, MessageSender


class FakeAlfredClient:
    payloads = []

    def post_json(self, path, payload):
        self.payloads.append(payload)
        return {
            "reply": "What location and budget should I use?",
            "intent": "date_planning",
            "confidence": 0.95,
            "actions": [],
            "recommendations": [],
            "memory_updates": [],
            "session_id": "ai-session-123",
            "session_status": "new",
            "timeline": [],
            "estimated_cost": None,
            "tips": [],
        }

    def post_audio(self, path, payload):
        return b"fake-mp3", "audio/mpeg"


class FailingAlfredClient:
    def post_json(self, path, payload):
        raise AlfredAIError(
            "AI service rejected the request.",
            status_code=500,
            detail={"detail": "Upstream exploded"},
        )


class EchoAlfredClient:
    def post_json(self, path, payload):
        reply = f"Reply for {payload['message']}"
        return {
            "reply": reply,
            "intent": "general_chat",
            "confidence": 0.9,
            "actions": [],
            "recommendations": [],
            "memory_updates": [],
            "session_id": "ai-session-echo",
            "session_status": "active",
            "timeline": [],
            "estimated_cost": None,
            "tips": [],
        }

    def post_audio(self, path, payload):
        return f"audio::{payload['text']}".encode("utf-8"), "audio/mpeg"


class ExpiredSessionAlfredClient:
    def post_json(self, path, payload):
        return {
            "reply": "The previous conversation context was lost, but we can continue from here.",
            "intent": "general_chat",
            "confidence": 0.8,
            "actions": [],
            "recommendations": [],
            "memory_updates": [],
            "session_id": payload.get("session_id", "expired-session"),
            "session_status": "expired",
            "timeline": [],
            "estimated_cost": None,
            "tips": [],
        }

    def post_audio(self, path, payload):
        return b"expired-audio", "audio/mpeg"


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    ALFRED_AI_BASE_URL="http://ai.test",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class ChatAPITests(APITestCase):
    def setUp(self):
        FakeAlfredClient.payloads = []
        self.user = User.objects.create_user(
            email="chat@example.com",
            password="StrongPass123!",
            full_name="Chat User",
        )
        self.client.force_authenticate(self.user)

    @patch("apps.chat.services.AlfredAIClient", return_value=FakeAlfredClient())
    def test_chat_message_creates_conversation_and_messages(self, _client):
        response = self.client.post(
            reverse("chat-message-create"),
            {"message": "Plan a cozy date night", "mode": "chat"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["session_id"], "ai-session-123")
        self.assertEqual(response.data["data"]["session_status"], "new")
        self.assertEqual(response.data["data"]["voice_agent"], None)
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 2)
        self.assertEqual(ChatMessage.objects.filter(sender=MessageSender.USER).count(), 1)
        self.assertEqual(ChatMessage.objects.filter(sender=MessageSender.ASSISTANT).count(), 1)

    @patch("apps.chat.services.AlfredAIClient", return_value=FakeAlfredClient())
    def test_free_user_speak_uses_flutter_tts_without_audio(self, _client):
        response = self.client.post(
            reverse("chat-message-create"),
            {"message": "Say this back", "mode": "speak"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["voice_agent"], "flutter_tts")
        self.assertNotIn("audio_base64", response.data["data"])

    @patch("apps.chat.services.AlfredAIClient", return_value=FakeAlfredClient())
    def test_premium_user_speak_returns_multipart_audio(self, _client):
        self.user.subscription_plan = SubscriptionPlan.MONTHLY
        self.user.save(update_fields=["subscription_plan"])

        response = self.client.post(
            reverse("chat-message-create"),
            {"message": "Say this back", "mode": "speak"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response["Content-Type"].startswith("multipart/mixed"))
        self.assertIn(b'Content-Disposition: inline; name="data"', response.content)
        self.assertIn(b'Content-Type: application/json; charset=utf-8', response.content)
        self.assertIn(b'"voice_agent": "Alfred"', response.content)
        self.assertIn(b'Content-Disposition: attachment; name="audio"; filename="alfred-reply.mp3"', response.content)
        self.assertIn(b"Content-Type: audio/mpeg", response.content)
        self.assertIn(b"fake-mp3", response.content)

    @patch("apps.chat.services.AlfredAIClient", return_value=FakeAlfredClient())
    def test_cached_audio_chat_returns_json_audio_url_for_premium_user(self, _client):
        self.user.subscription_plan = SubscriptionPlan.MONTHLY
        self.user.save(update_fields=["subscription_plan"])

        response = self.client.post(
            reverse("chat-message-create-cached-audio"),
            {"message": "Say this back", "mode": "speak"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["voice_agent"], "Alfred")
        self.assertIsNotNone(response.data["data"]["audio_url"])
        self.assertEqual(response.data["data"]["audio_expires_in_seconds"], 3600)
        self.assertIn("/audio/?token=", response.data["data"]["audio_url"])

        audio_response = self.client.get(response.data["data"]["audio_url"])

        self.assertEqual(audio_response.status_code, status.HTTP_200_OK)
        self.assertEqual(audio_response["Content-Type"], "audio/mpeg")
        self.assertEqual(audio_response.content, b"fake-mp3")
        self.assertEqual(audio_response["X-Alfred-Message-Id"], response.data["data"]["message_id"])

    @patch("apps.chat.services.AlfredAIClient", return_value=EchoAlfredClient())
    def test_cached_audio_url_returns_audio_for_the_current_reply(self, _client):
        self.user.subscription_plan = SubscriptionPlan.MONTHLY
        self.user.save(update_fields=["subscription_plan"])

        first = self.client.post(
            reverse("chat-message-create-cached-audio"),
            {"message": "first request", "mode": "speak"},
            format="json",
        )
        second = self.client.post(
            reverse("chat-message-create-cached-audio"),
            {"message": "second request", "mode": "speak"},
            format="json",
        )

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertNotEqual(first.data["data"]["message_id"], second.data["data"]["message_id"])
        self.assertNotEqual(first.data["data"]["audio_url"], second.data["data"]["audio_url"])

        first_audio = self.client.get(first.data["data"]["audio_url"])
        second_audio = self.client.get(second.data["data"]["audio_url"])

        self.assertEqual(first_audio.content, b"audio::Reply for first request")
        self.assertEqual(second_audio.content, b"audio::Reply for second request")
        self.assertEqual(first_audio["X-Alfred-Message-Id"], first.data["data"]["message_id"])
        self.assertEqual(second_audio["X-Alfred-Message-Id"], second.data["data"]["message_id"])

    @patch("apps.chat.services.AlfredAIClient", return_value=FakeAlfredClient())
    def test_cached_audio_chat_returns_no_audio_url_for_free_user(self, _client):
        response = self.client.post(
            reverse("chat-message-create-cached-audio"),
            {"message": "Say this back", "mode": "speak"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["voice_agent"], "flutter_tts")
        self.assertIsNone(response.data["data"]["audio_url"])
        self.assertIsNone(response.data["data"]["audio_expires_in_seconds"])

    def test_cached_audio_endpoint_rejects_other_users_messages(self):
        other_user = User.objects.create_user(
            email="audio-other@example.com",
            password="StrongPass123!",
        )
        other_conversation = Conversation.objects.create(user=other_user, title="Other audio")
        other_message = ChatMessage.objects.create(
            conversation=other_conversation,
            sender=MessageSender.ASSISTANT,
            content="Private audio",
        )

        response = self.client.get(
            reverse("chat-message-audio", kwargs={"message_id": str(other_message.id)})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cached_audio_endpoint_requires_token(self):
        conversation = Conversation.objects.create(user=self.user, title="Needs token")
        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=MessageSender.ASSISTANT,
            content="Private audio",
        )

        response = self.client.get(
            reverse("chat-message-audio", kwargs={"message_id": str(message.id)})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.chat.services.AlfredAIClient", return_value=FakeAlfredClient())
    def test_continuing_conversation_reuses_stored_ai_session_id(self, _client):
        conversation = Conversation.objects.create(
            user=self.user,
            title="Existing date plan",
            ai_session_id="stored-ai-session",
            ai_session_last_seen_at=timezone.now(),
        )

        response = self.client.post(
            reverse("chat-message-create"),
            {
                "message": "The budget is 5000 BDT",
                "mode": "chat",
                "conversation_id": str(conversation.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(FakeAlfredClient.payloads[-1]["session_id"], "stored-ai-session")
        self.assertEqual(FakeAlfredClient.payloads[-1]["conversation_id"], str(conversation.id))

    @patch("apps.chat.services.AlfredAIClient", return_value=ExpiredSessionAlfredClient())
    def test_chat_response_passes_through_expired_session_status(self, _client):
        conversation = Conversation.objects.create(
            user=self.user,
            title="Expired AI session",
            ai_session_id="stored-but-expired-in-ai",
            ai_session_last_seen_at=timezone.now(),
        )

        response = self.client.post(
            reverse("chat-message-create"),
            {
                "message": "Continue this please",
                "mode": "chat",
                "conversation_id": str(conversation.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["session_id"], "stored-but-expired-in-ai")
        self.assertEqual(response.data["data"]["session_status"], "expired")

    @override_settings(DEBUG=True)
    @patch("apps.chat.services.AlfredAIClient", return_value=FailingAlfredClient())
    def test_ai_service_errors_return_gateway_failure_with_debug_detail(self, _client):
        response = self.client.post(
            reverse("chat-message-create"),
            {"message": "Plan a cozy date night", "mode": "chat"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["detail"], "AI service failed while generating a response.")
        self.assertEqual(response.data["ai_status_code"], 500)
        self.assertEqual(response.data["ai_error"], {"detail": "Upstream exploded"})

    def test_messages_endpoint_lists_user_and_alfred_messages(self):
        conversation = Conversation.objects.create(user=self.user, title="Inbox thread")
        user_message = ChatMessage.objects.create(
            conversation=conversation,
            sender=MessageSender.USER,
            content="Plan a quiet date",
        )
        alfred_message = ChatMessage.objects.create(
            conversation=conversation,
            sender=MessageSender.ASSISTANT,
            content="Of course. What budget should I keep in mind?",
        )

        response = self.client.get(
            reverse("chat-messages-list"),
            {"conversation_id": str(conversation.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(response.data["results"][0]["id"], str(alfred_message.id))
        self.assertEqual(response.data["results"][0]["sender"], "alfred")
        self.assertEqual(response.data["results"][0]["message"], "Of course. What budget should I keep in mind?")
        self.assertEqual(response.data["results"][1]["id"], str(user_message.id))
        self.assertEqual(response.data["results"][1]["sender"], "me")
        self.assertEqual(response.data["results"][1]["message"], "Plan a quiet date")
        self.assertNotIn("ai_response", response.data["results"][0])

    def test_message_detail_returns_full_ai_response_payload(self):
        conversation = Conversation.objects.create(user=self.user, title="Detail message")
        ai_payload = {
            "reply": "Here is a complete plan.",
            "intent": "date_planning",
            "confidence": 0.91,
            "actions": [{"action": "suggest_transport", "payload": {"type": "ride"}}],
            "recommendations": [{"name": "Quiet Cafe", "category": "restaurant"}],
            "memory_updates": [{"key": "budget", "value": "5000 BDT"}],
            "session_id": "ai-session-detail",
            "session_status": "active",
            "timeline": [{"time": "7:00 PM", "activity": "Dinner"}],
            "estimated_cost": 5000,
            "tips": ["Book ahead"],
        }
        message = ChatMessage.objects.create(
            conversation=conversation,
            sender=MessageSender.ASSISTANT,
            mode="chat",
            content=ai_payload["reply"],
            ai_response=ai_payload,
            voice_agent="Alfred",
        )

        response = self.client.get(
            reverse("chat-messages-detail", kwargs={"pk": str(message.id)})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(message.id))
        self.assertEqual(str(response.data["conversation_id"]), str(conversation.id))
        self.assertEqual(response.data["sender"], "alfred")
        self.assertEqual(response.data["message"], "Here is a complete plan.")
        self.assertEqual(response.data["mode"], "chat")
        self.assertEqual(response.data["voice_agent"], "Alfred")
        self.assertEqual(response.data["ai_response"], ai_payload)

    def test_messages_endpoint_does_not_show_other_users_messages(self):
        other_user = User.objects.create_user(
            email="other@example.com",
            password="StrongPass123!",
        )
        own_conversation = Conversation.objects.create(user=self.user, title="Mine")
        other_conversation = Conversation.objects.create(user=other_user, title="Other")
        ChatMessage.objects.create(
            conversation=own_conversation,
            sender=MessageSender.USER,
            content="My message",
        )
        ChatMessage.objects.create(
            conversation=other_conversation,
            sender=MessageSender.USER,
            content="Other message",
        )

        response = self.client.get(reverse("chat-messages-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["message"], "My message")

    def test_conversation_detail_includes_latest_10_messages(self):
        conversation = Conversation.objects.create(user=self.user, title="Detail thread")
        created_messages = []
        for index in range(12):
            created_messages.append(
                ChatMessage.objects.create(
                    conversation=conversation,
                    sender=MessageSender.USER if index % 2 == 0 else MessageSender.ASSISTANT,
                    content=f"Message {index}",
                )
            )

        response = self.client.get(
            reverse("chat-conversations-detail", kwargs={"pk": str(conversation.id)})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["messages"]), 10)
        self.assertEqual(response.data["messages"][0]["id"], str(created_messages[-1].id))
        self.assertEqual(response.data["messages"][0]["message"], "Message 11")
        self.assertEqual(response.data["messages"][-1]["id"], str(created_messages[2].id))
        self.assertEqual(response.data["messages"][-1]["message"], "Message 2")

    def test_conversation_list_keeps_messages_preview_empty(self):
        conversation = Conversation.objects.create(user=self.user, title="List thread")
        ChatMessage.objects.create(
            conversation=conversation,
            sender=MessageSender.USER,
            content="Hello",
        )

        response = self.client.get(reverse("chat-conversations-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["messages"], [])
