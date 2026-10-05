"""
Notification models for the Alfred backend.
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class NotificationType(models.TextChoices):
    # Account / authentication
    WELCOME = "welcome", "Welcome"
    PASSWORD_CHANGED = "pass_changed", "Password Changed"
    ACCOUNT_BLOCKED = "account_blocked", "Account Blocked"
    ACCOUNT_REACTIVATED = "account_reactivated", "Account Reactivated"
    PROFILE_COMPLETED = "profile_completed", "Profile Completed"
    ONBOARDING_COMPLETED = "onboarding_completed", "Onboarding Completed"

    # Plans / calendar
    PLAN_SAVED = "plan_saved", "Plan Saved"
    PLAN_REMINDER = "plan_reminder", "Plan Reminder"
    EVENT_STARTING_SOON = "event_starting_soon", "Event Starting Soon"

    # Subscription / billing
    SUBSCRIPTION_UPGRADED = "subscription_upgraded", "Subscription Upgraded"
    SUBSCRIPTION_EXPIRING = "subscription_expiring", "Subscription Expiring"
    SUBSCRIPTION_EXPIRED = "subscription_expired", "Subscription Expired"
    PAYMENT_FAILED = "payment_failed", "Payment Failed"

    # AI / product
    SYSTEM_ANNOUNCEMENT = "system_announcement", "System Announcement"

    # Admin-facing alerts
    NEW_USER_JOINED = "new_user_joined", "New User Joined"
    ADMIN_BROADCAST = "admin_broadcast", "Admin Broadcast"


class NotificationPriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class Notification(models.Model):
    """
    Single notification table shared across user and admin notification flows.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=60,
        choices=NotificationType.choices,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL,
    )

    # Delivery tracking is only meaningful for admin WebSocket delivery.
    # These remain False for regular user notifications, which are polled via REST.
    websocket_pushed = models.BooleanField(
        default=False,
        help_text="True when a real-time WebSocket push was attempted (admin only).",
    )
    websocket_success = models.BooleanField(
        default=False,
        help_text="True when the WebSocket push was confirmed sent (admin only).",
    )

    # Read tracking is shared by both user and admin notifications.
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        return f"[{self.notification_type}] {self.title} -> {self.user.email}"
