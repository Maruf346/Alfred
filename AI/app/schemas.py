"""
All request/response contracts, matching the AI Developer Brief's
Output Format section exactly:

{
 "reply": "",
 "intent": "",
 "confidence": 0.98,
 "actions": [],
 "recommendations": [],
 "memory_updates": []
}
"""
import re
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional

from pydantic import BaseModel, BeforeValidator, Field


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

_CURRENCY_ALIASES = {
    "$": "USD", "US$": "USD", "USD": "USD", "DOLLAR": "USD", "DOLLARS": "USD",
    "TK": "BDT", "TAKA": "BDT", "৳": "BDT", "BDT": "BDT",
    "€": "EUR", "EUR": "EUR", "EURO": "EUR", "EUROS": "EUR",
    "£": "GBP", "GBP": "GBP", "POUND": "GBP", "POUNDS": "GBP", "STERLING": "GBP",
    "₹": "INR", "RS": "INR", "RS.": "INR", "INR": "INR", "RUPEE": "INR", "RUPEES": "INR",
}

_TOKEN_SPLIT_RE = re.compile(r"[^A-Za-z€£₹$৳]+")


def _normalize_currency(value: Optional[str]) -> str:
    """Accepts a currency shorthand/symbol/name — possibly messy, e.g. "tk /bdt"
    or "euro" — and normalizes it to an ISO code; defaults to USD when nothing
    usable was written, rather than passing an unrecognized string upstream."""
    if value is None or not str(value).strip():
        return "USD"
    raw = str(value).strip().upper()
    if raw in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[raw]

    for token in _TOKEN_SPLIT_RE.split(raw):
        if token in _CURRENCY_ALIASES:
            return _CURRENCY_ALIASES[token]

    if len(raw) == 3 and raw.isalpha():
        return raw  # looks like a real ISO code we don't have an alias for (e.g. "JPY")

    return "USD"


Currency = Annotated[str, BeforeValidator(_normalize_currency)]

_NUMBER_RE = re.compile(r"[\d,]+\.?\d*")


