from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ("-created_at",)
    list_display = (
        "email",
        "full_name",
        "provider",
        "subscription_plan",
        "is_active",
        "is_staff",
        "is_superuser",
        "created_at",
    )
    list_filter = (
        "provider",
        "subscription_plan",
        "is_active",
        "is_staff",
        "is_superuser",
        "gender",
    )
    search_fields = ("email", "full_name")
    readonly_fields = ("created_at", "updated_at", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "full_name",
                    "gender",
                    "age",
                    "profile_picture",
                    "bio",
                    "location",
                    "address",
                    "latitude",
                    "longitude",
                    "interests",
                    "budget",
                    "device_token",
                )
            },
        ),
        (
            "Subscription",
            {
                "fields": (
                    "subscription_plan",
                    "subscription_start",
                    "subscription_end",
                )
            },
        ),
        ("Authentication", {"fields": ("provider", "provider_id")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )
