"""
Notification services used by the backend.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Notification, NotificationPriority, NotificationType

logger = logging.getLogger(__name__)
User = get_user_model()


def _is_admin(user) -> bool:
    return getattr(user, "is_staff", False) and getattr(user, "is_superuser", False)


class NotificationService:
    @staticmethod
    def send(
        user,
        notification_type: str,
        title: str,
        body: str,
        data: dict | None = None,
        priority: str = NotificationPriority.NORMAL,
    ) -> Notification | None:
        if hasattr(user, "settings") and not user.settings.notification_enabled:
            logger.info("Notifications disabled for %s, skipped.", user.email)
            return None

        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            priority=priority,
        )

        if _is_admin(user):
            ws_ok = NotificationService._push_websocket(
                user_id=str(user.id),
                notification_id=str(notification.id),
                notification_type=notification_type,
                title=title,
                body=body,
                data=data or {},
                priority=priority,
            )
            notification.websocket_pushed = True
            notification.websocket_success = ws_ok
            notification.save(update_fields=["websocket_pushed", "websocket_success"])

        return notification

    @staticmethod
    def _push_websocket(
        user_id: str,
        notification_id: str,
        notification_type: str,
        title: str,
        body: str,
        data: dict,
        priority: str,
    ) -> bool:
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"user_{user_id}",
                {
                    "type": "notification_message",
                    "notification_id": notification_id,
                    "notification_type": notification_type,
                    "title": title,
                    "body": body,
                    "data": data,
                    "priority": priority,
                    "timestamp": timezone.now().isoformat(),
                },
            )
            return True
        except Exception as exc:
            logger.error("WebSocket push failed for user %s: %s", user_id, exc)
            return False

    @staticmethod
    def send_to_all_admins(
        notification_type: str,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> None:
        admins = User.objects.filter(is_staff=True, is_superuser=True, is_active=True)
        for admin in admins:
            NotificationService.send(
                user=admin,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
            )


class NotificationTemplates:
    # Account / onboarding

    @staticmethod
    def welcome(user) -> Notification | None:
        display_name = user.full_name or user.email
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.WELCOME,
            title="Welcome to Alfred AI",
            body=f"Hello {display_name}! Your account is ready. Complete your profile to get started.",
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def password_changed(user) -> Notification | None:
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.PASSWORD_CHANGED,
            title="Password Changed",
            body="Your Alfred AI password was changed successfully. If this wasn't you, contact support immediately.",
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def account_blocked(user) -> Notification | None:
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.ACCOUNT_BLOCKED,
            title="Account Blocked",
            body="Your Alfred AI account has been blocked. Please contact support if you believe this is a mistake.",
            priority=NotificationPriority.URGENT,
        )

    @staticmethod
    def account_reactivated(user) -> Notification | None:
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.ACCOUNT_REACTIVATED,
            title="Account Reactivated",
            body="Your Alfred AI account has been reactivated. You can continue using the app normally.",
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def profile_completed(user) -> Notification | None:
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.PROFILE_COMPLETED,
            title="Profile Completed",
            body="Nice work. Your profile is now complete and Alfred can personalize your experience better.",
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def onboarding_completed(user) -> Notification | None:
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.ONBOARDING_COMPLETED,
            title="Onboarding Complete",
            body="Thanks for sharing your preferences. Alfred is ready to make more personalized suggestions.",
            priority=NotificationPriority.NORMAL,
        )

    # Plans / calendar

    @staticmethod
    def plan_saved(user, plan_id: str, title: str) -> Notification | None:
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.PLAN_SAVED,
            title="Plan Saved",
            body=f'"{title}" has been saved to your plans.',
            data={"plan_id": str(plan_id), "title": title},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def plan_reminder(
        user,
        plan_id: str,
        title: str,
        scheduled_for: str | None = None,
    ) -> Notification | None:
        body = f'Reminder: "{title}" is coming up soon.'
        if scheduled_for:
            body = f'Reminder: "{title}" is scheduled for {scheduled_for}.'

        return NotificationService.send(
            user=user,
            notification_type=NotificationType.PLAN_REMINDER,
            title="Plan Reminder",
            body=body,
            data={"plan_id": str(plan_id), "title": title, "scheduled_for": scheduled_for},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def event_starting_soon(
        user,
        event_id: str,
        title: str,
        starts_at: str | None = None,
    ) -> Notification | None:
        body = f'"{title}" is starting soon.'
        if starts_at:
            body = f'"{title}" starts at {starts_at}.'

        return NotificationService.send(
            user=user,
            notification_type=NotificationType.EVENT_STARTING_SOON,
            title="Event Starting Soon",
            body=body,
            data={"event_id": str(event_id), "title": title, "starts_at": starts_at},
            priority=NotificationPriority.HIGH,
        )

    # Subscription / billing

    @staticmethod
    def subscription_upgraded(user, plan_name: str) -> Notification | None:
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.SUBSCRIPTION_UPGRADED,
            title="Subscription Upgraded",
            body=f"Your Alfred AI subscription is now {plan_name}.",
            data={"plan_name": plan_name},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def subscription_expiring(
        user,
        plan_name: str,
        ends_on: str | None = None,
    ) -> Notification | None:
        body = f"Your {plan_name} subscription will expire soon."
        if ends_on:
            body = f"Your {plan_name} subscription will expire on {ends_on}."

        return NotificationService.send(
            user=user,
            notification_type=NotificationType.SUBSCRIPTION_EXPIRING,
            title="Subscription Expiring",
            body=body,
            data={"plan_name": plan_name, "ends_on": ends_on},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def subscription_expired(user, plan_name: str) -> Notification | None:
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.SUBSCRIPTION_EXPIRED,
            title="Subscription Expired",
            body=f"Your {plan_name} subscription has expired.",
            data={"plan_name": plan_name},
            priority=NotificationPriority.URGENT,
        )

    @staticmethod
    def payment_failed(user, plan_name: str | None = None) -> Notification | None:
        body = "We could not process your latest payment."
        if plan_name:
            body = f"We could not process your payment for the {plan_name} subscription."

        return NotificationService.send(
            user=user,
            notification_type=NotificationType.PAYMENT_FAILED,
            title="Payment Failed",
            body=body,
            data={"plan_name": plan_name},
            priority=NotificationPriority.URGENT,
        )

    # AI / product

    @staticmethod
    def system_announcement(
        user,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> Notification | None:
        return NotificationService.send(
            user=user,
            notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
            title=title,
            body=body,
            data=data,
            priority=NotificationPriority.NORMAL,
        )

    # Admin-facing alerts

    @staticmethod
    def new_user_joined(new_user) -> None:
        display_name = new_user.full_name or new_user.email
        NotificationService.send_to_all_admins(
            notification_type=NotificationType.NEW_USER_JOINED,
            title="New User Registered",
            body=f"{display_name} just joined Alfred AI.",
            data={"user_id": str(new_user.id), "email": new_user.email},
        )

    @staticmethod
    def admin_broadcast(title: str, body: str, data: dict | None = None) -> None:
        NotificationService.send_to_all_admins(
            notification_type=NotificationType.ADMIN_BROADCAST,
            title=title,
            body=body,
            data=data,
        )
