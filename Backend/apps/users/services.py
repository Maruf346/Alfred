"""
Service layer for authentication and user account flows.
"""

import logging
import random
import secrets
import string

import jwt
import requests
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db import transaction
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jwt.algorithms import RSAAlgorithm
from rest_framework_simplejwt.tokens import RefreshToken

from .models import AuthProvider
from .serializers import build_user_payload
from .tasks import (
    send_password_reset_otp_email,
    send_registration_otp_email,
    send_welcome_email,
)

logger = logging.getLogger(__name__)
User = get_user_model()


def _dispatch_task(task, *args) -> None:
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        task(*args)
    else:
        task.delay(*args)


class OTPService:
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        return "".join(random.choices(string.digits, k=length))


class AuthService:
    @staticmethod
    def create_auth_payload(user, request=None) -> dict:
        refresh = RefreshToken.for_user(user)
        return {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": build_user_payload(user, request=request),
        }

    @staticmethod
    def authenticate_user(email: str, password: str, require_admin: bool = False):
        user = authenticate(email=email, password=password)
        if not user:
            raise ValueError("Invalid email or password.")
        if not user.is_active:
            raise ValueError("Your account has been deactivated. Please contact support.")
        if require_admin and not user.is_admin:
            raise ValueError("Admin access required.")
        return user

    @staticmethod
    def logout(refresh_token: str) -> None:
        token = RefreshToken(refresh_token)
        blacklist = getattr(token, "blacklist", None)
        if callable(blacklist):
            try:
                blacklist()
            except Exception as exc:
                logger.warning("Refresh token blacklist skipped: %s", exc)

    @staticmethod
    def change_password(user, new_password: str) -> None:
        user.set_password(new_password)
        user.save(update_fields=["password"])
        AuthService._notify_password_changed(user)

    @staticmethod
    def login_with_google(token: str, request=None) -> dict:
        if not settings.GOOGLE_WEB_CLIENT_ID:
            raise ValueError("Google login is not configured.")

        try:
            google_user = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                settings.GOOGLE_WEB_CLIENT_ID,
            )
        except Exception as exc:
            raise ValueError("Invalid or expired Google token.") from exc

        email = (google_user.get("email") or "").lower().strip()
        if not email:
            raise ValueError("Google account has no associated email.")

        user, created = AuthService._get_or_create_social_user(
            provider=AuthProvider.GOOGLE,
            email=email,
            provider_id=google_user.get("sub"),
            full_name=google_user.get("name") or "",
        )

        if created:
            picture_url = google_user.get("picture")
            if picture_url:
                AuthService._save_profile_picture_from_url(user, picture_url, "google")
            AuthService._run_post_registration_hooks(user)

        if not user.is_active:
            raise ValueError("Your account has been deactivated. Please contact support.")

        return AuthService.create_auth_payload(user, request=request)

    @staticmethod
    def login_with_apple(token: str, user_data=None, request=None) -> dict:
        if not settings.APPLE_CLIENT_ID:
            raise ValueError("Apple login is not configured.")

        try:
            response = requests.get("https://appleid.apple.com/auth/keys", timeout=10)
            response.raise_for_status()
            apple_keys = response.json()
            header = jwt.get_unverified_header(token)
            key_data = next(
                key for key in apple_keys["keys"] if key["kid"] == header["kid"]
            )
            public_key = RSAAlgorithm.from_jwk(key_data)
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=settings.APPLE_CLIENT_ID,
            )
        except StopIteration as exc:
            raise ValueError("Unable to verify Apple token.") from exc
        except Exception as exc:
            raise ValueError("Invalid or expired Apple token.") from exc

        email = (payload.get("email") or "").lower().strip()
        provider_id = payload.get("sub")
        if not email:
            raise ValueError("Apple account has no associated email.")

        full_name = ""
        if isinstance(user_data, dict):
            name_data = user_data.get("name")
            if isinstance(name_data, dict):
                full_name = " ".join(
                    part
                    for part in (name_data.get("firstName"), name_data.get("lastName"))
                    if part
                ).strip()
        if not full_name:
            full_name = email.split("@")[0]

        user, created = AuthService._get_or_create_social_user(
            provider=AuthProvider.APPLE,
            email=email,
            provider_id=provider_id,
            full_name=full_name,
        )

        if created:
            AuthService._run_post_registration_hooks(user)

        if not user.is_active:
            raise ValueError("Your account has been deactivated. Please contact support.")

        return AuthService.create_auth_payload(user, request=request)

    @staticmethod
    def _get_or_create_social_user(provider: str, email: str, provider_id: str, full_name: str):
        user = User.objects.filter(email=email).first()
        if user:
            if user.provider == AuthProvider.SELF:
                raise ValueError(
                    "An account with this email already exists. Please log in with email and password."
                )
            if user.provider != provider:
                provider_name = dict(AuthProvider.choices).get(user.provider, user.provider)
                raise ValueError(
                    f"An account with this email already exists via {provider_name}. Please use that login method."
                )
            if provider_id and user.provider_id != provider_id:
                user.provider_id = provider_id
                user.save(update_fields=["provider_id"])
            return user, False

        user = User.objects.create(
            email=email,
            full_name=full_name,
            is_active=True,
            provider=provider,
            provider_id=provider_id,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        return user, True

    @staticmethod
    def _save_profile_picture_from_url(user, url: str, suffix: str) -> None:
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Failed to fetch social profile image for %s: %s",
                user.email,
                exc,
            )
            return

        user.profile_picture.save(
            f"{user.id}_{suffix}.jpg",
            ContentFile(response.content),
            save=True,
        )

    @staticmethod
    def _run_post_registration_hooks(user) -> None:
        try:
            _dispatch_task(send_welcome_email, user.email, user.full_name)
        except Exception as exc:
            logger.warning("Failed to queue welcome email for %s: %s", user.email, exc)

        try:
            from apps.notifications.services import NotificationTemplates

            NotificationTemplates.welcome(user)
            NotificationTemplates.new_user_joined(user)
        except Exception as exc:
            logger.warning(
                "Failed to create welcome notifications for %s: %s",
                user.email,
                exc,
            )

    @staticmethod
    def _notify_password_changed(user) -> None:
        try:
            from apps.notifications.services import NotificationTemplates

            NotificationTemplates.password_changed(user)
        except Exception as exc:
            logger.warning(
                "Failed to create password-changed notification for %s: %s",
                user.email,
                exc,
            )


