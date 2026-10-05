"""
Business logic for every endpoint. Routers stay thin; all prompt assembly,
search orchestration, and response construction lives here so it's easy to
unit test without spinning up FastAPI.
"""
import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.intent import DetectedIntent, detect_intent
from app.llm_client import BaseLLMClient, LLMError
from app.memory import safe_user_memory, sanitize_memory_updates
from app.session_store import SessionStore
from app.prompts import (
    AIRPORT_CODE_PROMPT,
    ALFRED_PERSONA,
    CHAT_RESPONSE_PROMPT,
    COACH_PROMPT,
    DETAILS_INSTRUCTION,
    EXPENSE_ANALYSIS_SYSTEM_PROMPT,
    GIFT_PROMPT,
    NO_SEARCH_RESULTS_PROMPT,
    PLAN_DATE_OPTIONS_PROMPT,
    PLAN_DATE_PROMPT,
    RANK_RECOMMENDATIONS_PROMPT,
    TRAVEL_PROMPT,
    format_calendar_block,
    format_location_block,
    format_memory_block,
)
from app.schemas import (
    ActionRequest,
    BudgetAllocationItem,
    ChatRequest,
    ChatResponse,
    CoachRequest,
    CoachResponse,
    CoachTopic,
    ExpenseAnalysisRequest,
    ExpenseAnalysisResponse,
    ExpenseItem,
    GiftRequest,
    GiftResponse,
    Intent,
    MemoryUpdate,
    NextMonthPlan,
    PlanDateRequest,
    PlanDateResponse,
    PlanOption,
    ReceiptSummary,
    Recommendation,
    RecommendCategory,
    RecommendRequest,
    RecommendResponse,
    SessionStatus,
    SpendingBreakdownItem,
    TimelineStep,
    TravelRequest,
    TravelResponse,
    Location,
    UserMemory,
)
from app.exchange_client import ExchangeError, ExchangeRateClient
from app.search_client import SearchError, SerpAPIClient

logger = logging.getLogger("alfred.services")


def _history_text(history: List[Dict[str, str]]) -> str:
    if not history:
        return "(no prior messages)"
    return "\n".join(f"{t.get('role', 'user')}: {t.get('content', '')}" for t in history[-8:])


def _budget_text(budget: Optional[float], currency: str) -> str:
    if budget is None:
        return "not specified"
    return f"{budget} {currency}"


_CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "BDT": "৳"}


def _format_price(amount: float, currency: str) -> str:
    symbol = _CURRENCY_SYMBOLS.get(currency)
    formatted = f"{amount:,.2f}"
    return f"{symbol}{formatted}" if symbol else f"{formatted} {currency}"


async def _localize_product_prices(
    results: List[Dict[str, Any]], exchange: ExchangeRateClient, target_currency: str
) -> List[Dict[str, Any]]:
    """Google Shopping results always come back priced in USD (see search_products);
    convert each result's price into the currency the user actually asked for."""
    localized = []
    for r in results:
        price_usd = r.get("extracted_price_usd")
        clean = {k: v for k, v in r.items() if k != "extracted_price_usd"}
        if target_currency != "USD" and price_usd is not None:
            try:
                converted = await exchange.convert(price_usd, "USD", target_currency)
                clean["price_level"] = _format_price(converted, target_currency)
            except ExchangeError as exc:
                logger.warning("Price conversion to %s failed (%s); leaving USD price as-is", target_currency, exc)
        localized.append(clean)
    return localized


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------

def _merge_memory(base: UserMemory, override: Optional[UserMemory]) -> UserMemory:
    """Caller-sent memory wins field-by-field over stored session memory —
    the backend may know things (e.g. from its own profile DB) this service
    hasn't been told yet, so its data always takes precedence when present."""
    if override is None:
        return base
    override_fields = override.model_dump(exclude_none=True)
    if not override_fields:
        return base
    merged = base.model_dump()
    merged.update(override_fields)
    return safe_user_memory(merged)


