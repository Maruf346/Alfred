def test_coach_returns_tips(client, auth_headers, fake_llm):
    fake_llm.queue({
        "reply": "First dates go best when you both stay curious and relaxed.",
        "tips": ["Ask open-ended questions", "Pick a low-pressure venue", "Put your phone away"],
        "confidence": 0.9,
    })

    resp = client.post(
        "/coach",
        json={"topic": "first_date"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["tips"]) == 3


def test_coach_invalid_topic_is_rejected(client, auth_headers):
    resp = client.post("/coach", json={"topic": "not_a_real_topic"}, headers=auth_headers)
    assert resp.status_code == 422
