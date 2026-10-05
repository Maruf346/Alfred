"""
notifications/urls.py

REST URL registration for notification viewsets.

WebSocket routing is configured separately in `core/asgi.py`.

REST endpoints registered here:
    /api/notification/user/
    /api/notification/user/<id>/
    /api/notification/user/<id>/mark-read/
    /api/notification/user/mark-all-read/
    /api/notification/user/unread-count/
    /api/notification/user/clear-read/

    /api/notification/admin/
    /api/notification/admin/<id>/
    /api/notification/admin/<id>/mark-read/
    /api/notification/admin/mark-all-read/
    /api/notification/admin/unread-count/
    /api/notification/admin/clear-read/
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminNotificationViewSet, UserNotificationViewSet

router = DefaultRouter()
router.register(r"user", UserNotificationViewSet, basename="notification-user")
router.register(r"admin", AdminNotificationViewSet, basename="notification-admin")

urlpatterns = [
    path("", include(router.urls)),
]