class RegistrationService:
    @staticmethod
    def initiate_registration(email: str, password: str, full_name: str) -> dict:
        email = email.lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValueError("This email is already registered.")

        otp = OTPService.generate_otp()
        cache.set(
            RegistrationService._cache_key(email),
            {
                "email": email,
                "full_name": full_name,
                "password": make_password(password),
                "otp": otp,
            },
            settings.OTP_EXPIRY_SECONDS,
        )

        try:
            _dispatch_task(send_registration_otp_email, email, otp, full_name)
        except Exception as exc:
            logger.warning("Failed to queue registration OTP email for %s: %s", email, exc)

        return {
            "message": "OTP sent to your email. Please verify to complete registration.",
            "email": email,
            "expires_in_seconds": settings.OTP_EXPIRY_SECONDS,
        }

    @staticmethod
    @transaction.atomic
    def verify_and_complete_registration(email: str, otp: str, request=None) -> dict:
        email = email.lower().strip()
        payload = cache.get(RegistrationService._cache_key(email))
        if not payload:
            raise ValueError("OTP expired. Please restart registration.")
        if payload["otp"] != otp:
            raise ValueError("Invalid OTP.")
        if User.objects.filter(email=email).exists():
            cache.delete(RegistrationService._cache_key(email))
            raise ValueError("This email is already registered.")

        user = User.objects.create(
            email=email,
            full_name=payload["full_name"],
            password=payload["password"],
            is_active=True,
            provider=AuthProvider.SELF,
        )
        cache.delete(RegistrationService._cache_key(email))
        AuthService._run_post_registration_hooks(user)
        return AuthService.create_auth_payload(user, request=request)

    @staticmethod
    def resend_otp(email: str) -> dict:
        email = email.lower().strip()
        cache_key = RegistrationService._cache_key(email)
        payload = cache.get(cache_key)
        if not payload:
            raise ValueError("Registration session expired. Please restart registration.")

        otp = OTPService.generate_otp()
        payload["otp"] = otp
        cache.set(cache_key, payload, settings.OTP_EXPIRY_SECONDS)

        try:
            _dispatch_task(
                send_registration_otp_email,
                email,
                otp,
                payload.get("full_name", ""),
            )
        except Exception as exc:
            logger.warning("Failed to resend registration OTP for %s: %s", email, exc)

        return {
            "message": "A new OTP has been sent to your email.",
            "email": email,
            "expires_in_seconds": settings.OTP_EXPIRY_SECONDS,
        }

    @staticmethod
    def _cache_key(email: str) -> str:
        return f"registration_otp:{email.lower().strip()}"


class PasswordResetService:
    @staticmethod
    def initiate_password_reset(email: str) -> dict:
        email = email.lower().strip()
        user = User.objects.filter(email=email).first()
        message = "If this email is registered, an OTP has been sent."

        if not user:
            return {
                "message": message,
                "expires_in_seconds": settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
            }

        otp = OTPService.generate_otp()
        cache.set(
            PasswordResetService._otp_cache_key(email),
            otp,
            settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
        )

        try:
            _dispatch_task(send_password_reset_otp_email, email, otp, user.full_name)
        except Exception as exc:
            logger.warning("Failed to queue password reset OTP for %s: %s", email, exc)

        return {
            "message": message,
            "expires_in_seconds": settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
        }

    @staticmethod
    def verify_reset_otp(email: str, otp: str) -> dict:
        email = email.lower().strip()
        stored_otp = cache.get(PasswordResetService._otp_cache_key(email))
        if not stored_otp:
            raise ValueError("OTP expired or not found.")
        if stored_otp != otp:
            raise ValueError("Invalid OTP.")

        reset_token = secrets.token_urlsafe(32)
        cache.set(
            PasswordResetService._token_cache_key(reset_token),
            email,
            settings.PASSWORD_RESET_TOKEN_EXPIRY_SECONDS,
        )
        cache.delete(PasswordResetService._otp_cache_key(email))
        return {
            "message": "OTP verified. You can now set a new password.",
            "reset_token": reset_token,
            "expires_in_seconds": settings.PASSWORD_RESET_TOKEN_EXPIRY_SECONDS,
        }

    @staticmethod
    def reset_password(reset_token: str, new_password: str) -> dict:
        email = cache.get(PasswordResetService._token_cache_key(reset_token))
        if not email:
            raise ValueError("Invalid or expired reset token.")

        user = User.objects.filter(email=email).first()
        if not user:
            raise ValueError("User not found.")

        user.set_password(new_password)
        user.save(update_fields=["password"])
        cache.delete(PasswordResetService._token_cache_key(reset_token))
        AuthService._notify_password_changed(user)
        return {"message": "Password reset successful. Please log in."}

    @staticmethod
    def _otp_cache_key(email: str) -> str:
        return f"password_reset_otp:{email.lower().strip()}"

    @staticmethod
    def _token_cache_key(reset_token: str) -> str:
        return f"password_reset_token:{reset_token}"
