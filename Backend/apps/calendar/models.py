import uuid

from django.conf import settings
from django.db import models


class ScheduledPlan(models.Model):
    """
    A user-owned scheduled plan shown in the calendar and date history.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="scheduled_plans",
    )
    plan_name = models.CharField(max_length=255, blank=True, null=True)
    scheduled_at = models.DateTimeField(db_index=True)
    recommendations = models.JSONField(blank=True, null=True)
    timeline = models.JSONField(blank=True, null=True)
    estimated_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )
    reminder_sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["user", "scheduled_at"]),
            models.Index(fields=["reminder_sent_at", "scheduled_at"]),
        ]

    def __str__(self):
        return self.plan_name or f"Scheduled plan {self.id}"
