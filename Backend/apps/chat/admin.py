"""
Admin registrations for chat persistence.
"""

from django.contrib import admin

from .models import ChatMessage, Conversation


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    fields = ("sender", "mode", "content", "voice_agent", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "title", "ai_session_id", "updated_at")
    search_fields = ("user__email", "user__full_name", "title", "ai_session_id")
    list_filter = ("created_at", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ChatMessageInline]


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "mode", "intent", "voice_agent", "created_at")
    search_fields = ("content", "conversation__user__email")
    list_filter = ("sender", "mode", "voice_agent", "created_at")
    readonly_fields = ("id", "created_at")

    @admin.display(description="Intent")
    def intent(self, obj):
        return obj.ai_response.get("intent", "")
