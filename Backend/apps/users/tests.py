from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import Notification, NotificationType

from .models import User


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    },
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CELERY_TASK_ALWAYS_EAGER=True,
    CHANNEL_LAYERS={
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    },
)
class UserAuthFlowTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="user@example.com",
            password="StrongPass123!",
            full_name="Regular User",
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="StrongPass123!",
            full_name="Admin User",
            is_staff=True,
            is_superuser=True,
        )

    def test_user_login_returns_tokens(self):
        response = self.client.post(
            reverse("user-login"),
            {"email": self.user.email, "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertIn("access_token", response.data["data"])
        self.assertIn("refresh_token", response.data["data"])

    def test_admin_login_rejects_non_admin(self):
        response = self.client.post(
            reverse("admin-login"),
            {"email": self.user.email, "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Admin access required.", str(response.data))

    def test_change_password_updates_credentials(self):
        login = self.client.post(
            reverse("user-login"),
            {"email": self.user.email, "password": "StrongPass123!"},
            format="json",
        )
        access_token = login.data["data"]["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.post(
            reverse("password-change"),
            {
                "old_password": "StrongPass123!",
                "new_password": "EvenStrongerPass456!",
                "confirm_new_password": "EvenStrongerPass456!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("EvenStrongerPass456!"))

    def test_password_reset_flow_resets_password(self):
        initiate = self.client.post(
            reverse("password-reset-initiate"),
            {"email": self.user.email},
            format="json",
        )
        self.assertEqual(initiate.status_code, status.HTTP_200_OK)

        otp = cache.get(f"password_reset_otp:{self.user.email}")
        verify = self.client.post(
            reverse("password-reset-verify"),
            {"email": self.user.email, "otp": otp},
            format="json",
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

        reset_token = verify.data["data"]["reset_token"]
        confirm = self.client.post(
            reverse("password-reset-confirm"),
            {
                "reset_token": reset_token,
                "new_password": "BrandNewPass789!",
                "confirm_new_password": "BrandNewPass789!",
            },
            format="json",
        )
        self.assertEqual(confirm.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPass789!"))

    def test_registration_flow_creates_user_after_otp_verification(self):
        initiate = self.client.post(
            reverse("user-register-initiate"),
            {
                "full_name": "New User",
                "email": "new@example.com",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(initiate.status_code, status.HTTP_200_OK)

        otp_payload = cache.get("registration_otp:new@example.com")
        verify = self.client.post(
            reverse("user-register-verify"),
            {"email": "new@example.com", "otp": otp_payload["otp"]},
            format="json",
        )
        self.assertEqual(verify.status_code, status.HTTP_201_CREATED)
        new_user = User.objects.get(email="new@example.com")

        self.assertTrue(
            Notification.objects.filter(
                user=new_user,
                notification_type=NotificationType.WELCOME,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.admin,
                notification_type=NotificationType.NEW_USER_JOINED,
                data__user_id=str(new_user.id),
                data__email=new_user.email,
            ).exists()
        )

    def test_authenticated_user_can_update_address(self):
        login = self.client.post(
            reverse("user-login"),
            {"email": self.user.email, "password": "StrongPass123!"},
            format="json",
        )
        access_token = login.data["data"]["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.patch(
            reverse("user-address-update"),
            {
                "address": "Gulshan 1, Dhaka, Bangladesh",
                "latitude": "23.780573",
                "longitude": "90.416984",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        self.user.refresh_from_db()
        self.assertEqual(self.user.address, "Gulshan 1, Dhaka, Bangladesh")
        self.assertEqual(str(self.user.latitude), "23.780573")
        self.assertEqual(str(self.user.longitude), "90.416984")
