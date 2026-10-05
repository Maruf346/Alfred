import uuid

from django.conf import settings
from django.db import models


class SavedItem(models.Model):
    """
    Generic saved recommendation/timeline payload owned by one user.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_items",
    )
    recommendations = models.JSONField(blank=True, null=True)
    timeline = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"Saved item {self.id} for {self.user}"


class SavedTravelPlan(models.Model):
    """
    Saved travel plan payload owned by one user.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_travel_plans",
    )
    flights = models.JSONField(blank=True, null=True)
    hotels = models.JSONField(blank=True, null=True)
    activities = models.JSONField(blank=True, null=True)
    estimated_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    actions = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"Saved travel plan {self.id} for {self.user}"
