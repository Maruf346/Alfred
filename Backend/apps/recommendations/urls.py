from django.urls import path

from .views import *

urlpatterns = [
    path("restaurants/", RestaurantRecommendationView.as_view(), name="recommend-restaurants"),
    path("activities/", ActivityRecommendationView.as_view(), name="recommend-activities"),
    path("events/", EventRecommendationView.as_view(), name="recommend-events"),
    path("hotels/", HotelRecommendationView.as_view(), name="recommend-hotels"),
    path("gifts/", GiftRecommendationView.as_view(), name="recommend-gifts"),
    path("plans/", PlanDateOptionsView.as_view(), name="recommend-plans"),
    path("travel/", TravelRecommendationView.as_view(), name="recommend-travel"),
]