async def handle_chat(
    req: ChatRequest, llm: BaseLLMClient, search: SerpAPIClient, exchange: ExchangeRateClient,
    sessions: Optional[SessionStore] = None,
) -> ChatResponse:
    """Chat is the master endpoint: once intent is known, if the request already
    carries enough structured detail (e.g. a known location), route internally to
    the matching specialist flow and fold its result into one unified response —
    the caller doesn't need to orchestrate /recommend, /plan-date, /gift, /travel,
    or /coach separately.

    When req.session_id is set, prior turns, memory, location, and any other
    slots (travel dates, coach topic, etc.) mentioned in earlier turns are
    loaded from the session store and merged with whatever this request
    carries, so the backend doesn't have to resend full context every call."""
    session_id = req.session_id or (str(uuid.uuid4()) if sessions is not None else None)
    stored = sessions.get(session_id) if (sessions and req.session_id) else None
    stored_slots = stored.slots if stored else {}

    session_status: Optional[SessionStatus] = None
    if sessions is not None:
        if not req.session_id:
            session_status = SessionStatus.new
        elif stored is not None:
            session_status = SessionStatus.active
        else:
            # A session_id was sent but nothing was found for it — either it
            # expired (evicted after idle TTL) or was never valid. Either way,
            # context was NOT carried over even though we're about to proceed
            # under that same id — the caller needs to know this happened.
            session_status = SessionStatus.expired

    memory = _merge_memory(stored.memory if stored else UserMemory(), req.memory)
    calendar = req.calendar or []
    # Caller-sent location wins; otherwise fall back to whatever city was
    # remembered earlier in this session (e.g. mentioned two turns ago).
    location = req.location or (stored.location if stored else None) or Location()
    history = (stored.history if stored else []) + (req.conversation_history or [])

    detected = await detect_intent(llm, req.message, history)
    intent, intent_confidence = detected.intent, detected.confidence
    if detected.location_city and not location.city:
        location = Location(city=detected.location_city, country=location.country)
    if sessions and session_id and location.city:
        sessions.set_location(session_id, location.city)

    # Caller-sent values win over session-remembered ones, which win over
    # what the intent classifier just extracted from this message.
    def _slot(field_name: str, req_value: Optional[str], detected_value: Optional[str]) -> Optional[str]:
        return req_value or stored_slots.get(field_name) or detected_value

    # Search preferences must NEVER be the raw chat message — a real user
    # message can be pure logistics/filler ("umm the budget is 5000 bdt") or a
    # question back at Alfred ("why do you ask?"), and passing that verbatim
    # into a SerpAPI query produces garbage queries that reliably fail. Use
    # only the clean phrase the classifier distilled (or nothing at all).
    preferences = _slot("search_preferences", None, detected.search_keywords)
    if sessions and session_id and detected.search_keywords:
        sessions.update_slots(session_id, {"search_preferences": detected.search_keywords})

    # Budget-aware intents shouldn't search until the budget question has been
    # answered from *somewhere* — a number (this request, session, user memory,
    # or free text like "around 50 dollars"), OR an explicit "budget doesn't
    # matter" (no number to pass along, but the question is still answered).
    # Otherwise Alfred should ask, per the persona's "ask, don't guess" rule,
    # rather than silently searching unfiltered and never mentioning cost.
    budget = req.budget if req.budget is not None else (stored_slots.get("budget") or memory.budget or detected.budget_amount)
    budget_no_limit = bool(stored_slots.get("budget_no_limit")) or detected.budget_no_limit
    if sessions and session_id:
        if budget is not None:
            sessions.update_slots(session_id, {"budget": budget})
        if budget_no_limit:
            sessions.update_slots(session_id, {"budget_no_limit": True})
    have_budget = budget is not None or budget_no_limit

    if intent in (Intent.restaurant_search, Intent.activity_planning) and location.city and have_budget:
        category = RecommendCategory.restaurant if intent == Intent.restaurant_search else RecommendCategory.activity
        sub_req = RecommendRequest(
            category=category, location=location.city, budget=budget, currency=req.currency,
            memory=memory, preferences=preferences,
        )
        rec = await handle_recommend(sub_req, llm, search, history=history)
        return _finalize_chat(
            req, sessions, session_id, session_status, memory,
            reply=rec.reply, intent=intent, confidence=rec.confidence,
            recommendations=rec.recommendations,
        )

    if intent == Intent.event_search and location.city:
        # Unlike restaurants/gifts, events aren't typically budget-filtered —
        # asking "what's your budget" before showing "what's on this weekend"
        # is awkward, so this searches as soon as a city is known.
        sub_req = RecommendRequest(
            category=RecommendCategory.event, location=location.city, budget=budget, currency=req.currency,
            memory=memory, preferences=preferences,
        )
        rec = await handle_recommend(sub_req, llm, search, history=history)
        return _finalize_chat(
            req, sessions, session_id, session_status, memory,
            reply=rec.reply, intent=intent, confidence=rec.confidence,
            recommendations=rec.recommendations,
        )

    if intent == Intent.hotel_search and location.city and have_budget:
        sub_req = RecommendRequest(
            category=RecommendCategory.hotel, location=location.city, budget=budget, currency=req.currency,
            memory=memory, preferences=preferences,
        )
        rec = await handle_recommend(sub_req, llm, search, history=history)
        return _finalize_chat(
            req, sessions, session_id, session_status, memory,
            reply=rec.reply, intent=intent, confidence=rec.confidence,
            recommendations=rec.recommendations,
        )

    if intent == Intent.date_planning and location.city and have_budget:
        sub_req = PlanDateRequest(
            location=location.city, budget=budget, currency=req.currency,
            memory=memory, calendar=calendar, preferences=preferences,
        )
        plan = await handle_plan_date(sub_req, llm, search, history=history)
        recs = [r for r in (plan.restaurant, plan.activity) if r]
        return _finalize_chat(
            req, sessions, session_id, session_status, memory,
            reply=plan.reply, intent=intent, confidence=plan.confidence,
            actions=plan.actions, recommendations=recs, memory_updates=plan.memory_updates,
            timeline=plan.timeline, estimated_cost=plan.estimated_cost,
        )

    if intent == Intent.gift_suggestions and have_budget:
        sub_req = GiftRequest(
            budget=budget, currency=req.currency, memory=memory, location=location.city,
            preferences=preferences,
        )
        gift = await handle_gift(sub_req, llm, search, exchange, history=history)
        return _finalize_chat(
            req, sessions, session_id, session_status, memory,
            reply=gift.reply, intent=intent, confidence=gift.confidence,
            recommendations=gift.recommendations, memory_updates=gift.memory_updates,
        )

    if intent == Intent.travel_planning:
        origin = _slot("travel_origin", req.origin, detected.travel_origin)
        destination = _slot("travel_destination", req.destination, detected.travel_destination)
        start_date = _slot("travel_start_date", req.start_date, detected.travel_start_date)
        end_date = _slot("travel_end_date", req.end_date, detected.travel_end_date)
        if sessions and session_id:
            sessions.update_slots(session_id, {
                "travel_origin": origin, "travel_destination": destination,
                "travel_start_date": start_date, "travel_end_date": end_date,
            })
        if origin and destination and start_date and end_date and have_budget:
            sub_req = TravelRequest(
                origin=origin, destination=destination, start_date=start_date, end_date=end_date,
                budget=budget, currency=req.currency, memory=memory, preferences=preferences,
            )
            travel = await handle_travel(sub_req, llm, search)
            recs = travel.flights + travel.hotels + travel.activities
            return _finalize_chat(
                req, sessions, session_id, session_status, memory,
                reply=travel.reply, intent=intent, confidence=travel.confidence,
                actions=travel.actions, recommendations=recs, estimated_cost=travel.estimated_cost,
            )
        # Missing a required slot (dates, budget) — fall through to the
        # generic chat branch below, which asks a follow-up rather than guessing.

    if intent == Intent.coaching:
        topic_str = _slot("coach_topic", None, detected.coach_topic) or "relationship_advice"
        try:
            topic = CoachTopic(topic_str)
        except ValueError:
            topic = CoachTopic.relationship_advice
        if sessions and session_id:
            sessions.update_slots(session_id, {"coach_topic": topic.value})
        sub_req = CoachRequest(topic=topic, message=req.message, memory=memory, conversation_history=history)
        coach = await handle_coach(sub_req, llm)
        return _finalize_chat(
            req, sessions, session_id, session_status, memory,
            reply=coach.reply, intent=intent, confidence=coach.confidence, tips=coach.tips,
        )

    prompt = CHAT_RESPONSE_PROMPT.format(
        persona=ALFRED_PERSONA,
        memory_block=format_memory_block(memory),
        calendar_block=format_calendar_block(calendar),
        location_block=format_location_block(location),
        budget=_budget_text(budget, req.currency),
        intent=intent.value,
        history=_history_text(history),
        message=req.message,
        partner_name=memory.partner_name or "your partner",
        favorite_food=memory.favorite_food or "their favorite food",
    )

    try:
        data = await llm.complete_json(ALFRED_PERSONA, prompt)
    except LLMError as exc:
        logger.error("Chat completion failed: %s", exc)
        return _finalize_chat(
            req, sessions, session_id, session_status, memory,
            reply="I'm having trouble thinking that through right now — could you try again in a moment?",
            intent=intent, confidence=0.3,
        )

    actions = [ActionRequest(**a) for a in data.get("actions", []) if a.get("action")]
    memory_updates = sanitize_memory_updates(data.get("memory_updates", []))

    return _finalize_chat(
        req, sessions, session_id, session_status, memory,
        reply=data.get("reply", ""),
        intent=intent,
        confidence=float(data.get("confidence", intent_confidence)),
        actions=actions,
        memory_updates=memory_updates,
    )


