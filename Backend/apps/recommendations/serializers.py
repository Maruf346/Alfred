from rest_framework import serializers


class RecommendationDetailSerializer(serializers.Serializer):
    label = serializers.CharField(allow_blank=True, required=False)
    description = serializers.CharField(allow_blank=True, required=False)


class RecommendationItemSerializer(serializers.Serializer):
    name = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    category = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    rating = serializers.FloatField(allow_null=True, required=False)
    price_level = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    address = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    url = serializers.URLField(allow_blank=True, allow_null=True, required=False)
    image_url = serializers.URLField(allow_blank=True, allow_null=True, required=False)
    reason = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    details = RecommendationDetailSerializer(many=True, required=False)
    source = serializers.CharField(allow_blank=True, allow_null=True, required=False)


class RecommendResponseSerializer(serializers.Serializer):
    recommendations = RecommendationItemSerializer(many=True)
    reply = serializers.CharField()
    confidence = serializers.FloatField(allow_null=True, required=False)


class TravelRequestSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=255, trim_whitespace=True)
    destination = serializers.CharField(max_length=255, trim_whitespace=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "End date must be on or after start date."}
            )
        return attrs


class TravelResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
    flights = RecommendationItemSerializer(many=True, required=False)
    hotels = RecommendationItemSerializer(many=True, required=False)
    activities = RecommendationItemSerializer(many=True, required=False)
    estimated_cost = serializers.FloatField(allow_null=True, required=False)
    actions = serializers.JSONField(required=False)
    confidence = serializers.FloatField(allow_null=True, required=False)


class PlanDateTimelineItemSerializer(serializers.Serializer):
    time = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    activity = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    location = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    notes = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    recommendation = RecommendationItemSerializer(allow_null=True, required=False)


class PlanDateOptionSerializer(serializers.Serializer):
    name = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    description = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    image_url = serializers.URLField(allow_blank=True, allow_null=True, required=False)
    estimated_cost = serializers.FloatField(allow_null=True, required=False)
    date_type = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    timeline = PlanDateTimelineItemSerializer(many=True, required=False)
    travel_notes = serializers.CharField(allow_blank=True, allow_null=True, required=False)


class PlanDateResponseSerializer(serializers.Serializer):
    reply = serializers.CharField(allow_blank=True, required=False)
    timeline = PlanDateTimelineItemSerializer(many=True, required=False)
    restaurant = RecommendationItemSerializer(allow_null=True, required=False)
    activity = RecommendationItemSerializer(allow_null=True, required=False)
    estimated_cost = serializers.FloatField(allow_null=True, required=False)
    travel_notes = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    actions = serializers.JSONField(required=False)
    memory_updates = serializers.JSONField(required=False)
    options = PlanDateOptionSerializer(many=True, required=False)
    confidence = serializers.FloatField(allow_null=True, required=False)
