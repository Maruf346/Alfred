from fastapi import APIRouter, Body, Depends

from app.dependencies import verify_service_api_key
from app.exchange_client import get_exchange_client
from app.llm_client import get_llm_client
from app.schemas import GiftRequest, GiftResponse
from app.search_client import get_search_client
from app.services import handle_gift

router = APIRouter(tags=["gift"], dependencies=[Depends(verify_service_api_key)])


@router.post("/gift", response_model=GiftResponse)
async def gift(
    req: GiftRequest = Body(
        ...,
        openapi_examples={
            "minimal": {
                "summary": "Minimal payload",
                "description": "Every field is optional — Alfred can still help with just an empty body. "
                "currency accepts shorthand/symbols (\"tk\", \"$\", \"৳\", \"BDT\"...) and is normalized to an "
                "ISO code; omit it (or the whole field) to default to USD. It must be its own field — "
                "not appended to budget (e.g. NOT \"budget\": \"50 bdt\").",
                "value": {"occasion": "birthday", "budget": 50, "currency": "bdt"},
            },
            "with_context": {
                "summary": "Payload with optional context",
                "description": "Backend can send memory, location, and preferences when available. "
                "preferences should reflect what the user actually asked for in this turn (e.g. "
                "\"something more meaningful\") — without it, repeated calls with the same memory/"
                "budget/occasion produce the same search query and therefore identical results.",
                "value": {
                    "occasion": "anniversary",
                    "budget": 150,
                    "currency": "USD",
                    "location": "Mumbai",
                    "memory": {"partner_name": "Emily", "favorite_activity": "painting"},
                    "preferences": "something more meaningful than jewelry",
                },
            },
        },
    )
) -> GiftResponse:
    llm = get_llm_client()
    search = get_search_client()
    exchange = get_exchange_client()
    return await handle_gift(req, llm, search, exchange)
