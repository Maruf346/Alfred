import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.notifications.services import NotificationTemplates

from .models import ScheduledPlan

logger = logging.getLogger(__name__)


@shared_task(name="calendar.send_scheduled_plan_reminders")
def send_scheduled_plan_reminders() -> int:
    """
    Send one reminder per upcoming plan.

    The task runs periodically and scans for plans within the next 24 hours
    that have not already received a reminder.
    """

    now = timezone.now()
    reminder_window_end = now + timedelta(hours=24)
    sent_count = 0

    plans = (
        ScheduledPlan.objects.select_related("user")
        .filter(
            reminder_sent_at__isnull=True,
            scheduled_at__gt=now,
            scheduled_at__lte=reminder_window_end,
            user__is_active=True,
        )
        .order_by("scheduled_at")
    )

    for plan in plans:
        with transaction.atomic():
            locked_plan = (
                ScheduledPlan.objects.select_for_update()
                .select_related("user")
                .get(id=plan.id)
            )
            if locked_plan.reminder_sent_at is not None:
                continue

            title = locked_plan.plan_name or "Your date plan"
            scheduled_at_display = timezone.localtime(locked_plan.scheduled_at).strftime("%b %d, %Y at %I:%M %p")
            NotificationTemplates.plan_reminder(
                user=locked_plan.user,
                plan_id=str(locked_plan.id),
                title=title,
                scheduled_for=scheduled_at_display,
            )
            locked_plan.reminder_sent_at = timezone.now()
            locked_plan.save(update_fields=["reminder_sent_at"])
            sent_count += 1

    logger.info("Scheduled plan reminders sent: %s", sent_count)
    return sent_count