def _finalize_chat(
    req: ChatRequest, sessions: Optional[SessionStore], session_id: Optional[str],
    session_status: Optional[SessionStatus], memory: UserMemory,
    *, reply: str, intent: Intent, confidence: float,
    actions: Optional[List[ActionRequest]] = None,
    recommendations: Optional[List[Recommendation]] = None,
    memory_updates: Optional[List[Any]] = None,
    timeline: Optional[List[TimelineStep]] = None,
    estimated_cost: Optional[float] = None,
    tips: Optional[List[str]] = None,
) -> ChatResponse:
    """Persists the turn + any memory updates to the session (if one is active)
    and builds the ChatResponse. Centralized so every return path in handle_chat
    saves state the same way — easy to miss one if inlined at each call site."""
    memory_updates = memory_updates or []
    if sessions and session_id:
        sessions.append_turn(session_id, "user", req.message)
        sessions.append_turn(session_id, "assistant", reply)
        if memory_updates:
            memory = sessions.merge_memory(session_id, memory_updates)

    return ChatResponse(
        session_id=session_id,
        session_status=session_status,
        reply=reply,
        intent=intent,
        confidence=confidence,
        actions=actions or [],
        recommendations=recommendations or [],
        memory_updates=memory_updates,
        timeline=timeline or [],
        estimated_cost=estimated_cost,
        tips=tips or [],
    )


