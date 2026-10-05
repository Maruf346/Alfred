"""
users/models.py

Models:
    User          — custom AbstractUser (email-based auth, role-based access)

Role matrix:
    User        → normal user, is_staff = false, is_superadmin = false
    Admin       → is_staff = true, is_superadmin = true

Account state:
    is_active=True → normal active account
    is_active=False → blocked by admin

"""

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField



# ─────────────────────────────────────────────────────────────────────────────
# Choices
# ─────────────────────────────────────────────────────────────────────────────


class Gender(models.TextChoices):
    MALE   = "male",   "Male"
    FEMALE = "female", "Female"


class AuthProvider(models.TextChoices):
    SELF   = "self",   "Self"
    GOOGLE = "google", "Google"
    APPLE  = "apple",  "Apple"


class SubscriptionPlan(models.TextChoices):
    FREE    = "free",    "Free"
    MONTHLY = "monthly", "Monthly"
    ANNUAL  = "annual",  "Annual"


# ─────────────────────────────────────────────────────────────────────────────
# Custom User Manager
# ─────────────────────────────────────────────────────────────────────────────

class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Creates a Django superuser — mapped to SUPERADMIN role.
        Used only for the initial platform setup via manage.py createsuperuser.
        In production, superadmins are created programmatically or via admin panel.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)




# ─────────────────────────────────────────────────────────────────────────────
# Core User Model
# ─────────────────────────────────────────────────────────────────────────────

class User(AbstractUser):
    """
    Need to add details here...
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Remove unused Django AbstractUser fields
    username   = None

    # ── Core identity ─────────────────────────────────────────────────────────
    email     = models.EmailField(unique=True, verbose_name=_("Email Address"))
    full_name = models.CharField(max_length=150, blank=True, verbose_name=_("Full Name"))

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
        null=True,
        verbose_name=_("Gender"),
        help_text=(
            "User sets gender on Onboarding"
        ),
    )
    age = models.PositiveIntegerField(blank=True, null=True, verbose_name=_("Age"))

    # ──   DP     ───────────────────────────────────────────────────────────────
    profile_picture = models.ImageField(
        upload_to="users/profile_pictures/",
        blank=True,
        null=True,
        verbose_name=_("Profile Picture"),
    )
    
    # Admin only
    bio = models.TextField(blank=True, null=True, verbose_name=_("Bio"))
    
    # ── Location and preferences ──────────────────────────────────────────────
    location = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Location"))
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Address"))
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name=_("Latitude"),
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        verbose_name=_("Longitude"),
    )
    interests = models.JSONField(blank=True, null=True, verbose_name=_("Interests"))
    budget = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Budget"))
    
    # ── Subscription ──────────────────────────────────────────────────────────
    subscription_plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.choices,
        default=SubscriptionPlan.FREE,
        verbose_name=_("Subscription Plan"),
    )
    subscription_start = models.DateTimeField(null=True, blank=True)
    subscription_end   = models.DateTimeField(null=True, blank=True)

    # ── Auth provider ─────────────────────────────────────────────────────────
    provider    = models.CharField(
        max_length=20,
        choices=AuthProvider.choices,
        default=AuthProvider.SELF,
        verbose_name=_("Auth Provider"),
    )
    provider_id = models.CharField(max_length=255, blank=True, null=True)

    # ── Account state ─────────────────────────────────────────────────────────
    is_active           = models.BooleanField(
        default=True,
        verbose_name=_("Active"),
        help_text=(
            "False = account is blocked (by admin) "
        ),
    )

    # ── Device token (push notifications — future use) ────────────────────────
    device_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Device Token"),
        help_text="FCM/APNs device token for push notifications.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects        = UserManager()
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = []

    # ── Subscription helpers ──────────────────────────────────────────────────

    @property
    def is_subscribed(self) -> bool:
        """True for Monthly or Annual subscribers."""
        return self.subscription_plan in (SubscriptionPlan.MONTHLY, SubscriptionPlan.ANNUAL)

    def is_subscribed_monthly(self) -> bool:
        """True for Monthly subscribers."""
        return self.subscription_plan == SubscriptionPlan.MONTHLY
    
    def is_subscribed_annual(self) -> bool:
        """True for Annual subscribers."""
        return self.subscription_plan == SubscriptionPlan.ANNUAL

    @property
    def is_admin(self) -> bool:
        """True for platform administrators."""
        return self.is_staff and self.is_superuser
    
    def __str__(self):
        return self.full_name or self.email

    class Meta:
        verbose_name        = "User"
        verbose_name_plural = "Users"
        ordering            = ["-created_at"]


