"""
Alternative chat flow that returns JSON plus a temporary audio URL.

This intentionally lives beside the multipart flow instead of replacing it, so
we can test both client integration styles.
"""

import hashlib
import secrets

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.urls import reverse
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.ai_gateway.client import AlfredAIError
from apps.users.views import build_success_response_serializer, success_response, validation_error_serializer

from .audio_serializers import CachedAudioChatRequestSerializer, CachedAudioChatResponseSerializer
from .models import ChatMessage, Conversation, MessageSender
from .services import ChatService, ai_error_to_client_payload


class AIServiceUnavailable(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "AI service is unavailable."
    default_code = "ai_service_unavailable"


def build_tokenized_audio_cache_key(user_id, message_id, token) -> str:
    return f"chat-audio:{user_id}:{message_id}:{token}"


class CachedAudioChatMessageView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        operation_id="chat_message_create_cached_audio",
        summary="Send a chat message and cache premium audio",
        description=(
            "Alternative to the multipart chat endpoint. This endpoint always "
            "returns JSON. For premium `mode=speak` requests, the backend "
            "generates Alfred MP3 audio during the request, stores it in Redis "
            "temporarily, and returns `audio_url` for the frontend to fetch as "
            "a normal `audio/mpeg` response."
        ),
        request=CachedAudioChatRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer(
                    "CachedAudioChatMessageCreate",
                    CachedAudioChatResponseSerializer(),
                ),
                description="Chat response generated successfully.",
                examples=[
                    OpenApiExample(
                        "Premium Speak Response",
                        value={
                            "success": True,
                            "message": "Chat response generated successfully.",
                            "data": {
                                "conversation_id": "ed5f9424-38e6-4a40-b256-52cede0844f2",
                                "message_id": "54e6c63b-f839-4967-8408-b603a8f6b142",
                                "reply": "Let's craft a new and unique experience.",
                                "intent": "date_planning",
                                "confidence": 0.9,
                                "actions": [],
                                "recommendations": [],
                                "memory_updates": [],
                                "session_id": "ee298183-f112-4735-bb1b-3f4a787d2fd2",
                                "session_status": "active",
                                "timeline": [],
                                "estimated_cost": None,
                                "tips": [],
                                "voice_agent": "Alfred",
                                "audio_content_type": "audio/mpeg",
                                "audio_error": None,
                                "audio_url": "/api/chat/messages/54e6c63b-f839-4967-8408-b603a8f6b142/audio/",
                                "audio_expires_in_seconds": 3600,
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Validation error."),
            404: OpenApiResponse(response=validation_error_serializer, description="Conversation not found."),
            502: OpenApiResponse(response=validation_error_serializer, description="AI service error."),
        },
        examples=[
            OpenApiExample(
                "Premium Speak Request",
                value={
                    "message": "Plan a cozy date night",
                    "mode": "speak",
                    "conversation_id": "ed5f9424-38e6-4a40-b256-52cede0844f2",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = CachedAudioChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            data = ChatService.process_message(
                user=request.user,
                **serializer.validated_data,
            )
        except Conversation.DoesNotExist as exc:
            raise NotFound("Conversation not found.") from exc
        except AlfredAIError as exc:
            error = AIServiceUnavailable()
            error.detail = ai_error_to_client_payload(exc)
            raise error from exc

        audio_bytes = data.pop("audio_bytes", None)
        data["audio_url"] = None
        data["audio_expires_in_seconds"] = None

        if audio_bytes:
            ttl = settings.ALFRED_CHAT_AUDIO_TTL_SECONDS
            message_id = data["message_id"]
            audio_token = secrets.token_urlsafe(24)
            audio_cache_key = build_tokenized_audio_cache_key(
                request.user.id,
                message_id,
                audio_token,
            )
            audio_text_hash = hashlib.sha256(data.get("reply", "").encode("utf-8")).hexdigest()
            cache.set(
                audio_cache_key,
                {
                    "bytes": audio_bytes,
                    "content_type": data.get("audio_content_type") or "audio/mpeg",
                    "message_id": message_id,
                    "reply_hash": audio_text_hash,
                },
                timeout=ttl,
            )
            data["audio_url"] = (
                f"{reverse('chat-message-audio', kwargs={'message_id': message_id})}"
                f"?token={audio_token}"
            )
            data["audio_expires_in_seconds"] = ttl

        return success_response("Chat response generated successfully.", data)


class ChatMessageAudioView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        operation_id="chat_message_audio_retrieve",
        summary="Get cached message audio",
        description=(
            "Returns temporary Alfred MP3 audio for a message generated through "
            "`POST /api/chat/cached-audio/`. Audio is stored in Redis and expires "
            "after `ALFRED_CHAT_AUDIO_TTL_SECONDS`."
        ),
        parameters=[
            OpenApiParameter("message_id", str, location=OpenApiParameter.PATH, description="Assistant message UUID."),
        ],
        responses={
            200: OpenApiResponse(description="Raw MP3 audio (`audio/mpeg`)."),
            404: OpenApiResponse(response=validation_error_serializer, description="Audio missing, expired, or not owned by user."),
        },
    )
    def get(self, request, message_id):
        message = (
            ChatMessage.objects.filter(
                id=message_id,
                conversation__user=request.user,
                sender=MessageSender.ASSISTANT,
            )
            .select_related("conversation")
            .first()
        )
        if not message:
            raise NotFound("Audio not found.")

        audio_token = request.query_params.get("token")
        if not audio_token:
            raise NotFound("Audio has expired or is not available.")

        cache_key = build_tokenized_audio_cache_key(request.user.id, message.id, audio_token)

        cached_audio = cache.get(cache_key)
        if not cached_audio:
            raise NotFound("Audio has expired or is not available.")

        if str(cached_audio.get("message_id", message.id)) != str(message.id):
            raise NotFound("Audio has expired or is not available.")

        response = HttpResponse(
            cached_audio["bytes"],
            content_type=cached_audio.get("content_type") or "audio/mpeg",
        )
        response["Content-Disposition"] = f'inline; filename="alfred-{message.id}.mp3"'
        response["Cache-Control"] = "private, max-age=0, no-store"
        response["X-Alfred-Message-Id"] = str(message.id)
        if cached_audio.get("reply_hash"):
            response["X-Alfred-Reply-Hash"] = cached_audio["reply_hash"]
        return response