# ---------------------------------------------------------------------------
# /recommend
# ---------------------------------------------------------------------------

async def _fetch_place_results(search: SerpAPIClient, category: str, location: str, preferences: Optional[str], currency: Optional[str] = None) -> List[Dict[str, Any]]:
    query = f"{category}" + (f" {preferences}" if preferences else "") + f" in {location}"
    try:
        return await search.search_places(query, location, currency=currency)
    except SearchError:
        return []


async def handle_recommend(
    req: RecommendRequest, llm: BaseLLMClient, search: SerpAPIClient,
    history: Optional[List[Dict[str, str]]] = None,
) -> RecommendResponse:
    category = req.category.value

    if category == "hotel":
        raw_results = await search.search_places(f"hotels in {req.location}", req.location, currency=req.currency)
    elif category == "event":
        try:
            raw_results = await search.search_events(req.preferences or "local", req.location, currency=req.currency)
        except SearchError:
            raw_results = []
    else:
        raw_results = await _fetch_place_results(search, category, req.location, req.preferences, req.currency)

    if not raw_results:
        prompt = NO_SEARCH_RESULTS_PROMPT.format(
            persona=ALFRED_PERSONA,
            category=category,
            location=req.location,
            budget=_budget_text(req.budget, req.currency),
            memory_block=format_memory_block(req.memory),
        )
        try:
            data = await llm.complete_json(ALFRED_PERSONA, prompt)
        except LLMError:
            data = {"reply": "I couldn't pull live results just now, and I don't want to guess at real venues — want me to try again shortly?", "confidence": 0.3}
        return RecommendResponse(recommendations=[], reply=data.get("reply", ""), confidence=float(data.get("confidence", 0.4)))

    prompt = RANK_RECOMMENDATIONS_PROMPT.format(
        persona=ALFRED_PERSONA,
        memory_block=format_memory_block(req.memory),
        budget=_budget_text(req.budget, req.currency),
        category=category,
        location=req.location,
        preferences=req.preferences or "none stated",
        search_results=raw_results,
        history=_history_text(history or []),
        details_instruction=DETAILS_INSTRUCTION,
    )
    try:
        data = await llm.complete_json(ALFRED_PERSONA, prompt)
    except LLMError:
        # Fall back to raw, unranked results rather than fabricating anything.
        recs = [Recommendation(**{**r, "category": category, "source": "serpapi"}) for r in raw_results[:5] if r.get("name")]
        return RecommendResponse(recommendations=recs, reply="Here's what I found nearby.", confidence=0.4)

    recs = [Recommendation(**{**r, "category": r.get("category") or category, "source": "serpapi"}) for r in data.get("recommendations", [])]
    return RecommendResponse(recommendations=recs, reply=data.get("reply", ""), confidence=float(data.get("confidence", 0.6)))


