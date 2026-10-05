def test_gift_query_changes_with_preferences_instead_of_repeating_memory_only_search(client, auth_headers, fake_llm, fake_search):
    # Same memory/occasion/budget across two calls, but different `preferences`
    # (what the user actually asked for this turn) — the search query sent to
    # SerpAPI must reflect that, or every follow-up returns identical cached
    # results regardless of what the user said next.
    fake_search._products = []
    fake_llm.queue({"reply": "Here are some ideas.", "recommendations": [], "confidence": 0.7})
    client.post(
        "/gift",
        json={"occasion": "birthday", "budget": 50, "memory": {"favorite_food": "Italian"}},
        headers=auth_headers,
    )

    fake_llm.queue({"reply": "Here's something more meaningful.", "recommendations": [], "confidence": 0.7})
    client.post(
        "/gift",
        json={
            "occasion": "birthday", "budget": 50, "memory": {"favorite_food": "Italian"},
            "preferences": "something more meaningful",
        },
        headers=auth_headers,
    )

    assert len(fake_search.product_queries) == 2
    assert fake_search.product_queries[0] != fake_search.product_queries[1]
    assert "something more meaningful" in fake_search.product_queries[1]


def test_gift_recommendations_use_memory(client, auth_headers, fake_llm, fake_search):
    fake_search._products = []
    fake_llm.queue({
        "reply": "Since Emily loves Italian food, a cooking class together could be a lovely anniversary gift.",
        "recommendations": [
            {"name": "Italian Cooking Class", "category": "gift", "reason": "Matches favorite food"},
        ],
        "confidence": 0.8,
        "memory_updates": [],
    })

    resp = client.post(
        "/gift",
        json={
            "occasion": "anniversary",
            "budget": 150,
            "memory": {"partner_name": "Emily", "favorite_food": "Italian"},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "Emily" in body["reply"]
    assert len(body["recommendations"]) == 1


def test_gift_uses_real_products_without_requiring_location(client, auth_headers, fake_llm, fake_search):
    fake_search._products = [
        {"name": "Personalized Star Map", "rating": 4.7, "price_level": "$45", "extracted_price_usd": 45.0},
        {"name": "Leather Journal Set", "rating": 4.5, "price_level": "$38", "extracted_price_usd": 38.0},
    ]
    fake_llm.queue({
        "reply": "Here are a couple of well-rated picks within your budget.",
        "recommendations": [
            {"name": "Personalized Star Map", "rating": 4.7, "price_level": "$45", "reason": "Unique and sentimental."},
            {"name": "Leather Journal Set", "rating": 4.5, "price_level": "$38", "reason": "Practical and thoughtful."},
        ],
        "confidence": 0.85,
        "memory_updates": [],
    })

    resp = client.post(
        "/gift",
        json={"occasion": "birthday", "budget": 50, "currency": "usd"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recommendations"]) == 2
    assert body["recommendations"][0]["source"] == "serpapi"


def test_gift_filters_out_of_budget_results_and_converts_currency(client, auth_headers, fake_llm, fake_search, fake_exchange):
    # 1 USD = 100 BDT for this test, so a 500 BDT budget = $5 real budget.
    fake_exchange._rates = {("BDT", "USD"): 0.01, ("USD", "BDT"): 100.0}
    fake_search._products = [
        {"name": "Mini Photo Frame", "rating": 4.6, "price_level": "$4.50", "extracted_price_usd": 4.50},  # in budget
        {"name": "Fancy Watch", "rating": 4.9, "price_level": "$45.00", "extracted_price_usd": 45.00},     # way over budget
    ]
    fake_llm.queue({
        "reply": "Here's a thoughtful pick within your budget.",
        "recommendations": [
            {"name": "Mini Photo Frame", "rating": 4.6, "price_level": "৳450.00", "reason": "Sweet and affordable."},
        ],
        "confidence": 0.85,
        "memory_updates": [],
    })

    resp = client.post(
        "/gift",
        json={"occasion": "birthday", "budget": 500, "currency": "bdt"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recommendations"]) == 1
    # Google's own price-range filter turned out to be unreliable, so filtering
    # happens on the real extracted price — the $45 item must never reach the
    # model at all, proving the budget is actually enforced, not just mentioned.
    assert not any("Fancy Watch" in call for call in fake_llm.calls)
    # The surviving $4.50 result should be converted back to BDT (450.00) in
    # what the "model" saw, not left in USD.
    assert any("450" in call for call in fake_llm.calls)
