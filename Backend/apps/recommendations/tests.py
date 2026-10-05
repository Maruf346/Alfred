from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.ai_gateway.client import AlfredAIError
from apps.users.models import User


class FakeRecommendationClient:
    payloads = []

    def post_json(self, path, payload):
        self.payloads.append({"path": path, "payload": payload})
        if path == "/plan-date":
            return {
                "reply": "Here are four date plans.",
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
                        "image_url": None,
                        "estimated_cost": None,
                        "date_type": "dining",
                        "timeline": [],
                        "travel_notes": "Consider a short walk nearby before dinner.",
                    }
                ],
                "confidence": 0.9,
            }
        if path == "/travel":
            return {
                "reply": "Here is a travel plan.",
                "flights": [{"name": "Flight A", "category": "flight"}],
                "hotels": [{"name": "Hotel A", "category": "hotel"}],
                "activities": [{"name": "Activity A", "category": "activity"}],
                "estimated_cost": 788,
                "actions": [],
                "confidence": 0.9,
            }
        return {
            "recommendations": [
                {
                    "name": "Lake View Cafe",
                    "category": payload["category"],
                    "rating": 4.8,
                    "price_level": None,
                    "address": "Mumbai",
                    "url": None,
                    "image_url": None,
                    "reason": None,
                    "details": [],
                    "source": "serpapi",
                }
            ],
            "reply": "Here's what I found nearby.",
            "confidence": 0.4,
        }


class FailingRecommendationClient:
    def post_json(self, path, payload):
        raise AlfredAIError(
            "AI service rejected the request.",
            status_code=500,
            detail={"detail": "Provider failed"},
        )


@override_settings(CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}})
class RecommendationAPITests(APITestCase):
    def setUp(self):
        FakeRecommendationClient.payloads = []
        self.user = User.objects.create_user(
            email="recommend@example.com",
            password="StrongPass123!",
            full_name="Recommend User",
            location="Mumbai",
            interests=["quiet", "outdoor seating"],
        )
        self.client.force_authenticate(self.user)

    @patch("apps.recommendations.services.AlfredAIClient", return_value=FakeRecommendationClient())
    def test_restaurant_endpoint_builds_payload_from_user_profile(self, _client):
        response = self.client.get(reverse("recommend-restaurants"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["recommendations"][0]["category"], "restaurant")
        self.assertEqual(FakeRecommendationClient.payloads[-1]["path"], "/recommend")
        self.assertEqual(
            FakeRecommendationClient.payloads[-1]["payload"],
            {
                "category": "restaurant",
                "location": "Mumbai",
                "preferences": "quiet, outdoor seating",
            },
        )

    @patch("apps.recommendations.services.AlfredAIClient", return_value=FakeRecommendationClient())
    def test_each_category_endpoint_uses_expected_category(self, _client):
        cases = [
            ("recommend-activities", "activity"),
            ("recommend-events", "event"),
            ("recommend-hotels", "hotel"),
            ("recommend-gifts", "gift"),
        ]

        for route_name, category in cases:
            with self.subTest(route_name=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(FakeRecommendationClient.payloads[-1]["payload"]["category"], category)

    @patch("apps.recommendations.services.AlfredAIClient", return_value=FakeRecommendationClient())
    def test_travel_endpoint_forwards_frontend_payload(self, _client):
        response = self.client.post(
            reverse("recommend-travel"),
            {
                "origin": "Mumbai",
                "destination": "Dhaka",
                "start_date": "2026-09-09",
                "end_date": "2026-09-12",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["reply"], "Here is a travel plan.")
        self.assertEqual(FakeRecommendationClient.payloads[-1]["path"], "/travel")
        self.assertEqual(FakeRecommendationClient.payloads[-1]["payload"]["origin"], "Mumbai")
        self.assertEqual(FakeRecommendationClient.payloads[-1]["payload"]["destination"], "Dhaka")
        self.assertEqual(FakeRecommendationClient.payloads[-1]["payload"]["start_date"], "2026-09-09")
        self.assertEqual(FakeRecommendationClient.payloads[-1]["payload"]["end_date"], "2026-09-12")

    @patch("apps.recommendations.services.AlfredAIClient", return_value=FakeRecommendationClient())
    def test_plan_date_options_endpoint_uses_user_location_and_default_option_count(self, _client):
        response = self.client.get(reverse("recommend-plans"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["reply"], "Here are four date plans.")
        self.assertEqual(response.data["data"]["options"][0]["name"], "Romantic Lake View Dinner")
        self.assertEqual(FakeRecommendationClient.payloads[-1]["path"], "/plan-date")
        self.assertEqual(
            FakeRecommendationClient.payloads[-1]["payload"],
            {
                "location": "Mumbai",
                "num_options": 4,
            },
        )

    def test_plan_date_options_endpoint_requires_user_location_field(self):
        self.user.location = None
        self.user.address = "Fallback address should not be used here"
        self.user.save(update_fields=["location", "address"])

        response = self.client.get(reverse("recommend-plans"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("location", str(response.data).lower())

    def test_recommendation_endpoint_requires_user_location(self):
        self.user.location = None
        self.user.address = None
        self.user.save(update_fields=["location", "address"])

        response = self.client.get(reverse("recommend-restaurants"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("location", str(response.data).lower())

    def test_travel_endpoint_validates_date_order(self):
        response = self.client.post(
            reverse("recommend-travel"),
            {
                "origin": "Mumbai",
                "destination": "Dhaka",
                "start_date": "2026-09-12",
                "end_date": "2026-09-09",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data)

    @override_settings(DEBUG=True)
    @patch("apps.recommendations.services.AlfredAIClient", return_value=FailingRecommendationClient())
    def test_ai_errors_return_bad_gateway(self, _client):
        response = self.client.get(reverse("recommend-restaurants"))

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(response.data["detail"], "AI service failed while generating recommendations.")
        self.assertEqual(response.data["ai_status_code"], 500)
        self.assertEqual(response.data["ai_error"], {"detail": "Provider failed"})