# ---------------------------------------------------------------------------
# /plan-date
# ---------------------------------------------------------------------------

async def handle_plan_date(
    req: PlanDateRequest, llm: BaseLLMClient, search: SerpAPIClient,
    history: Optional[List[Dict[str, str]]] = None,
) -> PlanDateResponse:
    # Independent searches — run concurrently instead of paying for both round-trips serially.
    restaurants, activities = await asyncio.gather(
        _fetch_place_results(search, "restaurant", req.location, req.preferences, req.currency),
        _fetch_place_results(search, "activity", req.location, req.preferences, req.currency),
    )

    if req.num_options > 1:
        return await _handle_plan_date_options(req, llm, restaurants, activities, history)

    prompt = PLAN_DATE_PROMPT.format(
        persona=ALFRED_PERSONA,
        memory_block=format_memory_block(req.memory),
        calendar_block=format_calendar_block(req.calendar),
        budget=_budget_text(req.budget, req.currency),
        location=req.location,
        date_type=req.date_type or "date",
        preferences=req.preferences or "none stated",
        restaurant_results=restaurants or "none available",
        activity_results=activities or "none available",
        history=_history_text(history or []),
        details_instruction=DETAILS_INSTRUCTION,
    )

    try:
        data = await llm.complete_json(ALFRED_PERSONA, prompt)
    except LLMError as exc:
        logger.error("Plan-date completion failed: %s", exc)
        return PlanDateResponse(
            reply="I couldn't put together a full plan just now — mind trying again in a moment?",
            timeline=[],
            confidence=0.3,
        )

    restaurant = Recommendation(**data["restaurant"]) if data.get("restaurant") and data["restaurant"].get("name") else None
    activity = Recommendation(**data["activity"]) if data.get("activity") and data["activity"].get("name") else None

    timeline = []
    for t in data.get("timeline", []):
        step_fields = dict(t)
        venue_tag = step_fields.pop("venue", None)
        step = TimelineStep(**step_fields)
        if venue_tag == "restaurant":
            step.recommendation = restaurant
        elif venue_tag == "activity":
            step.recommendation = activity
        timeline.append(step)

    actions = [ActionRequest(**a) for a in data.get("actions", []) if a.get("action")]
    memory_updates = sanitize_memory_updates(data.get("memory_updates", []))

    return PlanDateResponse(
        reply=data.get("reply", ""),
        timeline=timeline,
        restaurant=restaurant,
        activity=activity,
        estimated_cost=data.get("estimated_cost"),
        travel_notes=data.get("travel_notes"),
        actions=actions,
        memory_updates=memory_updates,
        confidence=float(data.get("confidence", 0.6)),
    )


def _parse_option_timeline(raw_timeline: List[Dict[str, Any]]) -> List[TimelineStep]:
    """Parses one date-option's timeline steps. Unlike the single-plan path
    (one restaurant + one activity shared by the whole plan, looked up by a
    "venue" tag), different options can use different or overlapping venues —
    so each step's recommendation is embedded inline via "venue_details"
    rather than looked up from a single top-level pair."""
    steps = []
    for t in raw_timeline:
        step_fields = dict(t)
        step_fields.pop("venue", None)
        venue_details = step_fields.pop("venue_details", None)
        step = TimelineStep(**step_fields)
        if venue_details and venue_details.get("name"):
            step.recommendation = Recommendation(**venue_details)
        steps.append(step)
    return steps


