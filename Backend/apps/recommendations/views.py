from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.ai_gateway.client import AlfredAIError
from apps.users.views import build_success_response_serializer, success_response, validation_error_serializer

from .serializers import *
from .services import *


class AIRecommendationUnavailable(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "AI recommendation service is unavailable."
    default_code = "ai_recommendation_unavailable"


class BaseRecommendationView(APIView):
    permission_classes = [IsAuthenticated]
    category = None
    response_label = "Recommendations"

    def get(self, request):
        try:
            data = RecommendationService.recommend_for_user(
                user=request.user,
                category=self.category,
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        except AlfredAIError as exc:
            error = AIRecommendationUnavailable()
            error.detail = ai_error_to_client_payload(exc)
            raise error from exc

        return success_response(f"{self.response_label} fetched successfully.", data)


class RestaurantRecommendationView(BaseRecommendationView):
    category = "restaurant"
    response_label = "Restaurant recommendations"

    @extend_schema(
        tags=["Recommendations"],
        operation_id="recommend_restaurants",
        summary="Get restaurant recommendations",
        description=(
            "Calls AI `/recommend` with `category=restaurant`, using the "
            "authenticated user's saved location and interests as preferences. "
            "The frontend does not need to send a payload."
        ),
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("RestaurantRecommendations", RecommendResponseSerializer()),
                description="Restaurant recommendations fetched successfully.",
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="User location is missing."),
            502: OpenApiResponse(response=validation_error_serializer, description="AI service error."),
        },
    )
    def get(self, request):
        return super().get(request)


class ActivityRecommendationView(BaseRecommendationView):
    category = "activity"
    response_label = "Activity recommendations"

    @extend_schema(
        tags=["Recommendations"],
        operation_id="recommend_activities",
        summary="Get activity recommendations",
        description="Calls AI `/recommend` with `category=activity` using saved user location and interests.",
        responses={200: build_success_response_serializer("ActivityRecommendations", RecommendResponseSerializer())},
    )
    def get(self, request):
        return super().get(request)


class EventRecommendationView(BaseRecommendationView):
    category = "event"
    response_label = "Event recommendations"

    @extend_schema(
        tags=["Recommendations"],
        operation_id="recommend_events",
        summary="Get event recommendations",
        description="Calls AI `/recommend` with `category=event` using saved user location and interests.",
        responses={200: build_success_response_serializer("EventRecommendations", RecommendResponseSerializer())},
    )
    def get(self, request):
        return super().get(request)


class HotelRecommendationView(BaseRecommendationView):
    category = "hotel"
    response_label = "Hotel recommendations"

    @extend_schema(
        tags=["Recommendations"],
        operation_id="recommend_hotels",
        summary="Get hotel recommendations",
        description="Calls AI `/recommend` with `category=hotel` using saved user location and interests.",
        responses={200: build_success_response_serializer("HotelRecommendations", RecommendResponseSerializer())},
    )
    def get(self, request):
        return super().get(request)


class GiftRecommendationView(BaseRecommendationView):
    category = "gift"
    response_label = "Gift recommendations"

    @extend_schema(
        tags=["Recommendations"],
        operation_id="recommend_gifts",
        summary="Get gift recommendations",
        description="Calls AI `/recommend` with `category=gift` using saved user location and interests.",
        responses={200: build_success_response_serializer("GiftRecommendations", RecommendResponseSerializer())},
    )
    def get(self, request):
        return super().get(request)


class TravelRecommendationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Recommendations"],
        operation_id="recommend_travel",
        summary="Get travel recommendations",
        description=(
            "Calls AI `/travel`. The frontend sends origin, destination, "
            "start_date, and end_date. Backend may enrich the request with user "
            "memory/budget when available."
        ),
        request=TravelRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("TravelRecommendations", TravelResponseSerializer()),
                description="Travel recommendations fetched successfully.",
                examples=[
                    OpenApiExample(
                        "Travel Response",
                        value={
                            "success": True,
                            "message": "Travel recommendations fetched successfully.",
                            "data": {
                                "reply": "Here's a well-rounded plan for your trip.",
                                "flights": [],
                                "hotels": [],
                                "activities": [],
                                "estimated_cost": 788,
                                "actions": [],
                                "confidence": 0.9,
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="Invalid travel payload."),
            502: OpenApiResponse(response=validation_error_serializer, description="AI service error."),
        },
        examples=[
            OpenApiExample(
                "Travel Request",
                value={
                    "origin": "Mumbai",
                    "destination": "Dhaka",
                    "start_date": "2026-09-09",
                    "end_date": "2026-09-12",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = TravelRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            data = RecommendationService.travel(
                user=request.user,
                **serializer.validated_data,
            )
        except AlfredAIError as exc:
            error = AIRecommendationUnavailable()
            error.detail = ai_error_to_client_payload(exc)
            raise error from exc

        return success_response("Travel recommendations fetched successfully.", data)


class PlanDateOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Recommendations"],
        operation_id="recommend_date_plans",
        summary="Get date plan options",
        description=(
            "Calls AI `/plan-date` and returns multiple browsable date plan "
            "options. Frontend sends no payload. Backend uses "
            "`request.user.location` and sends `num_options=4` by default."
        ),
        responses={
            200: OpenApiResponse(
                response=build_success_response_serializer("DatePlanOptions", PlanDateResponseSerializer()),
                description="Date plan options fetched successfully.",
                examples=[
                    OpenApiExample(
                        "Date Plan Options",
                        value={
                            "success": True,
                            "message": "Date plan options fetched successfully.",
                            "data": {
                                "reply": "Here are four distinct date plans for your consideration.",
                                "timeline": [],
                                "restaurant": None,
                                "activity": None,
                                "estimated_cost": None,
                                "travel_notes": None,
                                "actions": [],
                                "memory_updates": [],
                                "options": [
                                    {
                                        "name": "Romantic Lake View Dinner",
                                        "description": "A serene evening enjoying dinner with a splendid view.",
                                        "image_url": "https://example.com/date-plan.jpg",
                                        "estimated_cost": None,
                                        "date_type": "dining",
                                        "timeline": [
                                            {
                                                "time": "6:30 PM",
                                                "activity": "Dinner at Lake View Cafe",
                                                "location": "Powai Lake area",
                                                "notes": "Enjoy a scenic dinner.",
                                                "recommendation": {
                                                    "name": "Lake View Cafe",
                                                    "category": "restaurant",
                                                    "rating": 4.8,
                                                    "price_level": None,
                                                    "address": "Mumbai",
                                                    "url": None,
                                                    "image_url": "https://example.com/cafe.jpg",
                                                    "reason": "Excellent rating and scenic location",
                                                    "details": [],
                                                    "source": "serpapi",
                                                },
                                            }
                                        ],
                                        "travel_notes": "Consider a short walk nearby before dinner.",
                                    }
                                ],
                                "confidence": 0.9,
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            400: OpenApiResponse(response=validation_error_serializer, description="User location is missing."),
            502: OpenApiResponse(response=validation_error_serializer, description="AI service error."),
        },
    )
    def get(self, request):
        try:
            data = RecommendationService.plan_date_options_for_user(user=request.user)
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        except AlfredAIError as exc:
            error = AIRecommendationUnavailable()
            error.detail = ai_error_to_client_payload(exc)
            raise error from exc

        return success_response("Date plan options fetched successfully.", data)
