from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ScheduledPlanViewSet

router = DefaultRouter()
router.register("plans", ScheduledPlanViewSet, basename="calendar-plans")

urlpatterns = [
    path("", include(router.urls)),
]
