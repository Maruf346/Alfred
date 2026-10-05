"""
Serializers for the cached-audio chat flow.
"""

from rest_framework import serializers

from .serializers import ChatRequestSerializer, ChatResponseSerializer


class CachedAudioChatRequestSerializer(ChatRequestSerializer):
    pass


class CachedAudioChatResponseSerializer(ChatResponseSerializer):
    audio_url = serializers.CharField(allow_blank=True, allow_null=True)
    audio_expires_in_seconds = serializers.IntegerField(allow_null=True)
