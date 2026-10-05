import json
import uuid

from django.http import Http404, HttpResponse
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai_gateway.client import AlfredAIError
from apps.users.views import build_success_response_serializer, success_response, validation_error_serializer

from .models import Conversation
from .serializers import *
from .services import ChatService, ai_error_to_client_payload


class AIServiceUnavailable(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "AI service is unavailable."
    default_code = "ai_service_unavailable"


def build_chat_multipart_response(payload: dict) -> HttpResponse:
    audio_bytes = payload.pop("audio_bytes")
    audio_content_type = payload.get("audio_content_type") or "audio/mpeg"
    boundary = f"alfred-{uuid.uuid4().hex}"
    json_payload = {
        "success": True,
        "message": "Chat response generated successfully.",
        "data": payload,
    }
    json_bytes = json.dumps(json_payload, ensure_ascii=False).encode("utf-8")

    body = b"".join(
        [
            f"--{boundary}\r\n".encode("ascii"),
            b'Content-Disposition: inline; name="data"\r\n',
            b"Content-Type: application/json; charset=utf-8\r\n\r\n",
            json_bytes,
            b"\r\n",
            f"--{boundary}\r\n".encode("ascii"),
            b'Content-Disposition: attachment; name="audio"; filename="alfred-reply.mp3"\r\n',
            f"Content-Type: {audio_content_type}\r\n\r\n".encode("ascii"),
            audio_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return HttpResponse(
        body,
        content_type=f'multipart/mixed; boundary="{boundary}"',
        status=status.HTTP_200_OK,
    )


class ChatMessageView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        operation_id="chat_message_create",
        summary="Send a chat message to Alfred",
        description=(
            "Persists the user message, calls the FastAPI AI service, stores the "
            "assistant reply, and returns a structured response. Use `mode=chat` "
            "for text-only replies. Use `mode=speak` when the client wants voice; "
            "premium users receive a `multipart/mixed` response with JSON metadata "
            "and raw MP3 audio, while free users receive JSON with "
            "`voice_agent=flutter_tts` and no audio payload.\n\n"
            "To continue a conversation, the frontend must send the backend "
            "`conversation_id` returned by the previous response. The frontend "
            "should not send or manage the AI `session_id`; Django stores and "
            "reuses that internally."
        ),
        request=ChatRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("ChatMessageCreate", ChatResponseSerializer()),
                description="Chat response generated successfully.",
                examples=[
                    OpenApiExample(
                        "Text Chat Response",
                        value={
                            "success": True,
                            "message": "Chat response generated successfully.",
                            "data": {
                                "conversation_id": "8ff2d741-3c58-4b2f-8b44-7ec7b8e018f6",
                                "message_id": "0c37a95b-6b73-4694-b3b3-7a47d3f58d2b",
                                "reply": "A cozy date night sounds splendid. What is your location and budget?",
                                "intent": "date_planning",
                                "confidence": 0.95,
                                "actions": [],
                                "recommendations": [],
                                "memory_updates": [],
                                "session_id": "65c03762-dbf0-4623-93c3-790cb41fa282",
                                "session_status": "new",
                                "timeline": [],
                                "estimated_cost": None,
                                "tips": [],
                                "voice_agent": None,
                                "audio_content_type": None,
                                "audio_error": None,
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Validation or AI gateway error."),
        },
        examples=[
            OpenApiExample(
                "Start Chat",
                value={"message": "Plan a cozy date night for Friday", "mode": "chat"},
                request_only=True,
            ),
            OpenApiExample(
                "Continue Chat With Voice",
                value={
                    "message": "What about somewhere quieter instead?",
                    "mode": "speak",
                    "conversation_id": "8ff2d741-3c58-4b2f-8b44-7ec7b8e018f6",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
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

        if data.get("audio_bytes"):
            return build_chat_multipart_response(data)

        data.pop("audio_bytes", None)
        return success_response("Chat response generated successfully.", data)


@extend_schema(tags=["Chat"])
class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-updated_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Conversation.objects.none()
        return Conversation.objects.filter(user=self.request.user).prefetch_related("messages")

    @extend_schema(
        operation_id="chat_conversation_list",
        summary="List my conversations",
        description="Returns the authenticated user's conversations, newest first.",
        parameters=[
            OpenApiParameter("page", int, description="Page number."),
            OpenApiParameter("page_size", int, description="Results per page."),
        ],
        responses={200: ConversationSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        operation_id="chat_conversation_retrieve",
        summary="Retrieve a conversation",
        description="Returns a single conversation owned by the authenticated user.",
        responses={200: ConversationSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except Http404 as exc:
            raise NotFound("Conversation not found.") from exc


@extend_schema(tags=["Chat"])
class ChatInboxMessageViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ChatInboxMessageSerializer
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ChatMessage.objects.none()

        queryset = (
            ChatMessage.objects.filter(conversation__user=self.request.user)
            .select_related("conversation")
            .order_by("-created_at")
        )
        conversation_id = self.request.query_params.get("conversation_id")
        if conversation_id:
            queryset = queryset.filter(conversation_id=conversation_id)
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ChatMessageDetailSerializer
        return ChatInboxMessageSerializer

    @extend_schema(
        operation_id="chat_message_list",
        summary="List my chat messages",
        description=(
            "Returns paginated chat messages for the authenticated user, newest "
            "first. Use `conversation_id` to show one chat thread, or omit it to "
            "show the latest messages across all conversations."
        ),
        parameters=[
            OpenApiParameter("conversation_id", str, description="Optional conversation UUID filter."),
            OpenApiParameter("page", int, description="Page number."),
            OpenApiParameter("page_size", int, description="Results per page."),
            OpenApiParameter("ordering", str, description="Use `created_at` for oldest first or `-created_at` for newest first."),
        ],
        responses={200: ChatInboxMessageSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        operation_id="chat_message_retrieve",
        summary="Retrieve a full chat message",
        description=(
            "Returns the full stored chat message. Assistant messages include "
            "the complete `ai_response` JSON payload returned by the FastAPI AI "
            "service. User messages usually have an empty `ai_response` object."
        ),
        responses={200: ChatMessageDetailSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)
