from fastapi import APIRouter, Body, Depends

from app.dependencies import verify_service_api_key
from app.llm_client import get_llm_client
from app.schemas import RecommendRequest, RecommendResponse
from app.search_client import get_search_client
from app.services import handle_recommend

router = APIRouter(tags=["recommend"], dependencies=[Depends(verify_service_api_key)])


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(
    req: RecommendRequest = Body(
        ...,
        openapi_examples={
            "minimal": {
                "summary": "Minimal payload",
                "description": "Only category and location are required.",
                "value": {"category": "restaurant", "location": "Mumbai"},
            },
            "with_context": {
                "summary": "Payload with optional context",
                "description": "Backend can send budget, memory, and preferences when available.",
                "value": {
                    "category": "restaurant",
                    "location": "Mumbai",
                    "budget": 80,
                    "currency": "USD",
                    "memory": {"favorite_food": "Italian"},
                    "preferences": "quiet, outdoor seating",
                },
            },
            "events": {
                "summary": "Events tab (concerts, festivals, shows)",
                "description": "category=event searches real dated events via Google Events (distinct "
                "from category=activity, which is static venues with no date). preferences can narrow "
                "the type of event, e.g. \"live music\", \"comedy\", \"art exhibition\".",
                "value": {
                    "category": "event",
                    "location": "Mumbai",
                    "preferences": "live music",
                },
            },
        },
    )
) -> RecommendResponse:
    llm = get_llm_client()
    search = get_search_client()
    return await handle_recommend(req, llm, search)
