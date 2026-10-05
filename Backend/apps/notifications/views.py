"""
notifications/views.py

REST endpoints for notifications with separate Swagger tags for user and admin
consumers.

Swagger tag structure:
    "Notifications - User"   -> Regular authenticated users (REST polling)
    "Notifications - Admin"  -> Platform administrators (REST + WebSocket)

Both tag groups use the same underlying logic via _NotificationMixin. The tag
split is only for documentation clarity.

WebSocket (admin dashboard only):
    ws://host/ws/notifications/?token=<access_token>
    Handled by NotificationConsumer in consumers.py.
"""

import logging

from django.utils import timezone
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)


_mark_all_read_response = inline_serializer(
    name="MarkAllReadResponse",
    fields={
        "message": drf_serializers.CharField(),
        "count": drf_serializers.IntegerField(),
    },
)

_unread_count_response = inline_serializer(
    name="UnreadCountResponse",
    fields={"unread_count": drf_serializers.IntegerField()},
)

_clear_read_response = inline_serializer(
    name="ClearReadResponse",
    fields={
        "message": drf_serializers.CharField(),
        "deleted_count": drf_serializers.IntegerField(),
    },
)


class _NotificationMixin:
    """
    Shared queryset and custom actions for notification viewsets.
    """

    serializer_class = NotificationSerializer
    filterset_fields = ["is_read", "notification_type", "priority"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
    queryset = Notification.objects.none()

    def get_queryset(self):
        """Return only the authenticated user's notifications."""
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        """Bulk-mark every unread notification as read."""
        count = (
            Notification.objects.filter(user=request.user, is_read=False).update(
                is_read=True,
                read_at=timezone.now(),
            )
        )
        return Response(
            {
                "message": f"{count} notification(s) marked as read.",
                "count": count,
            }
        )

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        """Return the unread notification count for the current user."""
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"unread_count": count})

    @action(detail=False, methods=["delete"], url_path="clear-read")
    def clear_read(self, request):
        """Permanently delete all read notifications for the current user."""
        deleted, _ = Notification.objects.filter(user=request.user, is_read=True).delete()
        return Response(
            {
                "message": f"{deleted} notification(s) deleted.",
                "deleted_count": deleted,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Notifications - User"])
@extend_schema_view(
    list=extend_schema(
        summary="List my notifications",
        description=(
            "Returns all notifications for the authenticated user, ordered newest "
            "first.\n\n"
            "Mobile clients should poll this endpoint periodically to fetch new "
            "notifications because regular user notifications are delivered via "
            "REST only.\n\n"
            "Filterable by: `is_read`, `notification_type`, `priority`.\n\n"
            "Response does not include `websocket_pushed` or "
            "`websocket_success` because regular users do not receive WebSocket "
            "pushes."
        ),
        parameters=[
            OpenApiParameter("is_read", bool, description="Filter by read status."),
            OpenApiParameter(
                "notification_type",
                str,
                description="Filter by notification type slug.",
            ),
            OpenApiParameter(
                "priority",
                str,
                description="Filter by priority: `low`, `normal`, `high`, `urgent`.",
            ),
            OpenApiParameter("page", int, description="Page number."),
            OpenApiParameter(
                "page_size",
                int,
                description="Results per page (default 8, max 600).",
            ),
        ],
        responses={200: NotificationSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Get a single notification",
        description="Retrieve full details of a single notification by its UUID.",
        responses={200: NotificationSerializer},
    ),
    mark_read=extend_schema(
        summary="Mark a notification as read",
        description="Sets `is_read=true` and stores the `read_at` timestamp.",
        responses={200: NotificationSerializer},
    ),
    mark_all_read=extend_schema(
        summary="Mark all notifications as read",
        description="Bulk-marks every unread notification as read in one call.",
        responses={200: _mark_all_read_response},
    ),
    unread_count=extend_schema(
        summary="Get unread notification count",
        description="Returns the number of unread notifications for the current user.",
        responses={200: _unread_count_response},
    ),
    clear_read=extend_schema(
        summary="Delete all read notifications",
        description="Permanently removes all read notifications. This action is irreversible.",
        responses={200: _clear_read_response},
    ),
)
class UserNotificationViewSet(_NotificationMixin, viewsets.ReadOnlyModelViewSet):
    """
    Notification feed for authenticated users.

    Mobile clients poll these endpoints periodically for new notifications.
    No WebSocket is used for non-admin users.
    """

    permission_classes = [IsAuthenticated]


@extend_schema(tags=["Notifications - Admin"])
@extend_schema_view(
    list=extend_schema(
        summary="Admin - List my notifications",
        description=(
            "Returns all notifications for the authenticated admin user, ordered "
            "newest first.\n\n"
            "Admin notifications are also pushed in real time via WebSocket:\n"
            "```\n"
            "ws://host/ws/notifications/?token=<access_token>\n"
            "```\n"
            "The admin dashboard should connect to the WebSocket on load and "
            "fall back to polling this REST endpoint if the socket disconnects.\n\n"
            "Filterable by: `is_read`, `notification_type`, `priority`.\n\n"
            "Response includes `websocket_pushed` and `websocket_success` for "
            "delivery-status visibility."
        ),
        parameters=[
            OpenApiParameter("is_read", bool, description="Filter by read status."),
            OpenApiParameter(
                "notification_type",
                str,
                description="Filter by notification type slug.",
            ),
            OpenApiParameter(
                "priority",
                str,
                description="Filter by priority: `low`, `normal`, `high`, `urgent`.",
            ),
            OpenApiParameter("page", int, description="Page number."),
            OpenApiParameter(
                "page_size",
                int,
                description="Results per page (default 8, max 600).",
            ),
        ],
        responses={200: NotificationSerializer(many=True)},
    ),
    retrieve=extend_schema(
        summary="Admin - Get a single notification",
        description=(
            "Retrieve full details of a single notification by its UUID.\n\n"
            "Includes `websocket_pushed` and `websocket_success` delivery "
            "metadata to help debug real-time delivery issues."
        ),
        responses={200: NotificationSerializer},
    ),
    mark_read=extend_schema(
        summary="Admin - Mark a notification as read",
        description="Sets `is_read=true` and stores the `read_at` timestamp.",
        responses={200: NotificationSerializer},
    ),
    mark_all_read=extend_schema(
        summary="Admin - Mark all notifications as read",
        description="Bulk-marks every unread admin notification as read in one call.",
        responses={200: _mark_all_read_response},
    ),
    unread_count=extend_schema(
        summary="Admin - Get unread notification count",
        description="Returns the number of unread notifications for the current admin user.",
        responses={200: _unread_count_response},
    ),
    clear_read=extend_schema(
        summary="Admin - Delete all read notifications",
        description="Permanently removes all read notifications for the current admin. Irreversible.",
        responses={200: _clear_read_response},
    ),
)
class AdminNotificationViewSet(_NotificationMixin, viewsets.ReadOnlyModelViewSet):
    """
    Notification feed for platform administrators.

    Admins receive persisted notifications and real-time WebSocket pushes.
    `websocket_pushed` and `websocket_success` reflect delivery status.
    """

    permission_classes = [IsAuthenticated]
