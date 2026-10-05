"""
Conversation and message persistence for Alfred chat.
"""

import uuid

from django.conf import settings
from django.db import models


class ChatMode(models.TextChoices):
    CHAT = "chat", "Chat"
    SPEAK = "speak", "Speak"


class MessageSender(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    title = models.CharField(max_length=255, blank=True)
    ai_session_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    ai_session_last_seen_at = models.DateTimeField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "updated_at"]),
            models.Index(fields=["ai_session_id"]),
        ]

    def __str__(self):
        return self.title or f"Conversation {self.id}"


class ChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.CharField(max_length=20, choices=MessageSender.choices)
    mode = models.CharField(max_length=20, choices=ChatMode.choices, default=ChatMode.CHAT)
    content = models.TextField()
    ai_response = models.JSONField(default=dict, blank=True)
    voice_agent = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["sender"]),
        ]

    def __str__(self):
        return f"{self.sender}: {self.content[:50]}"
