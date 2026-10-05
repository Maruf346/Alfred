from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.notifications.models import Notification, NotificationType

from .models import ScheduledPlan
from .tasks import send_scheduled_plan_reminders

User = get_user_model()


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)
class ScheduledPlanAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="calendar-owner@example.com",
            password="pass12345",
            full_name="Calendar Owner",
        )
        self.other_user = User.objects.create_user(
            email="calendar-other@example.com",
            password="pass12345",
            full_name="Calendar Other",
        )
        self.client.force_authenticate(self.user)

    def test_create_plan_assigns_authenticated_user(self):
        scheduled_at = timezone.now() + timedelta(days=3)

        response = self.client.post(
            reverse("calendar-plans-list"),
            {
                "plan_name": "Dinner date",
                "scheduled_at": scheduled_at.isoformat(),
                "recommendations": [{"name": "Lake View Cafe"}],
                "timeline": [{"time": "7:00 PM", "activity": "Dinner"}],
                "estimated_cost": "2500.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        plan = ScheduledPlan.objects.get(id=response.data["id"])
        self.assertEqual(plan.user, self.user)
        self.assertEqual(plan.plan_name, "Dinner date")
        self.assertEqual(str(plan.estimated_cost), "2500.00")
        self.assertEqual(response.data["estimated_cost"], "2500.00")

    def test_list_retrieve_and_delete_are_user_scoped(self):
        own_plan = ScheduledPlan.objects.create(
            user=self.user,
            plan_name="Own plan",
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        other_plan = ScheduledPlan.objects.create(
            user=self.other_user,
            plan_name="Other plan",
            scheduled_at=timezone.now() + timedelta(days=1),
        )

        list_response = self.client.get(reverse("calendar-plans-list"))
        retrieve_response = self.client.get(
            reverse("calendar-plans-detail", kwargs={"pk": own_plan.id})
        )
        other_response = self.client.get(
            reverse("calendar-plans-detail", kwargs={"pk": other_plan.id})
        )
        delete_response = self.client.delete(
            reverse("calendar-plans-detail", kwargs={"pk": own_plan.id})
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [str(own_plan.id)])
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ScheduledPlan.objects.filter(id=own_plan.id).exists())

    def test_today_and_date_filters(self):
        today_plan = ScheduledPlan.objects.create(
            user=self.user,
            plan_name="Today",
            scheduled_at=timezone.now() + timedelta(hours=2),
        )
        tomorrow = timezone.localdate() + timedelta(days=1)
        tomorrow_plan = ScheduledPlan.objects.create(
            user=self.user,
            plan_name="Tomorrow",
            scheduled_at=timezone.now() + timedelta(days=1),
        )

        today_response = self.client.get(reverse("calendar-plans-list"), {"today": "true"})
        date_response = self.client.get(
            reverse("calendar-plans-list"),
            {"date": tomorrow.isoformat()},
        )
        invalid_response = self.client.get(reverse("calendar-plans-list"), {"date": "tomorrow"})

        self.assertEqual(today_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in today_response.data["results"]], [str(today_plan.id)])
        self.assertEqual(date_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in date_response.data["results"]], [str(tomorrow_plan.id)])
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_date_history_returns_past_plans_only(self):
        past_plan = ScheduledPlan.objects.create(
            user=self.user,
            plan_name="Past date",
            scheduled_at=timezone.now() - timedelta(days=1),
        )
        ScheduledPlan.objects.create(
            user=self.user,
            plan_name="Future date",
            scheduled_at=timezone.now() + timedelta(days=1),
        )

        response = self.client.get(reverse("calendar-plans-date-history"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data["results"]], [str(past_plan.id)])

    def test_reschedule_updates_only_datetime_and_resets_reminder(self):
        plan = ScheduledPlan.objects.create(
            user=self.user,
            plan_name="Original name",
            scheduled_at=timezone.now() + timedelta(days=1),
            reminder_sent_at=timezone.now(),
        )
        new_scheduled_at = timezone.now() + timedelta(days=2)

        response = self.client.patch(
            reverse("calendar-plans-reschedule", kwargs={"pk": plan.id}),
            {
                "scheduled_at": new_scheduled_at.isoformat(),
                "plan_name": "Changed name",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plan.refresh_from_db()
        self.assertEqual(plan.plan_name, "Original name")
        self.assertIsNone(plan.reminder_sent_at)
        self.assertAlmostEqual(
            plan.scheduled_at.timestamp(),
            new_scheduled_at.timestamp(),
            delta=1,
        )


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)
class ScheduledPlanReminderTaskTests(APITestCase):
    def test_reminder_task_sends_once_for_upcoming_plans(self):
        user = User.objects.create_user(
            email="reminder@example.com",
            password="pass12345",
            full_name="Reminder User",
        )
        plan = ScheduledPlan.objects.create(
            user=user,
            plan_name="Dinner reminder",
            scheduled_at=timezone.now() + timedelta(hours=5),
        )
        ScheduledPlan.objects.create(
            user=user,
            plan_name="Far future",
            scheduled_at=timezone.now() + timedelta(days=3),
        )

        first_count = send_scheduled_plan_reminders()
        second_count = send_scheduled_plan_reminders()

        self.assertEqual(first_count, 1)
        self.assertEqual(second_count, 0)
        plan.refresh_from_db()
        self.assertIsNotNone(plan.reminder_sent_at)
        self.assertEqual(
            Notification.objects.filter(
                user=user,
                notification_type=NotificationType.PLAN_REMINDER,
            ).count(),
            1,
        )
