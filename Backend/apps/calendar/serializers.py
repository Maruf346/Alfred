from rest_framework import serializers

from .models import ScheduledPlan


class ScheduledPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledPlan
        fields = [
            "id",
            "plan_name",
            "scheduled_at",
            "recommendations",
            "timeline",
            "estimated_cost",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ScheduledPlanRescheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledPlan
        fields = ["scheduled_at"]
