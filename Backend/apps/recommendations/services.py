import logging
from typing import Any

from django.conf import settings

from apps.ai_gateway.client import AlfredAIClient, AlfredAIError

logger = logging.getLogger(__name__)


class RecommendationService:
    @classmethod
    def recommend_for_user(cls, *, user, category: str) -> dict[str, Any]:
        payload = cls._build_user_recommendation_payload(user=user, category=category)
        logger.info(
            "Calling AI recommendation endpoint",
            extra={"category": category, "user_id": str(user.id)},
        )
        return AlfredAIClient().post_json("/recommend", payload)

    @classmethod
    def travel(cls, *, user, origin, destination, start_date, end_date) -> dict[str, Any]:
        payload = {
            "origin": str(origin),
            "destination": str(destination),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        logger.info(
            "Calling AI travel endpoint",
            extra={
                "user_id": str(user.id),
                "origin": payload["origin"],
                "destination": payload["destination"],
            },
        )
        return AlfredAIClient().post_json("/travel", payload)

    @classmethod
    def plan_date_options_for_user(cls, *, user, num_options: int = 4) -> dict[str, Any]:
        location = (getattr(user, "location", None) or "").strip()
        if not location:
            raise ValueError("Please update your location before requesting date plans.")

        payload = {
            "location": location,
            "num_options": num_options,
        }

        logger.info(
            "Calling AI plan-date endpoint",
            extra={
                "user_id": str(user.id),
                "location": location,
                "num_options": num_options,
            },
        )
        return AlfredAIClient().post_json("/plan-date", payload)

    @classmethod
    def _build_user_recommendation_payload(cls, *, user, category: str) -> dict[str, Any]:
        location = cls._get_user_location(user)
        if not location:
            raise ValueError("Please update your location before requesting recommendations.")

        payload = {
            "category": category,
            "location": location,
            "preferences": cls._build_preferences(user),
        }
        return {key: value for key, value in payload.items() if value not in (None, "", [])}

    @staticmethod
    def _get_user_location(user) -> str | None:
        return user.location or user.address

    @staticmethod
    def _build_preferences(user) -> str | None:
        interests = user.interests
        if isinstance(interests, list):
            return ", ".join(str(item) for item in interests if str(item).strip())
        if isinstance(interests, dict):
            return ", ".join(f"{key}: {value}" for key, value in interests.items())
        if interests:
            return str(interests)
        return None


def ai_error_to_client_payload(exc: AlfredAIError) -> dict:
    detail = {
        "detail": ai_error_to_validation_message(exc),
        "ai_status_code": exc.status_code,
    }
    if settings.DEBUG and exc.detail:
        detail["ai_error"] = exc.detail
    return detail


def ai_error_to_validation_message(exc: AlfredAIError) -> str:
    if exc.status_code in (401, 403):
        return "AI service authentication failed."
    if exc.status_code == 422:
        return "AI service could not understand the request payload."
    if exc.status_code and exc.status_code >= 500:
        return "AI service failed while generating recommendations."
    return exc.message
