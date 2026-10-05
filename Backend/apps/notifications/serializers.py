"""
notifications/serializers.py

Single serializer shared across users.

    • `websocket_pushed` / `websocket_success` are included so the admin
      dashboard can surface real-time delivery-status info where needed.
    • All fields are read-only — notifications are system-generated only.
"""

from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for all notification types.

    Used by:
        - User endpoints    → For Mobile App user
        - Admin endpoints   → For admin to access via admin dashboard
    """

    class Meta:
        model  = Notification
        fields = [
            "id",
            "notification_type",
            "title",
            "body",
            "data",
            "priority",
            "is_read",
            "read_at",
            "websocket_pushed",
            "websocket_success",
            "created_at",
        ]
        read_only_fields = fields