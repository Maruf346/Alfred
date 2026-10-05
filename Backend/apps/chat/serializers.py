from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import ChatMessage, ChatMode, Conversation


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(
        allow_blank=False,
        trim_whitespace=True,
        max_length=8000,
    )
    mode = serializers.ChoiceField(
        choices=ChatMode.choices,
        default=ChatMode.CHAT,
        help_text="Use `chat` for text-only replies and `speak` when the client wants voice output.",
    )
    conversation_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        attrs.pop("session_id", None)
        return attrs


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = (
            "id",
            "sender",
            "mode",
            "content",
            "ai_response",
            "voice_agent",
            "created_at",
        )
        read_only_fields = fields


class ChatInboxMessageSerializer(serializers.ModelSerializer):
    message = serializers.CharField(source="content", read_only=True)
    sender = serializers.SerializerMethodField()
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ChatMessage
        fields = (
            "id",
            "conversation_id",
            "message",
            "sender",
            "timestamp",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_sender(self, instance):
        if instance.sender == "user":
            return "me"
        return "alfred"


class ChatMessageDetailSerializer(serializers.ModelSerializer):
    message = serializers.CharField(source="content", read_only=True)
    sender = serializers.SerializerMethodField()
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = ChatMessage
        fields = (
            "id",
            "conversation_id",
            "sender",
            "message",
            "timestamp",
            "mode",
            "voice_agent",
            "ai_response",
            "created_at",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_sender(self, instance):
        if instance.sender == "user":
            return "me"
        return "alfred"


class ConversationSerializer(serializers.ModelSerializer):
    latest_message = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = (
            "id",
            "title",
            "ai_session_id",
            "latest_message",
            "messages",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    @extend_schema_field(ChatMessageSerializer(allow_null=True))
    def get_latest_message(self, instance):
        message = instance.messages.order_by("-created_at").first()
        if not message:
            return None
        return ChatMessageSerializer(message).data

    @extend_schema_field(ChatInboxMessageSerializer(many=True))
    def get_messages(self, instance):
        request = self.context.get("request")
        view = self.context.get("view")
        if request is None or getattr(view, "action", None) != "retrieve":
            return []

        messages = instance.messages.order_by("-created_at")[:10]
        return ChatInboxMessageSerializer(messages, many=True).data


class ChatResponseSerializer(serializers.Serializer):
    conversation_id = serializers.UUIDField()
    message_id = serializers.UUIDField()
    reply = serializers.CharField()
    intent = serializers.CharField(allow_blank=True, allow_null=True)
    confidence = serializers.FloatField(allow_null=True)
    actions = serializers.JSONField()
    recommendations = serializers.JSONField()
    memory_updates = serializers.JSONField()
    session_id = serializers.CharField(allow_blank=True, allow_null=True)
    session_status = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    timeline = serializers.JSONField()
    estimated_cost = serializers.FloatField(allow_null=True)
    tips = serializers.JSONField()
    voice_agent = serializers.CharField(allow_blank=True, allow_null=True)
    audio_content_type = serializers.CharField(allow_blank=True, allow_null=True)
    audio_error = serializers.CharField(allow_blank=True, allow_null=True)