async def _handle_plan_date_options(
    req: PlanDateRequest, llm: BaseLLMClient,
    restaurants: List[Dict[str, Any]], activities: List[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]],
) -> PlanDateResponse:
    """Figma's 'Recommended Date Ideas' browsing list: several distinct,
    COMPLETE date plans (each with its own full timeline) so the caller can
    render either the browsing cards or a picked option's full plan straight
    from this one response, with no second API call needed."""
    prompt = PLAN_DATE_OPTIONS_PROMPT.format(
        persona=ALFRED_PERSONA,
        memory_block=format_memory_block(req.memory),
        calendar_block=format_calendar_block(req.calendar),
        budget=_budget_text(req.budget, req.currency),
        location=req.location,
        date_type=req.date_type or "date",
        preferences=req.preferences or "none stated",
        restaurant_results=restaurants or "none available",
        activity_results=activities or "none available",
        num_options=req.num_options,
        details_instruction=DETAILS_INSTRUCTION,
    )
    try:
        # This is the single most token-hungry call in the service: several
        # COMPLETE plans in one response, each with its own multi-step
        # timeline and embedded venue details. The default budget (sized for
        # a normal chat reply) truncates this mid-JSON well before it
        # finishes, so scale the request up with the number of options asked
        # for rather than reusing the shared default.
        data = await llm.complete_json(ALFRED_PERSONA, prompt, max_tokens=min(8000, 1500 + req.num_options * 1500))
    except LLMError as exc:
        logger.error("Plan-date options completion failed: %s", exc)
        return PlanDateResponse(
            reply="I couldn't put together date ideas just now — mind trying again in a moment?",
            confidence=0.3,
        )

    options = []
    for o in data.get("options", []):
        if not o.get("name"):
            continue
        option_fields = dict(o)
        option_fields["timeline"] = _parse_option_timeline(option_fields.pop("timeline", []))
        options.append(PlanOption(**option_fields))

    return PlanDateResponse(
        reply=data.get("reply", ""),
        options=options,
        confidence=float(data.get("confidence", 0.6)),
    )


# ---------------------------------------------------------------------------
# /coach
# ---------------------------------------------------------------------------

async def handle_coach(req: CoachRequest, llm: BaseLLMClient) -> CoachResponse:
    prompt = COACH_PROMPT.format(
        persona=ALFRED_PERSONA,
        topic=req.topic.value,
        memory_block=format_memory_block(req.memory),
        history=_history_text(req.conversation_history),
        message=req.message or "",
    )
    try:
        data = await llm.complete_json(ALFRED_PERSONA, prompt)
    except LLMError:
        return CoachResponse(reply="I'm having trouble pulling that together right now — try again in a moment?", tips=[], confidence=0.3)

    return CoachResponse(
        reply=data.get("reply", ""),
        tips=list(data.get("tips", [])),
        confidence=float(data.get("confidence", 0.6)),
    )


# ---------------------------------------------------------------------------
# /gift
# ---------------------------------------------------------------------------

async def handle_gift(
    req: GiftRequest, llm: BaseLLMClient, search: SerpAPIClient, exchange: ExchangeRateClient,
    history: Optional[List[Dict[str, str]]] = None,
) -> GiftResponse:
    location = req.location or "the user's area"
    # Preferences (what the user actually asked for, e.g. "something more
    # meaningful") take priority over generic memory-derived interests — using
    # only memory meant every gift request with the same memory/occasion/budget
    # produced the identical search query, and therefore identical cached
    # results, no matter what the user actually said in this turn.
    favorite = req.preferences or req.memory.favorite_activity or req.memory.favorite_food or "unique"
    budget_hint = f" under {req.budget} {req.currency}" if req.budget is not None else ""
    query = f"{favorite} gift ideas" + (f" for {req.occasion}" if req.occasion else "") + budget_hint

    budget_usd: Optional[float] = None
    if req.budget is not None:
        try:
            budget_usd = await exchange.convert(req.budget, req.currency, "USD")
        except ExchangeError as exc:
            logger.warning("Currency conversion for gift budget failed (%s); searching without a price filter", exc)

    try:
        raw_results = await search.search_products(query, req.location)
    except SearchError:
        raw_results = []

    if budget_usd is not None:
        # Google's own price-range filter turned out to be unreliable (see
        # search_products) — filter on the real extracted price ourselves so
        # results actually respect the budget instead of just mentioning it.
        raw_results = [r for r in raw_results if r.get("extracted_price_usd") is not None and r["extracted_price_usd"] <= budget_usd]
        raw_results.sort(key=lambda r: r["extracted_price_usd"], reverse=True)
    raw_results = raw_results[:5]

    if raw_results:
        raw_results = await _localize_product_prices(raw_results, exchange, req.currency)

    prompt = GIFT_PROMPT.format(
        persona=ALFRED_PERSONA,
        memory_block=format_memory_block(req.memory),
        occasion=req.occasion or "not specified",
        budget=_budget_text(req.budget, req.currency),
        location=location,
        search_results=raw_results or "none available",
        history=_history_text(history or []),
        details_instruction=DETAILS_INSTRUCTION,
    )
    try:
        data = await llm.complete_json(ALFRED_PERSONA, prompt)
    except LLMError:
        return GiftResponse(reply="I couldn't pull gift ideas together right now — want me to try again shortly?", recommendations=[], confidence=0.3)

    recs = [Recommendation(**{**r, "category": "gift", "source": "serpapi" if raw_results else "general_advice"}) for r in data.get("recommendations", [])]
    memory_updates = sanitize_memory_updates(data.get("memory_updates", []))

    return GiftResponse(
        reply=data.get("reply", ""),
        recommendations=recs,
        confidence=float(data.get("confidence", 0.6)),
        memory_updates=memory_updates,
    )


