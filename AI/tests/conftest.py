import json
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.config import get_settings
from app.exchange_client import ExchangeRateClient
from app.llm_client import BaseLLMClient
from app.search_client import SerpAPIClient

API_KEY = "test-key"


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch):
    monkeypatch.setenv("AI_SERVICE_API_KEY", API_KEY)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("SERPAPI_KEY", "")  # default: no live search in tests
    # Blank voice provider creds regardless of the developer's real .env, so
    # "not configured" tests are deterministic across machines.
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_session_store():
    from app.session_store import reset_session_store_for_tests

    reset_session_store_for_tests()
    yield
    reset_session_store_for_tests()


class FakeLLMClient(BaseLLMClient):
    """Returns canned JSON responses keyed by a substring match on the prompt,
    so each test can control exactly what "the model" says without any network call."""

    def __init__(self, responses: Optional[List[Dict[str, Any]]] = None):
        # responses is a queue consumed in order; simplest possible fake.
        self._queue: List[Dict[str, Any]] = list(responses or [])
        self.calls: List[str] = []
        self.max_tokens_used: List[Optional[int]] = []  # records each call's max_tokens override (or None)

    def queue(self, response: Dict[str, Any]) -> None:
        self._queue.append(response)

    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: Optional[int] = None) -> str:
        self.calls.append(user_prompt)
        self.max_tokens_used.append(max_tokens)
        if not self._queue:
            return json.dumps({"reply": "ok", "confidence": 0.9})
        return json.dumps(self._queue.pop(0))


class FakeSearchClient(SerpAPIClient):
    def __init__(self, places=None, flights=None, hotels=None, products=None, events=None):
        self._places = places if places is not None else []
        self._flights = flights if flights is not None else []
        self._hotels = hotels if hotels is not None else []
        self._products = products if products is not None else []
        self._events = events if events is not None else []
        self.product_queries: List[str] = []  # records each query search_products was called with

    async def search_places(self, query: str, location: str, currency=None):
        return self._places

    async def search_flights(self, origin: str, destination: str, start_date: str, end_date: str, currency=None):
        return self._flights

    async def search_hotels(self, destination: str, start_date: str, end_date: str, currency=None):
        return self._hotels

    async def search_products(self, query: str, location=None):
        self.product_queries.append(query)
        return self._products

    async def search_events(self, query: str, location: str, currency=None):
        return self._events


class FakeExchangeClient(ExchangeRateClient):
    """Identity conversion by default (rate 1.0 for any pair); tests can override
    specific pairs via `rates` to exercise real conversion math."""

    def __init__(self, rates=None):
        self._rates = rates or {}

    async def get_rate(self, from_currency: str, to_currency: str) -> float:
        from_currency, to_currency = from_currency.upper(), to_currency.upper()
        if from_currency == to_currency:
            return 1.0
        return self._rates.get((from_currency, to_currency), 1.0)

    async def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        rate = await self.get_rate(from_currency, to_currency)
        return round(amount * rate, 2)


@pytest.fixture
def fake_llm():
    return FakeLLMClient()


@pytest.fixture
def fake_search():
    return FakeSearchClient()


@pytest.fixture
def fake_exchange():
    return FakeExchangeClient()


@pytest.fixture
def client(monkeypatch, fake_llm, fake_search, fake_exchange):
    import app.exchange_client as exchange_module
    import app.llm_client as llm_module
    import app.search_client as search_module

    monkeypatch.setattr(llm_module, "get_llm_client", lambda: fake_llm)
    monkeypatch.setattr(search_module, "get_search_client", lambda: fake_search)
    monkeypatch.setattr(exchange_module, "get_exchange_client", lambda: fake_exchange)
    # Routers imported get_llm_client/get_search_client/get_exchange_client by
    # reference at import time, so patch each router module's bound name too.
    for mod in (main_module.chat, main_module.recommend, main_module.plan_date, main_module.coach, main_module.gift, main_module.travel, main_module.budget):
        if hasattr(mod, "get_llm_client"):
            monkeypatch.setattr(mod, "get_llm_client", lambda: fake_llm)
        if hasattr(mod, "get_search_client"):
            monkeypatch.setattr(mod, "get_search_client", lambda: fake_search)
        if hasattr(mod, "get_exchange_client"):
            monkeypatch.setattr(mod, "get_exchange_client", lambda: fake_exchange)

    return TestClient(main_module.app)


@pytest.fixture
def auth_headers():
    return {"X-API-Key": API_KEY}
