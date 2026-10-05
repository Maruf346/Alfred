"""Intent detection — first stage of the Chat Flow in the brief."""
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.llm_client import BaseLLMClient, LLMError
from app.prompts import ALFRED_PERSONA, INTENT_CLASSIFIER_PROMPT
from app.schemas import Intent

logger = logging.getLogger("alfred.intent")

_VALID_INTENTS = {i.value for i in Intent}
_VALID_COACH_TOPICS = {"first_date", "second_date", "texting_advice", "relationship_advice", "conversation_starters"}


@dataclass
class DetectedIntent:
    intent: Intent
    confidence: float
    location_city: Optional[str] = None
    travel_origin: Optional[str] = None
    travel_destination: Optional[str] = None
    travel_start_date: Optional[str] = None
    travel_end_date: Optional[str] = None
    coach_topic: Optional[str] = None
    budget_amount: Optional[float] = None
    budget_no_limit: bool = False
    search_keywords: Optional[str] = None


def _format_history(history: List[Dict[str, str]]) -> str:
    if not history:
        return "(no prior messages)"
    return "\n".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in history[-6:])


async def detect_intent(llm: BaseLLMClient, message: str, history: List[Dict[str, str]]) -> DetectedIntent:
    """Classifies intent and extracts any slots (location, travel dates, coach
    topic) mentioned in the new message or earlier turns — all in this one LLM
    call rather than a separate round-trip per slot."""
    prompt = INTENT_CLASSIFIER_PROMPT.format(message=message, history=_format_history(history))
    try:
        data = await llm.complete_json(ALFRED_PERSONA, prompt)
        intent_str = str(data.get("intent", "general_chat"))
        confidence = float(data.get("confidence", 0.6))
    except (LLMError, ValueError, TypeError) as exc:
        logger.warning("Intent detection fell back to general_chat: %s", exc)
        return DetectedIntent(Intent.general_chat, 0.4)

    coach_topic = data.get("coach_topic") or None
    if coach_topic not in _VALID_COACH_TOPICS:
        coach_topic = None

    budget_amount = data.get("budget_amount")
    try:
        budget_amount = float(budget_amount) if budget_amount is not None else None
    except (TypeError, ValueError):
        budget_amount = None

    if intent_str not in _VALID_INTENTS:
        logger.warning("Model returned unknown intent %r, defaulting to general_chat", intent_str)
        return DetectedIntent(Intent.general_chat, min(confidence, 0.5), data.get("location_city") or None)

    return DetectedIntent(
        intent=Intent(intent_str),
        confidence=max(0.0, min(confidence, 1.0)),
        location_city=data.get("location_city") or None,
        travel_origin=data.get("travel_origin") or None,
        travel_destination=data.get("travel_destination") or None,
        travel_start_date=data.get("travel_start_date") or None,
        travel_end_date=data.get("travel_end_date") or None,
        coach_topic=coach_topic,
        budget_amount=budget_amount,
        budget_no_limit=bool(data.get("budget_no_limit")),
        search_keywords=data.get("search_keywords") or None,
    )
