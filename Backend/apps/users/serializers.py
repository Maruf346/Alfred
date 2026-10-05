"""
Serializers for the users app.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

User = get_user_model()


def build_user_payload(user, request=None) -> dict:
    profile_picture = None
    if user.profile_picture:
        profile_picture = user.profile_picture.url
        if request is not None:
            profile_picture = request.build_absolute_uri(profile_picture)

    return {
        "id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "gender": user.gender,
        "age": user.age,
        "location": user.location,
        "address": user.address,
        "latitude": str(user.latitude) if user.latitude is not None else None,
        "longitude": str(user.longitude) if user.longitude is not None else None,
        "interests": user.interests,
        "budget": user.budget,
        "subscription_plan": user.subscription_plan,
        "provider": user.provider,
        "profile_picture": profile_picture,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
    }


# ── Step 1: Initiate Registration ───────────────────────────────────────────────

class InitiateRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        min_length=8,
        write_only=True,
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        min_length=8,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        return value.lower().strip()

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs


# ── Step 2: Verify OTP ────────────────────────────────────────────────────────

class VerifyRegistrationOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain digits only.")
        return value


# ── Resend OTP ────────────────────────────────────────────────────────────────

class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        return value.lower().strip()


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    confirm_new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_new_password"]:
            raise serializers.ValidationError(
                {"confirm_new_password": "Passwords do not match."}
            )
        if attrs["new_password"] == attrs["old_password"]:
            raise serializers.ValidationError(
                {"new_password": "New password must differ from the current one."}
            )
        try:
            validate_password(attrs["new_password"], self.context["request"].user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs


class InitiatePasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        return value.lower().strip()


class VerifyPasswordResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp   = serializers.CharField(min_length=6, max_length=6, required=True)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain digits only.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    reset_token          = serializers.CharField(required=True)
    new_password         = serializers.CharField(write_only=True, min_length=8, required=True, style={"input_type": "password"})
    confirm_new_password = serializers.CharField(write_only=True, min_length=8, required=True, style={"input_type": "password"})

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_new_password"]:
            raise serializers.ValidationError(
                {"confirm_new_password": "Passwords do not match."}
            )
        try:
            validate_password(attrs["new_password"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})
        return attrs


class GoogleOAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()


class AppleOAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()
    user = serializers.JSONField(required=False)


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "gender",
            "age",
            "profile_picture",
            "location",
            "address",
            "latitude",
            "longitude",
            "interests",
            "budget",
            "subscription_plan",
            "subscription_start",
            "subscription_end",
            "provider",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "email",
            "subscription_plan",
            "subscription_start",
            "subscription_end",
            "provider",
            "is_active",
            "created_at",
            "updated_at",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if instance.profile_picture and request:
            data["profile_picture"] = request.build_absolute_uri(instance.profile_picture.url)
        return data


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "full_name",
            "age",
            "profile_picture",
            "gender",
            "location",
            "interests",
            "budget",
            "device_token",
        )


class UserAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "address",
            "latitude",
            "longitude",
        )
        extra_kwargs = {
            "address": {"required": False, "allow_blank": True, "allow_null": True},
            "latitude": {"required": False, "allow_null": True},
            "longitude": {"required": False, "allow_null": True},
        }

    def validate_latitude(self, value):
        if value is not None and not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value):
        if value is not None and not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value


class AdminProfileSerializer(serializers.ModelSerializer):
    member_since = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "profile_picture",
            "bio",
            "member_since",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "email", "member_since", "created_at", "updated_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if instance.profile_picture and request:
            data["profile_picture"] = request.build_absolute_uri(instance.profile_picture.url)
        return data


class AdminProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("full_name", "profile_picture", "bio")


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "profile_picture",
            "provider",
            "subscription_plan",
            "is_active",
            "is_staff",
            "is_superuser",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
