def test_travel_plan_combines_flights_and_hotels(client, auth_headers, fake_llm, fake_search):
    fake_search._flights = [{"name": "Delta / United", "price_level": "$320"}]
    fake_search._hotels = [{"name": "Riverside Inn", "rating": 4.2}]
    fake_llm.queue({"code": "IND"})  # origin airport code resolution
    fake_llm.queue({"code": "ORD"})  # destination airport code resolution
    fake_llm.queue({
        "reply": "Here's a weekend getaway plan within your budget.",
        "flights": [{"name": "Delta / United", "category": "flight", "price_level": "$320"}],
        "hotels": [{"name": "Riverside Inn", "category": "hotel", "rating": 4.2}],
        "activities": [],
        "estimated_cost": 750,
        "actions": [],
        "confidence": 0.82,
    })

    resp = client.post(
        "/travel",
        json={
            "origin": "Indianapolis",
            "destination": "Chicago",
            "start_date": "2026-08-01",
            "end_date": "2026-08-03",
            "budget": 800,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["flights"][0]["name"] == "Delta / United"
    assert body["hotels"][0]["name"] == "Riverside Inn"
    assert body["estimated_cost"] == 750


def test_travel_skips_flight_search_when_airport_code_unresolvable(client, auth_headers, fake_llm, fake_search):
    fake_search._flights = [{"name": "Should Not Appear", "price_level": "$999"}]
    fake_llm.queue({"code": None})  # origin: LLM isn't confident
    fake_llm.queue({"code": "ORD"})  # destination resolves fine
    fake_llm.queue({
        "reply": "I couldn't find live flights, but here's general travel guidance.",
        "flights": [],
        "hotels": [],
        "activities": [],
        "confidence": 0.5,
    })

    resp = client.post(
        "/travel",
        json={
            "origin": "SomeUnrecognizablePlace",
            "destination": "Chicago",
            "start_date": "2026-08-01",
            "end_date": "2026-08-03",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    # Flight search must never have been called with a bad/city-name origin —
    # the fake would've returned "Should Not Appear" otherwise.
    assert body["flights"] == []
