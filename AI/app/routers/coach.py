from fastapi import APIRouter, Body, Depends

from app.dependencies import verify_service_api_key
from app.llm_client import get_llm_client
from app.schemas import CoachRequest, CoachResponse
from app.services import handle_coach

router = APIRouter(tags=["coach"], dependencies=[Depends(verify_service_api_key)])


@router.post("/coach", response_model=CoachResponse)
async def coach(
    req: CoachRequest = Body(
        ...,
        openapi_examples={
            "minimal": {
                "summary": "Minimal payload",
                "description": "Only topic is required.",
                "value": {"topic": "first_date"},
            },
            "with_context": {
                "summary": "Payload with optional context",
                "description": "Backend can send message, memory, and conversation history when available.",
                "value": {
                    "topic": "texting_advice",
                    "message": "She hasn't replied in two days, what should I say?",
                    "memory": {"partner_name": "Emily"},
                    "conversation_history": [
                        {"role": "user", "content": "We had a great first date."}
                    ],
                },
            },
        },
    )
) -> CoachResponse:
    llm = get_llm_client()
    return await handle_coach(req, llm)