def _normalize_budget(value: Optional[Any]) -> Optional[float]:
    """The AI sometimes proposes a memory_update budget as free text with the
    currency baked in (e.g. "5000 BDT" instead of 5000) — extract the numeric
    part rather than rejecting it outright, since a strict float field crashing
    the whole request over this is worse than just parsing what's usable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER_RE.search(str(value))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


Budget = Annotated[Optional[float], BeforeValidator(_normalize_budget)]


class Intent(str, Enum):
    general_chat = "general_chat"
    restaurant_search = "restaurant_search"
    activity_planning = "activity_planning"
    event_search = "event_search"
    hotel_search = "hotel_search"
    date_planning = "date_planning"
    budget_planning = "budget_planning"
    travel_planning = "travel_planning"
    gift_suggestions = "gift_suggestions"
    coaching = "coaching"
    calendar_assistance = "calendar_assistance"
    anniversary_planning = "anniversary_planning"
    reminder_requests = "reminder_requests"
    small_talk = "small_talk"


class CalendarEvent(BaseModel):
    title: str
    date: str
    time: Optional[str] = None
    notes: Optional[str] = None


class UserMemory(BaseModel):
    """Mirrors the example memory object in the brief. Extra fields are allowed
    since the backend may evolve this shape independently of the AI layer."""
    name: Optional[str] = None
    budget: Budget = None
    favorite_food: Optional[str] = None
    favorite_activity: Optional[str] = None
    relationship_status: Optional[str] = None
    partner_name: Optional[str] = None
    anniversary: Optional[str] = None

    model_config = {"extra": "allow"}


class Location(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ActionRequest(BaseModel):
    """An action the AI proposes; the backend decides whether/how to execute it."""
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    key: str
    value: Any


class DetailItem(BaseModel):
    """A short, descriptive talking-point for a venue's detail page (e.g.
    "Ambiance", "Best For") — generated framing/atmosphere text based on real
    search-result signals (rating, price, category), never a claimed fact like
    a chef's name or an award that wasn't actually in the search data."""
    label: str
    description: str


class Recommendation(BaseModel):
    name: str
    category: Optional[str] = None
    rating: Optional[float] = None
    price_level: Optional[str] = None
    address: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    reason: Optional[str] = None
    details: List[DetailItem] = Field(default_factory=list)
    source: str = "serpapi"


class TimelineStep(BaseModel):
    time: str
    activity: str
    location: Optional[str] = None
    notes: Optional[str] = None
    # The full recommendation (image, price, rating, atmosphere details) for
    # this step's venue, when one applies — e.g. the "Meet At Coffee Shop"
    # step carries the restaurant's photo/price directly on itself, so the
    # timeline array alone is self-sufficient to render without needing to
    # separately look at PlanDateResponse.restaurant/activity.
    recommendation: Optional[Recommendation] = None


class PlanOption(BaseModel):
    """One browsable date-idea card (Figma: 'Recommended Date Ideas' list).
    Carries its own full step-by-step timeline so the client can render a
    complete plan (e.g. tapping "View Plan") without a second API call to
    fetch details for whichever option the user picks."""
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    estimated_cost: Optional[float] = None
    date_type: Optional[str] = None
    timeline: List[TimelineStep] = Field(default_factory=list)
    travel_notes: Optional[str] = None


class StructuredAIResponse(BaseModel):
    """The universal response envelope used by every endpoint."""
    reply: str
    intent: Intent
    confidence: float = Field(ge=0.0, le=1.0)
    actions: List[ActionRequest] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    memory_updates: List[MemoryUpdate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    memory: Optional[UserMemory] = None
    location: Optional[Location] = None
    calendar: Optional[List[CalendarEvent]] = None
    budget: Optional[float] = None
    currency: Currency = "USD"
    conversation_history: Optional[List[Dict[str, str]]] = None
    subscription_status: Optional[str] = None
    # Optional travel slots — only needed when discussing travel_planning; if
    # omitted here, /chat will try to fill them from session memory or ask.
    origin: Optional[str] = None
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class SessionStatus(str, Enum):
    new = "new"          # no session_id was sent; a fresh one was generated
    active = "active"    # session_id was sent and its prior context was found/used
    expired = "expired"  # session_id was sent but not found (evicted after idle
                          # TTL, or simply invalid) — a fresh, empty session was
                          # silently started under that same id. The caller should
                          # treat this like a lost conversation (e.g. show a
                          # "conversation reset" notice) rather than assume
                          # continuity actually happened.


class ChatResponse(StructuredAIResponse):
    """Chat is the master endpoint: when a message has enough structured detail
    (e.g. a known location), it internally calls the relevant specialist flow
    (recommend/plan-date/gift) and folds the result in here, so the caller gets
    one unified response instead of having to orchestrate multiple endpoints.

    When session_id is used, Alfred remembers prior turns/memory server-side —
    the backend doesn't have to resend full history every call. session_id is
    always echoed back (generated if the caller didn't send one) so the caller
    can persist it for the next turn. Check session_status to detect when a
    sent session_id wasn't found (expired/invalid) so context was NOT actually
    carried over, even though a session_id is still returned."""
    session_id: Optional[str] = None
    session_status: Optional[SessionStatus] = None
    timeline: List[TimelineStep] = Field(default_factory=list)
    estimated_cost: Optional[float] = None
    tips: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# POST /recommend
# ---------------------------------------------------------------------------

class RecommendCategory(str, Enum):
    restaurant = "restaurant"
    activity = "activity"
    event = "event"
    gift = "gift"
    hotel = "hotel"


class RecommendRequest(BaseModel):
    category: RecommendCategory
    location: str
    budget: Optional[float] = None
    currency: Currency = "USD"
    memory: UserMemory = Field(default_factory=UserMemory)
    preferences: Optional[str] = None


class RecommendResponse(BaseModel):
    recommendations: List[Recommendation]
    reply: str
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# POST /plan-date
# ---------------------------------------------------------------------------

class PlanDateRequest(BaseModel):
    location: str
    budget: Optional[float] = None
    currency: Currency = "USD"
    memory: UserMemory = Field(default_factory=UserMemory)
    calendar: List[CalendarEvent] = Field(default_factory=list)
    date_type: Optional[str] = None       # e.g. "first date", "anniversary"
    preferences: Optional[str] = None
    # When > 1, returns that many browsable candidate plans (PlanDateResponse.options)
    # instead of one fully-built plan — matches the Figma "Recommended Date Ideas"
    # browsing list. Callers then re-call with a specific date_type/preferences
    # derived from the chosen option to get its full timeline.
    num_options: int = 1


class PlanDateResponse(BaseModel):
    reply: str
    timeline: List[TimelineStep] = Field(default_factory=list)
    restaurant: Optional[Recommendation] = None
    activity: Optional[Recommendation] = None
    estimated_cost: Optional[float] = None
    travel_notes: Optional[str] = None
    actions: List[ActionRequest] = Field(default_factory=list)
    memory_updates: List[MemoryUpdate] = Field(default_factory=list)
    # Populated instead of timeline/restaurant/activity when num_options > 1 —
    # a browsable list of candidate plans (Figma: "Recommended Date Ideas").
    options: List[PlanOption] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# POST /coach
# ---------------------------------------------------------------------------

class CoachTopic(str, Enum):
    first_date = "first_date"
    second_date = "second_date"
    texting_advice = "texting_advice"
    relationship_advice = "relationship_advice"
    conversation_starters = "conversation_starters"


class CoachRequest(BaseModel):
    topic: CoachTopic
    message: Optional[str] = None
    memory: UserMemory = Field(default_factory=UserMemory)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)


class CoachResponse(BaseModel):
    reply: str
    tips: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# POST /gift
# ---------------------------------------------------------------------------

class GiftRequest(BaseModel):
    occasion: Optional[str] = None
    budget: Optional[float] = None
    currency: Currency = "USD"
    memory: UserMemory = Field(default_factory=UserMemory)
    location: Optional[str] = None
    preferences: Optional[str] = None


class GiftResponse(BaseModel):
    reply: str
    recommendations: List[Recommendation]
    confidence: float = Field(ge=0.0, le=1.0)
    memory_updates: List[MemoryUpdate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# POST /travel
# ---------------------------------------------------------------------------

class TravelRequest(BaseModel):
    origin: str
    destination: str
    start_date: str
    end_date: str
    budget: Optional[float] = None
    currency: Currency = "USD"
    memory: UserMemory = Field(default_factory=UserMemory)
    preferences: Optional[str] = None


class TravelResponse(BaseModel):
    reply: str
    flights: List[Recommendation] = Field(default_factory=list)
    hotels: List[Recommendation] = Field(default_factory=list)
    activities: List[Recommendation] = Field(default_factory=list)
    estimated_cost: Optional[float] = None
    actions: List[ActionRequest] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# POST /voice/speak
# ---------------------------------------------------------------------------

class SpeakRequest(BaseModel):
    text: str


# ---------------------------------------------------------------------------
# POST /budget/analyze
# ---------------------------------------------------------------------------

class ExpenseItem(BaseModel):
    category: str
    amount: float
    date: Optional[str] = None
    merchant: Optional[str] = None
    notes: Optional[str] = None


class SpendingBreakdownItem(BaseModel):
    category: str
    total_amount: float
    percentage: float
    expense_count: int = 1


class ReceiptSummary(BaseModel):
    total_expense: float
    currency: Currency = "USD"
    item_count: int = 0
    period_detected: Optional[str] = None
    merchant_names: List[str] = Field(default_factory=list)
    bank_name_detected: Optional[str] = None
    date_range_detected: Optional[str] = None
    deduplicated_count: int = 0


class BudgetAllocationItem(BaseModel):
    category: str
    recommended_amount: float
    notes: Optional[str] = None


class NextMonthPlan(BaseModel):
    estimated_total_budget: float
    currency: Currency = "USD"
    weekly_spending_target: Optional[float] = None
    projected_savings: Optional[float] = None
    suggested_allocations: List[BudgetAllocationItem] = Field(default_factory=list)
    planner_tips: List[str] = Field(default_factory=list)


class ExpenseAnalysisRequest(BaseModel):
    user_id: Optional[str] = None
    currency: Currency = "USD"
    current_budget: Optional[float] = None
    expenses_text: Optional[str] = None
    previous_month_expenses: List[ExpenseItem] = Field(default_factory=list)
    file_base64: Optional[str] = None
    file_type: Optional[str] = None  # e.g. "image/jpeg", "image/png", "application/pdf"
    notes: Optional[str] = None
    memory: UserMemory = Field(default_factory=UserMemory)


class ExpenseAnalysisResponse(BaseModel):
    reply: str
    receipt_summary: Optional[ReceiptSummary] = None
    analyzed_expenses: List[ExpenseItem] = Field(default_factory=list)
    spending_breakdown: List[SpendingBreakdownItem] = Field(default_factory=list)
    major_expense_areas: List[str] = Field(default_factory=list)
    spending_patterns: List[str] = Field(default_factory=list)
    insights_and_recommendations: List[str] = Field(default_factory=list)
    next_month_plan: Optional[NextMonthPlan] = None
    follow_up_questions: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    actions: List[ActionRequest] = Field(default_factory=list)
    memory_updates: List[MemoryUpdate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    follow_up_question: Optional[str] = None
