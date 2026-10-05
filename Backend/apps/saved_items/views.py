from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from .models import SavedItem, SavedTravelPlan
from .serializers import SavedItemSerializer, SavedTravelPlanSerializer


class _UserOwnedCreateListRetrieveDeleteViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset.none()
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema(tags=["Saved Items"])
@extend_schema_view(
    create=extend_schema(
        operation_id="saved_item_create",
        summary="Save an item",
        description=(
            "Saves a frontend-provided recommendations/timeline JSON payload for "
            "the authenticated user. No AI call is made here."
        ),
        request=SavedItemSerializer,
        responses={201: SavedItemSerializer},
        examples=[
            OpenApiExample(
                "Save Recommendations",
                value={
                    "recommendations": [
                        {
                            "name": "Lake View Cafe",
                            "category": "restaurant",
                            "reason": "Quiet place for a relaxed date.",
                        }
                    ],
                    "timeline": [
                        {
                            "time": "6:00 PM",
                            "activity": "Dinner",
                            "location": "Gulshan 1",
                        }
                    ],
                },
                request_only=True,
            )
        ],
    ),
    list=extend_schema(
        operation_id="saved_item_list",
        summary="List my saved items",
        description="Returns only saved items owned by the authenticated user, newest first.",
        responses={200: SavedItemSerializer(many=True)},
    ),
    retrieve=extend_schema(
        operation_id="saved_item_retrieve",
        summary="Retrieve a saved item",
        description="Returns the full saved recommendations/timeline payload.",
        responses={200: SavedItemSerializer},
    ),
    destroy=extend_schema(
        operation_id="saved_item_delete",
        summary="Delete a saved item",
        description="Deletes one saved item owned by the authenticated user.",
    ),
)
class SavedItemViewSet(_UserOwnedCreateListRetrieveDeleteViewSet):
    serializer_class = SavedItemSerializer
    queryset = SavedItem.objects.all()


@extend_schema(tags=["Saved Travel Plans"])
@extend_schema_view(
    create=extend_schema(
        operation_id="saved_travel_plan_create",
        summary="Save a travel plan",
        description=(
            "Saves a frontend-provided travel plan payload for the authenticated "
            "user. No AI call is made here."
        ),
        request=SavedTravelPlanSerializer,
        responses={201: SavedTravelPlanSerializer},
        examples=[
            OpenApiExample(
                "Save Travel Plan",
                value={
                    "flights": [{"airline": "Example Air", "price": 240}],
                    "hotels": [{"name": "Dhaka Garden Hotel", "price": 120}],
                    "activities": [{"name": "Old Dhaka food walk"}],
                    "estimated_cost": "788.00",
                    "actions": [{"action": "book_hotel", "payload": {"hotel_id": "dhaka-garden"}}],
                },
                request_only=True,
            )
        ],
    ),
    list=extend_schema(
        operation_id="saved_travel_plan_list",
        summary="List my saved travel plans",
        description="Returns only travel plans owned by the authenticated user, newest first.",
        responses={200: SavedTravelPlanSerializer(many=True)},
    ),
    retrieve=extend_schema(
        operation_id="saved_travel_plan_retrieve",
        summary="Retrieve a saved travel plan",
        description="Returns the full saved travel payload.",
        responses={200: SavedTravelPlanSerializer},
    ),
    destroy=extend_schema(
        operation_id="saved_travel_plan_delete",
        summary="Delete a saved travel plan",
        description="Deletes one saved travel plan owned by the authenticated user.",
    ),
)
class SavedTravelPlanViewSet(_UserOwnedCreateListRetrieveDeleteViewSet):
    serializer_class = SavedTravelPlanSerializer
    queryset = SavedTravelPlan.objects.all()
