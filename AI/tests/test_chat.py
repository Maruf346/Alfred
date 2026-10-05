def test_chat_does_not_crash_when_ai_proposes_budget_memory_update_with_units(client, auth_headers, fake_llm):
    # Reproduces a real production 500: the AI proposed memory_updates with
    # budget as "5000 BDT" (units baked into the string) instead of a plain
    # number, which crashed the whole request when saved to session memory.
    fake_llm.queue({"intent": "general_chat", "confidence": 0.8})
    fake_llm.queue({
        "reply": "Understood, I've noted your budget.",
        "confidence": 0.85,
        "memory_updates": [{"key": "budget", "value": "5000 BDT"}],
    })

    resp = client.post(
        "/chat",
        json={"message": "umm the budget is 5000 bdt", "session_id": "sess-budget-crash"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["memory_updates"][0]["key"] == "budget"


def test_chat_returns_structured_response(client, auth_headers, fake_llm):
    fake_llm.queue({"intent": "restaurant_search", "confidence": 0.85})
    fake_llm.queue({
        "reply": "Since Emily enjoys Italian food, here's a great pick nearby.",
        "confidence": 0.9,
        "actions": [{"action": "search_restaurants", "payload": {"location": "Indianapolis"}}],
        "memory_updates": [{"key": "favorite_food", "value": "Italian"}],
    })

    payload = {
        "message": "Find a nice Italian place for me and Emily",
        "conversation_id": "abc123",
        "memory": {"name": "Carl", "budget": 100, "partner_name": "Emily", "favorite_food": "Italian"},
        "budget": 100,
    }
    resp = client.post("/chat", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "restaurant_search"
    assert "Emily" in body["reply"]
    assert body["actions"][0]["action"] == "search_restaurants"
    assert body["memory_updates"][0]["key"] == "favorite_food"


def test_chat_rejects_empty_message(client, auth_headers):
    resp = client.post("/chat", json={"message": "  ", "conversation_id": "c1"}, headers=auth_headers)
    assert resp.status_code == 422


def test_chat_falls_back_gracefully_on_llm_error(client, auth_headers, fake_llm, monkeypatch):
    async def _boom(*args, **kwargs):
        from app.llm_client import LLMError
        raise LLMError("provider down")

    monkeypatch.setattr(fake_llm, "complete_json", _boom)

    resp = client.post(
        "/chat",
        json={"message": "hello", "conversation_id": "c1"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confidence"] <= 0.5


def test_chat_routes_restaurant_search_to_recommend_when_location_known(client, auth_headers, fake_llm, fake_search):
    fake_search._places = [{"name": "Trattoria Roma", "rating": 4.6, "address": "12 MG Road"}]
    fake_llm.queue({"intent": "restaurant_search", "confidence": 0.9})
    fake_llm.queue({
        "reply": "Trattoria Roma is a great pick for Italian food nearby.",
        "confidence": 0.88,
        "recommendations": [{"name": "Trattoria Roma", "rating": 4.6, "reason": "Highly rated Italian spot."}],
    })

    payload = {
        "message": "Find a nice Italian place",
        "location": {"city": "Mumbai", "country": "India"},
        "budget": 50,
    }
    resp = client.post("/chat", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "restaurant_search"
    assert body["recommendations"][0]["name"] == "Trattoria Roma"
    assert body["actions"] == []


def test_chat_routes_date_planning_to_plan_date_when_location_known(client, auth_headers, fake_llm, fake_search):
    fake_llm.queue({"intent": "date_planning", "confidence": 0.9})
    fake_llm.queue({
        "reply": "Here's a cozy evening plan within budget.",
        "confidence": 0.85,
        "timeline": [{"time": "19:00", "activity": "Dinner", "location": "Trattoria Roma"}],
        "restaurant": {"name": "Trattoria Roma", "rating": 4.6},
        "estimated_cost": 4500,
    })

    payload = {
        "message": "Plan a cozy date night for Friday, budget 5000",
        "location": {"city": "Dhaka", "country": "Bangladesh"},
        "budget": 5000,
    }
    resp = client.post("/chat", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "date_planning"
    assert body["timeline"][0]["activity"] == "Dinner"
    assert body["estimated_cost"] == 4500
    assert any(r["name"] == "Trattoria Roma" for r in body["recommendations"])


def test_chat_accepts_message_only_payload(client, auth_headers, fake_llm):
    fake_llm.queue({"intent": "small_talk", "confidence": 0.8})
    fake_llm.queue({"reply": "Hey there!", "confidence": 0.9, "actions": [], "memory_updates": []})

    resp = client.post(
        "/chat",
        json={"message": "hello"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "small_talk"


def test_chat_without_session_id_gets_one_generated(client, auth_headers, fake_llm):
    fake_llm.queue({"intent": "small_talk", "confidence": 0.8})
    fake_llm.queue({"reply": "Hey there!", "confidence": 0.9})

    resp = client.post("/chat", json={"message": "hello"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"]
    assert body["session_status"] == "new"


def test_chat_session_status_is_active_when_session_id_is_found(client, auth_headers, fake_llm):
    # Realistic flow: first call omits session_id (server mints one, status
    # "new"); the caller then reuses that *server-returned* id on later calls,
    # which should come back "active". (A caller-invented id that the server
    # never issued is indistinguishable from an expired one — see the
    # dedicated "expired" test below.)
    fake_llm.queue({"intent": "small_talk", "confidence": 0.8})
    fake_llm.queue({"reply": "Hey there!", "confidence": 0.9})
    resp1 = client.post("/chat", json={"message": "hello"}, headers=auth_headers)
    body1 = resp1.json()
    assert body1["session_status"] == "new"
    session_id = body1["session_id"]

    fake_llm.queue({"intent": "small_talk", "confidence": 0.8})
    fake_llm.queue({"reply": "Good to see you again!", "confidence": 0.9})
    resp2 = client.post("/chat", json={"message": "hi again", "session_id": session_id}, headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["session_status"] == "active"


def test_chat_session_status_is_expired_for_unknown_session_id(client, auth_headers, fake_llm):
    # A session_id that was never created (or was evicted after the idle TTL)
    # must be flagged as "expired" so the caller knows context was NOT carried
    # over, even though a response with that same session_id still comes back.
    fake_llm.queue({"intent": "small_talk", "confidence": 0.8})
    fake_llm.queue({"reply": "Hello there!", "confidence": 0.9})

    resp = client.post(
        "/chat",
        json={"message": "continuing our chat", "session_id": "never-seen-before-id"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == "never-seen-before-id"
    assert body["session_status"] == "expired"


def test_chat_expired_session_starts_with_no_prior_context(client, auth_headers, fake_llm):
    # Confirms an "expired" session_id doesn't silently smuggle in context from
    # a different, coincidentally-similar prior call — it should behave exactly
    # like a fresh conversation, not a partial/corrupted resume.
    fake_llm.queue({"intent": "restaurant_search", "confidence": 0.8})
    fake_llm.queue({"reply": "Which city would you like to search?", "confidence": 0.7})

    resp = client.post(
        "/chat",
        json={"message": "find a restaurant", "session_id": "expired-session-xyz"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_status"] == "expired"
    assert body["recommendations"] == []


def test_chat_remembers_prior_turns_across_calls_via_session_id(client, auth_headers, fake_llm):
    # Turn 1: ask about a restaurant with no location -> general chat branch,
    # Alfred asks a follow-up question (simulated via the queued reply).
    fake_llm.queue({"intent": "restaurant_search", "confidence": 0.7})
    fake_llm.queue({"reply": "Certainly — which city shall I search near?", "confidence": 0.6})

    resp1 = client.post(
        "/chat",
        json={"message": "Find a nice restaurant for us", "session_id": "sess-1"},
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["session_id"] == "sess-1"

    # Turn 2: user answers the follow-up with just the city, no history resent.
    # The intent classifier call receives history — assert it now contains turn 1.
    fake_llm.queue({"intent": "small_talk", "confidence": 0.7})
    fake_llm.queue({"reply": "Wonderful, allow me a moment.", "confidence": 0.8})

    resp2 = client.post(
        "/chat",
        json={"message": "Mumbai", "session_id": "sess-1"},
        headers=auth_headers,
    )
    assert resp2.status_code == 200

    # The intent-detection prompt for turn 2 is the 3rd LLM call overall;
    # it should embed turn 1's user message and Alfred's reply as prior history.
    intent_prompt_turn2 = fake_llm.calls[2]
    assert "Find a nice restaurant for us" in intent_prompt_turn2
    assert "which city shall I search near" in intent_prompt_turn2


def test_chat_routes_event_search_to_recommend_without_requiring_budget(client, auth_headers, fake_llm, fake_search):
    # No budget given anywhere — events must NOT be gated on budget the way
    # restaurant/activity/gift are, since "what's on this weekend" shouldn't
    # require answering a budget question first.
    fake_search._events = [{"name": "Jazz Night", "price_level": "Fri, Aug 1, 8PM", "address": "Blue Room, Mumbai"}]
    fake_llm.queue({"intent": "event_search", "confidence": 0.9, "location_city": "Mumbai"})
    fake_llm.queue({
        "reply": "Jazz Night looks like a great pick this weekend.",
        "recommendations": [{"name": "Jazz Night", "reason": "Live music, well-reviewed venue."}],
        "confidence": 0.85,
    })

    resp = client.post(
        "/chat",
        json={"message": "any concerts happening in Mumbai this weekend?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "event_search"
    assert body["recommendations"], "expected a real event search, not a follow-up question"
    assert body["recommendations"][0]["name"] == "Jazz Night"


def test_chat_hotel_search_asks_for_budget_when_unknown(client, auth_headers, fake_llm):
    # Unlike events, hotels ARE budget-gated (price is a real filtering
    # criterion for lodging) — must ask rather than search unfiltered.
    fake_llm.queue({"intent": "hotel_search", "confidence": 0.85, "location_city": "Goa"})
    fake_llm.queue({"reply": "What budget did you have in mind for the stay?", "confidence": 0.7})

    resp = client.post(
        "/chat",
        json={"message": "find me a hotel in Goa"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "hotel_search"
    assert body["recommendations"] == []
    assert "budget" in body["reply"].lower()


def test_chat_routes_hotel_search_to_recommend_when_budget_known(client, auth_headers, fake_llm, fake_search):
    fake_search._places = [{"name": "Seaside Resort Goa", "rating": 4.5, "price_level": "$80/night"}]
    fake_llm.queue({"intent": "hotel_search", "confidence": 0.9, "location_city": "Goa", "budget_amount": 100})
    fake_llm.queue({
        "reply": "Seaside Resort Goa is a lovely option within budget.",
        "recommendations": [{"name": "Seaside Resort Goa", "rating": 4.5, "reason": "Great value near the beach."}],
        "confidence": 0.85,
    })

    resp = client.post(
        "/chat",
        json={"message": "find me a hotel in Goa, budget $100 a night"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "hotel_search"
    assert body["recommendations"], "expected a real hotel search once budget was known"
    assert body["recommendations"][0]["name"] == "Seaside Resort Goa"


def test_chat_remembers_city_and_routes_to_recommend_on_bare_followup(client, auth_headers, fake_llm, fake_search):
    # Turn 1: user mentions a city — intent classifier extracts it as location_city
    # even though no structured `location` field is sent in the request.
    fake_llm.queue({"intent": "restaurant_search", "confidence": 0.8, "location_city": "Dhaka"})
    fake_llm.queue({"reply": "Might I ask what you're in the mood for?", "confidence": 0.7})

    resp1 = client.post(
        "/chat",
        json={"message": "I'm looking for restaurants in Dhaka", "session_id": "sess-city", "budget": 40},
        headers=auth_headers,
    )
    assert resp1.status_code == 200

    # Turn 2: bare "just suggest something", no location or budget resent —
    # this is the exact bug reported: Alfred must still remember "Dhaka" (and
    # the budget given in turn 1) from session state, and actually call the
    # recommend flow, not just talk about it.
    fake_search._places = [{"name": "Kasturi", "rating": 4.5, "address": "Gulshan, Dhaka"}]
    fake_llm.queue({"intent": "restaurant_search", "confidence": 0.9, "location_city": "Dhaka"})
    fake_llm.queue({
        "reply": "Kasturi is a fine choice.",
        "confidence": 0.85,
        "recommendations": [{"name": "Kasturi", "rating": 4.5, "reason": "Highly rated."}],
    })

    resp2 = client.post(
        "/chat",
        json={"message": "just suggest a restaurant, no details needed", "session_id": "sess-city"},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["intent"] == "restaurant_search"
    # Must have actually routed to the recommend flow and returned a real result,
    # not just an unexecuted "actions" proposal with empty recommendations.
    assert body2["recommendations"], "expected a real recommendation, not an empty list"
    assert body2["recommendations"][0]["name"] == "Kasturi"


def test_chat_gift_query_changes_across_turns_via_session_message(client, auth_headers, fake_llm, fake_search):
    # Reproduces the original reported bug (two gift follow-ups must produce
    # different SerpAPI queries, not an identical cached-looking result twice)
    # WITHOUT reintroducing the raw-message-as-query bug found later: the
    # query must come from the classifier's distilled search_keywords, never
    # req.message verbatim, since a raw message can contain filler/logistics
    # text that breaks the search query outright.
    fake_llm.queue({"intent": "gift_suggestions", "confidence": 0.9, "budget_amount": 50, "search_keywords": None})
    fake_llm.queue({"reply": "Here are some ideas.", "recommendations": [], "confidence": 0.8})
    client.post(
        "/chat",
        json={"message": "do you have any suggestions what to take for her, budget 50", "session_id": "sess-gift-repeat"},
        headers=auth_headers,
    )

    fake_llm.queue({"intent": "gift_suggestions", "confidence": 0.9, "search_keywords": "sentimental, meaningful keepsake"})
    fake_llm.queue({"reply": "Here's something more meaningful.", "recommendations": [], "confidence": 0.8})
    client.post(
        "/chat",
        json={"message": "something more meaningful?", "session_id": "sess-gift-repeat"},
        headers=auth_headers,
    )

    assert len(fake_search.product_queries) == 2
    assert fake_search.product_queries[0] != fake_search.product_queries[1]
    assert "sentimental, meaningful keepsake" in fake_search.product_queries[1]
    # The raw, punctuation-laden user message must never leak into the query.
    assert "something more meaningful?" not in fake_search.product_queries[1]


def test_chat_treats_explicit_no_budget_limit_as_answered(client, auth_headers, fake_llm, fake_search):
    # User states city + occasion AND explicitly says budget isn't a concern —
    # there's no number to extract, but the budget question has still been
    # answered, so this must route straight to a real search, not ask again.
    fake_search._places = [{"name": "Nile View Restaurant", "rating": 4.7, "address": "Cairo"}]
    fake_llm.queue({
        "intent": "restaurant_search", "confidence": 0.95,
        "location_city": "Cairo", "budget_amount": None, "budget_no_limit": True,
    })
    fake_llm.queue({
        "reply": "A candlelight dinner in Cairo sounds delightful.",
        "confidence": 0.9,
        "recommendations": [{"name": "Nile View Restaurant", "rating": 4.7, "reason": "Romantic ambiance."}],
    })

    resp = client.post(
        "/chat",
        json={"message": "i live in cairo and i want candle light dinner, budget is not a concern"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "restaurant_search"
    assert body["recommendations"], "expected a real search once 'no budget limit' was recognized as answered"
    assert body["recommendations"][0]["name"] == "Nile View Restaurant"


def test_chat_routes_travel_planning_to_handle_travel_when_all_slots_known(client, auth_headers, fake_llm, fake_search):
    fake_search._flights = [{"name": "Delta / United", "price_level": "$320"}]
    fake_search._hotels = [{"name": "Riverside Inn", "rating": 4.2}]
    fake_llm.queue({
        "intent": "travel_planning", "confidence": 0.9,
        "travel_origin": "Indianapolis", "travel_destination": "Chicago",
        "travel_start_date": "2026-08-01", "travel_end_date": "2026-08-03",
    })
    fake_llm.queue({"code": "IND"})
    fake_llm.queue({"code": "ORD"})
    fake_llm.queue({
        "reply": "Here's a weekend getaway plan within your budget.",
        "flights": [{"name": "Delta / United", "category": "flight", "price_level": "$320"}],
        "hotels": [{"name": "Riverside Inn", "category": "hotel", "rating": 4.2}],
        "activities": [],
        "estimated_cost": 750,
        "confidence": 0.82,
    })

    resp = client.post(
        "/chat",
        json={
            "message": "Plan a trip from Indianapolis to Chicago, Aug 1 to Aug 3",
            "origin": "Indianapolis", "destination": "Chicago",
            "start_date": "2026-08-01", "end_date": "2026-08-03",
            "budget": 800,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "travel_planning"
    assert any(r["name"] == "Delta / United" for r in body["recommendations"])
    assert any(r["name"] == "Riverside Inn" for r in body["recommendations"])
    assert body["estimated_cost"] == 750


def test_chat_travel_planning_asks_followup_when_dates_missing(client, auth_headers, fake_llm):
    # Only origin/destination known, no dates yet — must not call handle_travel
    # (which requires all 4 fields); should fall through to a follow-up question.
    fake_llm.queue({
        "intent": "travel_planning", "confidence": 0.7,
        "travel_origin": "Indianapolis", "travel_destination": "Chicago",
        "travel_start_date": None, "travel_end_date": None,
    })
    fake_llm.queue({"reply": "Certainly — what dates did you have in mind?", "confidence": 0.6})

    resp = client.post(
        "/chat",
        json={"message": "I want to go from Indianapolis to Chicago"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "travel_planning"
    assert body["recommendations"] == []
    assert "dates" in body["reply"].lower()


def test_chat_remembers_travel_slots_across_turns_via_session_id(client, auth_headers, fake_llm, fake_search):
    fake_llm.queue({
        "intent": "travel_planning", "confidence": 0.7,
        "travel_origin": "Indianapolis", "travel_destination": "Chicago",
        "travel_start_date": None, "travel_end_date": None,
    })
    fake_llm.queue({"reply": "What dates did you have in mind?", "confidence": 0.6})

    resp1 = client.post(
        "/chat",
        json={"message": "Plan a trip from Indianapolis to Chicago", "session_id": "sess-travel", "budget": 800},
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["recommendations"] == []

    # Turn 2: only supplies dates — origin/destination/budget must be recalled from session.
    fake_search._flights = [{"name": "Delta / United", "price_level": "$320"}]
    fake_search._hotels = [{"name": "Riverside Inn", "rating": 4.2}]
    fake_llm.queue({
        "intent": "travel_planning", "confidence": 0.9,
        "travel_origin": None, "travel_destination": None,
        "travel_start_date": "2026-08-01", "travel_end_date": "2026-08-03",
    })
    fake_llm.queue({"code": "IND"})
    fake_llm.queue({"code": "ORD"})
    fake_llm.queue({
        "reply": "Here's your plan.",
        "flights": [{"name": "Delta / United", "category": "flight"}],
        "hotels": [{"name": "Riverside Inn", "category": "hotel"}],
        "activities": [],
        "confidence": 0.85,
    })

    resp2 = client.post(
        "/chat",
        json={"message": "August 1st to August 3rd", "session_id": "sess-travel"},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["intent"] == "travel_planning"
    assert any(r["name"] == "Delta / United" for r in body2["recommendations"])


def test_chat_gift_suggestions_asks_for_budget_when_unknown(client, auth_headers, fake_llm, fake_search):
    # No budget anywhere (request, session, memory) — must NOT call handle_gift
    # (which would silently search unfiltered); should ask instead.
    fake_search._products = [{"name": "Should Not Appear", "extracted_price_usd": 9999}]
    fake_llm.queue({"intent": "gift_suggestions", "confidence": 0.9})
    fake_llm.queue({"reply": "Of course — what budget did you have in mind?", "confidence": 0.7})

    resp = client.post(
        "/chat",
        json={"message": "what should i take for her?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "gift_suggestions"
    assert body["recommendations"] == []
    assert "budget" in body["reply"].lower()


def test_chat_gift_suggestions_completes_when_budget_given_as_freetext_followup(client, auth_headers, fake_llm, fake_search):
    # Turn 1: gift request, no budget -> asks.
    fake_llm.queue({"intent": "gift_suggestions", "confidence": 0.9, "budget_amount": None})
    fake_llm.queue({"reply": "What budget did you have in mind?", "confidence": 0.7})

    resp1 = client.post(
        "/chat",
        json={"message": "what should i take for her?", "session_id": "sess-gift-budget"},
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["recommendations"] == []

    # Turn 2: bare free-text budget answer, e.g. "around 50 dollars" — the intent
    # classifier must both (a) keep classifying this as gift_suggestions (it's a
    # continuation of Alfred's own question) and (b) extract 50 as budget_amount,
    # so the real gift search actually runs instead of staying stuck asking.
    fake_search._products = [{"name": "Cozy Candle Set", "extracted_price_usd": 30, "rating": 4.5}]
    fake_llm.queue({"intent": "gift_suggestions", "confidence": 0.9, "budget_amount": 50})
    fake_llm.queue({
        "reply": "A cozy candle set fits perfectly.",
        "recommendations": [{"name": "Cozy Candle Set", "rating": 4.5, "reason": "Fits the budget and her taste."}],
        "confidence": 0.85,
    })

    resp2 = client.post(
        "/chat",
        json={"message": "around 50 dollars, she likes cozy things", "session_id": "sess-gift-budget"},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert body2["intent"] == "gift_suggestions"
    assert body2["recommendations"], "expected a real search once budget was extracted from free text"


def test_chat_gift_suggestions_uses_budget_from_memory(client, auth_headers, fake_llm, fake_search):
    # Budget not in this request, but present in memory — should still route
    # to the real gift search rather than asking again.
    fake_search._products = [{"name": "Nice Mug", "extracted_price_usd": 20, "rating": 4.5}]
    fake_llm.queue({"intent": "gift_suggestions", "confidence": 0.9})
    fake_llm.queue({
        "reply": "Here's a thoughtful pick within your usual budget.",
        "recommendations": [{"name": "Nice Mug", "rating": 4.5, "reason": "Affordable and thoughtful."}],
        "confidence": 0.85,
    })

    resp = client.post(
        "/chat",
        json={"message": "what should i take for her?", "memory": {"budget": 30}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "gift_suggestions"
    assert body["recommendations"], "expected a real recommendation using memory.budget"


def test_chat_routes_coaching_to_handle_coach(client, auth_headers, fake_llm):
    fake_llm.queue({"intent": "coaching", "confidence": 0.85, "coach_topic": "texting_advice"})
    fake_llm.queue({
        "reply": "Give it a day before following up.",
        "tips": ["Don't double-text", "Keep it light", "Ask a question to invite a reply"],
        "confidence": 0.9,
    })

    resp = client.post(
        "/chat",
        json={"message": "She hasn't replied in two days, what should I say?"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "coaching"
    assert len(body["tips"]) == 3
    assert "Don't double-text" in body["tips"]
