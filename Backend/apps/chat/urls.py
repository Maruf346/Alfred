from django.urls import path
from rest_framework.routers import DefaultRouter

from .audio_views import CachedAudioChatMessageView, ChatMessageAudioView
from .views import ChatInboxMessageViewSet, ChatMessageView, ConversationViewSet

router = DefaultRouter()
router.register("conversations", ConversationViewSet, basename="chat-conversations")
router.register("messages", ChatInboxMessageViewSet, basename="chat-messages")

urlpatterns = [
    path("", ChatMessageView.as_view(), name="chat-message-create"),
    # path("cached-audio/", CachedAudioChatMessageView.as_view(), name="chat-message-create-cached-audio"),
    # path("messages/<uuid:message_id>/audio/", ChatMessageAudioView.as_view(), name="chat-message-audio"),
]

urlpatterns += router.urls
