from rest_framework import serializers

from .models import SavedItem, SavedTravelPlan


class SavedItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedItem
        fields = [
            "id",
            "recommendations",
            "timeline",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SavedTravelPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedTravelPlan
        fields = [
            "id",
            "flights",
            "hotels",
            "activities",
            "estimated_cost",
            "actions",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