# ---------------------------------------------------------------------------
# /travel
# ---------------------------------------------------------------------------

async def _resolve_airport_code(llm: BaseLLMClient, place: str) -> Optional[str]:
    """Google Flights (via SerpAPI) requires a strict IATA 3-letter code, not a
    free-text city name — origin/destination in TravelRequest are plain city
    names, so ask the LLM to resolve the real airport code before searching,
    rather than passing the city straight through and always getting a 400."""
    try:
        data = await llm.complete_json(ALFRED_PERSONA, AIRPORT_CODE_PROMPT.format(place=place))
    except LLMError:
        return None
    code = data.get("code")
    if isinstance(code, str) and len(code) == 3 and code.isalpha():
        return code.upper()
    return None


async def _search_hotels_safe(search: SerpAPIClient, req: TravelRequest) -> List[Dict[str, Any]]:
    try:
        return await search.search_hotels(req.destination, req.start_date, req.end_date, currency=req.currency)
    except SearchError:
        return []


async def _search_activities_safe(search: SerpAPIClient, req: TravelRequest) -> List[Dict[str, Any]]:
    try:
        return await search.search_places(f"things to do in {req.destination}", req.destination, currency=req.currency)
    except SearchError:
        return []


async def handle_travel(req: TravelRequest, llm: BaseLLMClient, search: SerpAPIClient) -> TravelResponse:
    # Airport-code resolution (2 LLM calls) and hotel/activity search (2 SerpAPI
    # calls) are all independent of each other — run concurrently rather than
    # paying for four sequential round-trips.
    origin_code, destination_code, hotels, activities = await asyncio.gather(
        _resolve_airport_code(llm, req.origin),
        _resolve_airport_code(llm, req.destination),
        _search_hotels_safe(search, req),
        _search_activities_safe(search, req),
    )

    flights: List[Dict[str, Any]] = []
    if origin_code and destination_code:
        try:
            flights = await search.search_flights(origin_code, destination_code, req.start_date, req.end_date, currency=req.currency)
        except SearchError:
            flights = []
    else:
        logger.warning("Could not resolve airport codes for %r -> %r; skipping live flight search", req.origin, req.destination)

    prompt = TRAVEL_PROMPT.format(
        persona=ALFRED_PERSONA,
        memory_block=format_memory_block(req.memory),
        origin=req.origin,
        destination=req.destination,
        start_date=req.start_date,
        end_date=req.end_date,
        budget=_budget_text(req.budget, req.currency),
        preferences=req.preferences or "none stated",
        flight_results=flights or "none available",
        hotel_results=hotels or "none available",
        activity_results=activities or "none available",
        details_instruction=DETAILS_INSTRUCTION,
    )
    try:
        data = await llm.complete_json(ALFRED_PERSONA, prompt)
    except LLMError:
        return TravelResponse(reply="I couldn't put together the travel plan just now — want me to try again shortly?", confidence=0.3)

    actions = [ActionRequest(**a) for a in data.get("actions", []) if a.get("action")]

    return TravelResponse(
        reply=data.get("reply", ""),
        flights=[Recommendation(**{**f, "category": "flight"}) for f in data.get("flights", [])],
        hotels=[Recommendation(**{**h, "category": "hotel"}) for h in data.get("hotels", [])],
        activities=[Recommendation(**{**a, "category": "activity"}) for a in data.get("activities", [])],
        estimated_cost=data.get("estimated_cost"),
        actions=actions,
        confidence=float(data.get("confidence", 0.6)),
    )


