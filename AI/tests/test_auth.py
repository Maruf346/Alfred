import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _enforce_service_auth_for_auth_tests(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("REQUIRE_SERVICE_API_KEY_IN_DEV", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_chat_without_api_key_is_rejected(client):
    resp = client.post("/chat", json={"message": "hi", "conversation_id": "c1"})
    assert resp.status_code == 401


def test_chat_with_wrong_api_key_is_rejected(client):
    resp = client.post(
        "/chat",
        json={"message": "hi", "conversation_id": "c1"},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 401


def test_chat_with_correct_api_key_is_accepted(client, auth_headers, fake_llm):
    fake_llm.queue({"intent": "small_talk", "confidence": 0.8})
    fake_llm.queue({"reply": "Hey there!", "confidence": 0.9, "actions": [], "memory_updates": []})
    resp = client.post(
        "/chat",
        json={"message": "hi", "conversation_id": "c1"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
