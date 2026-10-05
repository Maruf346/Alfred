"""
Chat orchestration service.
"""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.ai_gateway.client import AlfredAIClient, AlfredAIError

from .models import ChatMessage, ChatMode, Conversation, MessageSender


class ChatService:
    @classmethod
    @transaction.atomic
    def process_message(cls, *, user, message: str, mode: str, conversation_id=None) -> dict:
        conversation = cls._get_or_create_conversation(
            user=user,
            message=message,
            conversation_id=conversation_id,
        )

        ChatMessage.objects.create(
            conversation=conversation,
            sender=MessageSender.USER,
            mode=mode,
            content=message,
        )

        ai_payload = cls._build_ai_payload(
            user=user,
            conversation=conversation,
            message=message,
        )
        ai_client = AlfredAIClient()
        ai_response = ai_client.post_json("/chat", ai_payload)

        assistant_message = cls._save_assistant_message(
            conversation=conversation,
            mode=mode,
            ai_response=ai_response,
        )

        returned_session_id = ai_response.get("session_id")
        if returned_session_id:
            conversation.ai_session_id = returned_session_id
            conversation.ai_session_last_seen_at = timezone.now()
            conversation.save(update_fields=["ai_session_id", "ai_session_last_seen_at", "updated_at"])

        response = cls._build_client_response(
            conversation=conversation,
            assistant_message=assistant_message,
            ai_response=ai_response,
            user=user,
            mode=mode,
            ai_client=ai_client,
        )
        return response

    @classmethod
    def _get_or_create_conversation(cls, *, user, message: str, conversation_id=None) -> Conversation:
        if conversation_id:
            return Conversation.objects.get(id=conversation_id, user=user)

        title = message[:80]
        return Conversation.objects.create(user=user, title=title)

    @classmethod
    def _build_ai_payload(cls, *, user, conversation: Conversation, message: str) -> dict:
        payload = {
            "message": message,
            "conversation_id": str(conversation.id),
            "memory": cls._build_memory(user),
            "location": cls._build_location(user),
            "subscription_status": "premium" if user.is_subscribed else "free",
        }

        if cls._ai_session_is_active(conversation):
            payload["session_id"] = conversation.ai_session_id
        else:
            conversation.ai_session_id = None
            conversation.ai_session_last_seen_at = None
            conversation.save(update_fields=["ai_session_id", "ai_session_last_seen_at", "updated_at"])

        history = cls._build_history(conversation)
        if history:
            payload["conversation_history"] = history

        budget = cls._parse_budget(user.budget)
        if budget is not None:
            payload["budget"] = budget

        return cls._remove_empty(payload)

    @staticmethod
    def _build_memory(user) -> dict:
        return {
            "name": user.full_name or None,
            "favorite_activity": ", ".join(user.interests) if isinstance(user.interests, list) else None,
        }

    @staticmethod
    def _build_location(user) -> dict | None:
        if not any([user.location, user.address, user.latitude, user.longitude]):
            return None

        return {
            "city": user.location or user.address,
            "latitude": float(user.latitude) if user.latitude is not None else None,
            "longitude": float(user.longitude) if user.longitude is not None else None,
        }

    @staticmethod
    def _build_history(conversation: Conversation) -> list[dict[str, str]]:
        max_items = settings.ALFRED_AI_HISTORY_LIMIT
        messages = conversation.messages.order_by("-created_at")[:max_items]
        history = []
        for item in reversed(list(messages)):
            role = "assistant" if item.sender == MessageSender.ASSISTANT else "user"
            history.append({"role": role, "content": item.content})
        return history

    @staticmethod
    def _parse_budget(value) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(Decimal(str(value).strip()))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _ai_session_is_active(conversation: Conversation) -> bool:
        if not conversation.ai_session_id or not conversation.ai_session_last_seen_at:
            return False
        age = timezone.now() - conversation.ai_session_last_seen_at
        return age.total_seconds() < settings.ALFRED_AI_SESSION_TTL_SECONDS

    @staticmethod
    def _remove_empty(value):
        if isinstance(value, dict):
            cleaned = {
                key: ChatService._remove_empty(item)
                for key, item in value.items()
                if item is not None
            }
            return {
                key: item
                for key, item in cleaned.items()
                if item not in ({}, [])
            }
        if isinstance(value, list):
            return [ChatService._remove_empty(item) for item in value if item is not None]
        return value

    @staticmethod
    def _save_assistant_message(*, conversation: Conversation, mode: str, ai_response: dict) -> ChatMessage:
        return ChatMessage.objects.create(
            conversation=conversation,
            sender=MessageSender.ASSISTANT,
            mode=mode,
            content=ai_response.get("reply", ""),
            ai_response=ai_response,
            voice_agent="Alfred" if mode == ChatMode.SPEAK else "",
        )

    @staticmethod
    def _build_client_response(
        *,
        conversation: Conversation,
        assistant_message: ChatMessage,
        ai_response: dict,
        user,
        mode: str,
        ai_client: AlfredAIClient,
    ) -> dict:
        audio_bytes = None
        audio_content_type = None
        audio_error = None
        voice_agent = None

        if mode == ChatMode.SPEAK:
            if user.is_subscribed:
                try:
                    audio_bytes, audio_content_type = ai_client.post_audio(
                        "/voice/speak",
                        {"text": ai_response.get("reply", "")},
                    )
                    voice_agent = "Alfred"
                except AlfredAIError as exc:
                    voice_agent = "flutter_tts"
                    audio_error = exc.message
            else:
                voice_agent = "flutter_tts"

            assistant_message.voice_agent = voice_agent
            assistant_message.save(update_fields=["voice_agent"])

        return {
            "conversation_id": str(conversation.id),
            "message_id": str(assistant_message.id),
            "reply": ai_response.get("reply", ""),
            "intent": ai_response.get("intent"),
            "confidence": ai_response.get("confidence"),
            "actions": ai_response.get("actions") or [],
            "recommendations": ai_response.get("recommendations") or [],
            "memory_updates": ai_response.get("memory_updates") or [],
            "session_id": ai_response.get("session_id"),
            "session_status": ai_response.get("session_status"),
            "timeline": ai_response.get("timeline") or [],
            "estimated_cost": ai_response.get("estimated_cost"),
            "tips": ai_response.get("tips") or [],
            "voice_agent": voice_agent,
            "audio_bytes": audio_bytes,
            "audio_content_type": audio_content_type,
            "audio_error": audio_error,
        }


def ai_error_to_client_payload(exc: AlfredAIError) -> dict:
    detail = {
        "detail": ai_error_to_validation_message(exc),
        "ai_status_code": exc.status_code,
    }
    if settings.DEBUG and exc.detail:
        detail["ai_error"] = exc.detail
    return detail


def ai_error_to_validation_message(exc: AlfredAIError) -> str:
    if exc.status_code in (401, 403):
        return "AI service authentication failed."
    if exc.status_code == 422:
        return "AI service could not understand the request payload."
    if exc.status_code and exc.status_code >= 500:
        return "AI service failed while generating a response."
    return exc.message
