def test_recommend_with_search_results(client, auth_headers, fake_llm, fake_search):
    fake_search._places = [
        {"name": "Trattoria Roma", "rating": 4.6, "price_level": "$$", "address": "123 Main St"},
    ]
    fake_llm.queue({
        "reply": "Trattoria Roma is a great fit for your budget.",
        "recommendations": [
            {"name": "Trattoria Roma", "category": "restaurant", "rating": 4.6, "price_level": "$$", "reason": "Fits your $100 budget nicely."},
        ],
        "confidence": 0.9,
    })

    resp = client.post(
        "/recommend",
        json={"category": "restaurant", "location": "Indianapolis", "budget": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recommendations"]) == 1
    assert body["recommendations"][0]["name"] == "Trattoria Roma"


def test_recommend_events_category_uses_search_events(client, auth_headers, fake_llm, fake_search):
    fake_search._events = [
        {"name": "Jazz Night at Blue Room", "price_level": "Fri, Aug 1, 8:00 PM", "address": "Blue Room, Mumbai"},
    ]
    fake_llm.queue({
        "reply": "Jazz Night at Blue Room looks like a lovely evening out.",
        "recommendations": [
            {"name": "Jazz Night at Blue Room", "category": "event", "reason": "Live music, well-reviewed venue."},
        ],
        "confidence": 0.85,
    })

    resp = client.post(
        "/recommend",
        json={"category": "event", "location": "Mumbai", "preferences": "live music"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recommendations"]) == 1
    assert body["recommendations"][0]["name"] == "Jazz Night at Blue Room"


def test_recommend_without_search_results_does_not_fabricate(client, auth_headers, fake_llm, fake_search):
    fake_search._places = []
    fake_llm.queue({
        "reply": "I couldn't find live results right now, but generally Italian spots near you tend to fit that budget.",
        "recommendations": [],
        "confidence": 0.5,
    })

    resp = client.post(
        "/recommend",
        json={"category": "restaurant", "location": "Indianapolis", "budget": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["recommendations"] == []