async def handle_budget_analysis(req: ExpenseAnalysisRequest, llm: BaseLLMClient) -> ExpenseAnalysisResponse:
    prev_expenses_str = "\n".join(
        [
            f"- {item.category}: {req.currency} {item.amount} at {item.merchant or 'N/A'} (Date: {item.date or 'N/A'}, Notes: {item.notes or 'N/A'})"
            for item in req.previous_month_expenses
        ]
    ) if req.previous_month_expenses else "None provided in structured array"

    prompt = EXPENSE_ANALYSIS_SYSTEM_PROMPT.format(
        persona=ALFRED_PERSONA,
        memory_block=format_memory_block(req.memory),
        currency=req.currency,
        current_budget=_budget_text(req.current_budget, req.currency),
        notes=req.notes or "None",
        expenses_text=req.expenses_text or "See attached document or structured array",
        previous_month_expenses=prev_expenses_str,
    )

    try:
        data = await llm.complete_multimodal_json(
            ALFRED_PERSONA,
            prompt,
            file_base64=req.file_base64,
            file_type=req.file_type,
            max_tokens=8000,  # itemizes every transaction; long statements overflow small limits mid-JSON
        )
    except LLMError as exc:
        logger.error("Budget analysis LLM error: %s", exc)
        return ExpenseAnalysisResponse(
            reply="I ran into an issue analyzing the expense data. Please ensure the document is clear and try again.",
            confidence=0.0,
        )

    raw_expenses = [ExpenseItem(**e) for e in data.get("analyzed_expenses", []) if isinstance(e, dict)]
    seen_signatures = set()
    deduped_expenses: List[ExpenseItem] = []
    deduped_count = 0

    for exp in raw_expenses:
        sig_date = str(exp.date or "").strip().lower()
        sig_amt = round(float(exp.amount), 2)
        sig_merch = str(exp.merchant or exp.notes or "").strip().lower()
        sig = (sig_date, sig_amt, sig_merch)
        if sig in seen_signatures:
            deduped_count += 1
            continue
        seen_signatures.add(sig)
        deduped_expenses.append(exp)

    receipt_sum_raw = data.get("receipt_summary")
    if isinstance(receipt_sum_raw, dict):
        receipt_summary = ReceiptSummary(**{
            **receipt_sum_raw,
            "item_count": len(deduped_expenses) if deduped_expenses else receipt_sum_raw.get("item_count", 0),
            "deduplicated_count": deduped_count,
        })
    else:
        receipt_summary = ReceiptSummary(
            total_expense=sum(e.amount for e in deduped_expenses) if deduped_expenses else 0.0,
            currency=req.currency,
            item_count=len(deduped_expenses),
            deduplicated_count=deduped_count,
        )

    spending_breakdown = [SpendingBreakdownItem(**s) for s in data.get("spending_breakdown", []) if isinstance(s, dict)]

    next_month_raw = data.get("next_month_plan")
    next_month_plan = None
    if isinstance(next_month_raw, dict):
        allocs = [BudgetAllocationItem(**a) for a in next_month_raw.get("suggested_allocations", []) if isinstance(a, dict)]
        next_month_plan = NextMonthPlan(
            estimated_total_budget=float(next_month_raw.get("estimated_total_budget", req.current_budget or 0.0)),
            currency=next_month_raw.get("currency", req.currency),
            weekly_spending_target=next_month_raw.get("weekly_spending_target"),
            projected_savings=next_month_raw.get("projected_savings"),
            suggested_allocations=allocs,
            planner_tips=[str(t) for t in next_month_raw.get("planner_tips", [])],
        )

    actions = [ActionRequest(**a) for a in data.get("actions", []) if isinstance(a, dict) and a.get("action")]
    mem_updates = [MemoryUpdate(**m) for m in data.get("memory_updates", []) if isinstance(m, dict) and m.get("key")]
    follow_up_questions = [str(q) for q in data.get("follow_up_questions", []) if q]

    return ExpenseAnalysisResponse(
        reply=str(data.get("reply", "Expense analysis completed.")),
        receipt_summary=receipt_summary,
        analyzed_expenses=deduped_expenses,
        spending_breakdown=spending_breakdown,
        major_expense_areas=[str(a) for a in data.get("major_expense_areas", [])],
        spending_patterns=[str(p) for p in data.get("spending_patterns", [])],
        insights_and_recommendations=[str(i) for i in data.get("insights_and_recommendations", [])],
        next_month_plan=next_month_plan,
        follow_up_questions=follow_up_questions,
        confidence=float(data.get("confidence", 0.9)),
        actions=actions,
        memory_updates=mem_updates,
    )

