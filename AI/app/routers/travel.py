from fastapi import APIRouter, Body, Depends

from app.dependencies import verify_service_api_key
from app.llm_client import get_llm_client
from app.schemas import TravelRequest, TravelResponse
from app.search_client import get_search_client
from app.services import handle_travel

router = APIRouter(tags=["travel"], dependencies=[Depends(verify_service_api_key)])


@router.post("/travel", response_model=TravelResponse)
async def travel(
    req: TravelRequest = Body(
        ...,
        openapi_examples={
            "minimal": {
                "summary": "Minimal payload",
                "description": "Only origin, destination, start_date, and end_date are required.",
                "value": {
                    "origin": "Mumbai",
                    "destination": "Delhi",
                    "start_date": "2026-08-01",
                    "end_date": "2026-08-05",
                },
            },
            "with_context": {
                "summary": "Payload with optional context",
                "description": "Backend can send budget, memory, and preferences when available.",
                "value": {
                    "origin": "Mumbai",
                    "destination": "Delhi",
                    "start_date": "2026-08-01",
                    "end_date": "2026-08-05",
                    "budget": 500,
                    "currency": "USD",
                    "memory": {"partner_name": "Emily"},
                    "preferences": "budget-friendly, direct flights",
                },
            },
        },
    )
) -> TravelResponse:
    llm = get_llm_client()
    search = get_search_client()
    return await handle_travel(req, llm, search)
