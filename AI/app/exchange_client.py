"""
Live currency conversion via a free, keyless FX-rate API (open.er-api.com).

Rates are cached in-memory per base currency for a configurable TTL so we
don't hit the API on every request. Conversion never fabricates a rate — if
the API is unavailable and there's no usable cache, callers get ExchangeError
and must fall back gracefully (e.g. skip price filtering) rather than guess.
"""
import logging
import time
from typing import Dict, Optional, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings, get_settings
from app.http_client import get_http_client

logger = logging.getLogger("alfred.exchange")


class ExchangeError(Exception):
    pass


class ExchangeRateClient:
    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._cache: Dict[str, Tuple[float, Dict[str, float]]] = {}  # base -> (fetched_at, rates)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _fetch_rates(self, base: str) -> Dict[str, float]:
        url = f"{self._settings.exchange_rate_base_url}/{base}"
        client = get_http_client()
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        rates = data.get("rates")
        if not rates:
            raise ExchangeError(f"No rates returned for base {base!r}")
        return rates

    async def _get_rates(self, base: str) -> Dict[str, float]:
        base = base.upper()
        cached = self._cache.get(base)
        now = time.monotonic()
        if cached and (now - cached[0]) < self._settings.exchange_rate_cache_seconds:
            return cached[1]
        try:
            rates = await self._fetch_rates(base)
        except Exception as exc:  # noqa: BLE001
            logger.error("Exchange rate fetch failed for base %r: %s", base, exc)
            if cached:
                logger.warning("Using stale cached rates for %r after a failed refresh", base)
                return cached[1]
            raise ExchangeError(str(exc)) from exc
        self._cache[base] = (now, rates)
        return rates

    async def get_rate(self, from_currency: str, to_currency: str) -> float:
        from_currency, to_currency = from_currency.upper(), to_currency.upper()
        if from_currency == to_currency:
            return 1.0
        rates = await self._get_rates(from_currency)
        rate = rates.get(to_currency)
        if rate is None:
            raise ExchangeError(f"No rate from {from_currency} to {to_currency}")
        return rate

    async def convert(self, amount: float, from_currency: str, to_currency: str) -> float:
        rate = await self.get_rate(from_currency, to_currency)
        return round(amount * rate, 2)


_exchange_singleton: Optional[ExchangeRateClient] = None


def get_exchange_client() -> ExchangeRateClient:
    global _exchange_singleton
    if _exchange_singleton is None:
        _exchange_singleton = ExchangeRateClient()
    return _exchange_singleton


def reset_exchange_client_for_tests() -> None:
    global _exchange_singleton
    _exchange_singleton = None
