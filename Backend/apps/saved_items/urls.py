from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SavedItemViewSet, SavedTravelPlanViewSet

router = DefaultRouter()
router.register("items", SavedItemViewSet, basename="saved-items")
router.register("travel-plans", SavedTravelPlanViewSet, basename="saved-travel-plans")

urlpatterns = [
    path("", include(router.urls)),
]
