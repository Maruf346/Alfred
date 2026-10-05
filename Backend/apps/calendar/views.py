from datetime import datetime

from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ScheduledPlan
from .serializers import ScheduledPlanRescheduleSerializer, ScheduledPlanSerializer


def _parse_date_param(value: str):
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    return parsed


@extend_schema(tags=["Calendar"])
@extend_schema_view(
    create=extend_schema(
        operation_id="calendar_plan_create",
        summary="Schedule a plan",
        description=(
            "Creates a scheduled plan for the authenticated user. The backend "
            "sets `user` from the access token."
        ),
        request=ScheduledPlanSerializer,
        responses={201: ScheduledPlanSerializer},
        examples=[
            OpenApiExample(
                "Schedule Plan",
                value={
                    "plan_name": "Anniversary dinner",
                    "scheduled_at": "2026-09-09T19:00:00Z",
                    "recommendations": [{"name": "Lake View Cafe"}],
                    "timeline": [{"time": "7:00 PM", "activity": "Dinner"}],
                    "estimated_cost": "2500.00",
                },
                request_only=True,
            )
        ],
    ),
    list=extend_schema(
        operation_id="calendar_plan_list",
        summary="List my scheduled plans",
        description=(
            "Returns authenticated user's scheduled plans.\n\n"
            "Filter examples:\n"
            "- `/api/calendar/plans/?today=true` returns today's plans.\n"
            "- `/api/calendar/plans/?date=2026-09-09` returns plans scheduled on that exact date.\n\n"
            "If both `today` and `date` are sent, `today=true` takes priority."
        ),
        parameters=[
            OpenApiParameter(
                "today",
                bool,
                description="Set to `true` to return only today's scheduled plans. Example: `?today=true`.",
                examples=[
                    OpenApiExample(
                        "Today",
                        value=True,
                        description="GET /api/calendar/plans/?today=true",
                    )
                ],
            ),
            OpenApiParameter(
                "date",
                str,
                description="Filter plans by one calendar date. Format: `YYYY-MM-DD`. Example: `?date=2026-09-09`.",
                examples=[
                    OpenApiExample(
                        "Specific Date",
                        value="2026-09-09",
                        description="GET /api/calendar/plans/?date=2026-09-09",
                    )
                ],
            ),
            OpenApiParameter("page", int, description="Page number."),
            OpenApiParameter("page_size", int, description="Results per page."),
        ],
        responses={200: ScheduledPlanSerializer(many=True)},
    ),
    retrieve=extend_schema(
        operation_id="calendar_plan_retrieve",
        summary="Retrieve a scheduled plan",
        description="Returns the full scheduled plan payload.",
        responses={200: ScheduledPlanSerializer},
    ),
    destroy=extend_schema(
        operation_id="calendar_plan_delete",
        summary="Delete a scheduled plan",
        description="Deletes one scheduled plan owned by the authenticated user.",
    ),
)
class ScheduledPlanViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsAuthenticated]
    serializer_class = ScheduledPlanSerializer
    queryset = ScheduledPlan.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ScheduledPlan.objects.none()

        queryset = ScheduledPlan.objects.filter(user=self.request.user)

        today = self.request.query_params.get("today")
        date_value = self.request.query_params.get("date")

        if today and today.lower() in {"1", "true", "yes"}:
            return queryset.filter(scheduled_at__date=timezone.localdate())

        if date_value:
            try:
                selected_date = _parse_date_param(date_value)
            except ValueError as exc:
                raise ValidationError({"date": "Use YYYY-MM-DD format."}) from exc
            return queryset.filter(scheduled_at__date=selected_date)

        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        operation_id="calendar_plan_reschedule",
        summary="Reschedule a plan",
        description="Updates only the `scheduled_at` datetime for one scheduled plan.",
        request=ScheduledPlanRescheduleSerializer,
        responses={200: ScheduledPlanSerializer},
        examples=[
            OpenApiExample(
                "Reschedule Plan",
                value={"scheduled_at": "2026-09-10T20:00:00Z"},
                request_only=True,
            )
        ],
    )
    @action(detail=True, methods=["patch"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        plan = self.get_object()
        serializer = ScheduledPlanRescheduleSerializer(plan, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(reminder_sent_at=None)
        return Response(ScheduledPlanSerializer(plan).data, status=status.HTTP_200_OK)

    @extend_schema(
        operation_id="calendar_plan_date_history",
        summary="List date history",
        description=(
            "Returns authenticated user's scheduled plans where `scheduled_at` "
            "is in the past. These are treated as completed date history."
        ),
        parameters=[
            OpenApiParameter("page", int, description="Page number."),
            OpenApiParameter("page_size", int, description="Results per page."),
        ],
        responses={200: ScheduledPlanSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="date-history")
    def date_history(self, request):
        queryset = self.filter_queryset(
            ScheduledPlan.objects.filter(
                user=request.user,
                scheduled_at__lt=timezone.now(),
            ).order_by("-scheduled_at")
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
