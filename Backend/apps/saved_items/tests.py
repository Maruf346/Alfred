from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import SavedItem, SavedTravelPlan

User = get_user_model()


@override_settings(
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
)
class SavedItemsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="pass12345",
            full_name="Owner User",
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="pass12345",
            full_name="Other User",
        )
        self.client.force_authenticate(self.user)

    def test_create_saved_item_assigns_authenticated_user(self):
        response = self.client.post(
            reverse("saved-items-list"),
            {
                "recommendations": [{"name": "Lake View Cafe"}],
                "timeline": [{"time": "6:00 PM", "activity": "Dinner"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        saved_item = SavedItem.objects.get(id=response.data["id"])
        self.assertEqual(saved_item.user, self.user)
        self.assertEqual(saved_item.recommendations[0]["name"], "Lake View Cafe")

    def test_saved_item_list_only_returns_current_users_items(self):
        own_item = SavedItem.objects.create(
            user=self.user,
            recommendations=[{"name": "Own"}],
        )
        SavedItem.objects.create(
            user=self.other_user,
            recommendations=[{"name": "Other"}],
        )

        response = self.client.get(reverse("saved-items-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [str(own_item.id)])

    def test_retrieve_and_delete_saved_item_are_user_scoped(self):
        own_item = SavedItem.objects.create(user=self.user, timeline=[{"activity": "Walk"}])
        other_item = SavedItem.objects.create(user=self.other_user)

        retrieve_response = self.client.get(
            reverse("saved-items-detail", kwargs={"pk": own_item.id})
        )
        other_response = self.client.get(
            reverse("saved-items-detail", kwargs={"pk": other_item.id})
        )
        delete_response = self.client.delete(
            reverse("saved-items-detail", kwargs={"pk": own_item.id})
        )

        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SavedItem.objects.filter(id=own_item.id).exists())

    def test_create_saved_travel_plan_assigns_authenticated_user(self):
        response = self.client.post(
            reverse("saved-travel-plans-list"),
            {
                "flights": [{"airline": "Example Air"}],
                "hotels": [{"name": "Dhaka Garden Hotel"}],
                "activities": [{"name": "Old Dhaka food walk"}],
                "estimated_cost": "788.50",
                "actions": [{"action": "book_hotel"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        travel_plan = SavedTravelPlan.objects.get(id=response.data["id"])
        self.assertEqual(travel_plan.user, self.user)
        self.assertEqual(str(travel_plan.estimated_cost), "788.50")

    def test_saved_travel_plan_list_retrieve_and_delete_are_user_scoped(self):
        own_plan = SavedTravelPlan.objects.create(
            user=self.user,
            flights=[{"airline": "Example Air"}],
            estimated_cost="500.00",
        )
        other_plan = SavedTravelPlan.objects.create(user=self.other_user)

        list_response = self.client.get(reverse("saved-travel-plans-list"))
        retrieve_response = self.client.get(
            reverse("saved-travel-plans-detail", kwargs={"pk": own_plan.id})
        )
        other_response = self.client.get(
            reverse("saved-travel-plans-detail", kwargs={"pk": other_plan.id})
        )
        delete_response = self.client.delete(
            reverse("saved-travel-plans-detail", kwargs={"pk": own_plan.id})
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in list_response.data["results"]],
            [str(own_plan.id)],
        )
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SavedTravelPlan.objects.filter(id=own_plan.id).exists())
