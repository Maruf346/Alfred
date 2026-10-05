"""
Thin SerpAPI wrapper. The AI never fabricates recommendations — if this
returns [] or raises, callers must fall back to the "no search results"
prompt path rather than inventing venues.
"""
import logging
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings, get_settings
from app.http_client import get_http_client

logger = logging.getLogger("alfred.search")


class SearchError(Exception):
    pass


# SerpAPI has no single "just give me this currency" switch that works across every
# engine — the reliable way to get region-appropriate pricing is currency + a matching
# Google country code (gl). Extend this as more currencies come up.
_CURRENCY_TO_GL = {
    "USD": "us",
    "BDT": "bd",
    "INR": "in",
    "GBP": "gb",
    "EUR": "de",
}


def _locale_params(currency: Optional[str]) -> Dict[str, str]:
    if not currency:
        return {}
    currency = currency.upper()
    params = {"currency": currency}
    gl = _CURRENCY_TO_GL.get(currency)
    if gl:
        params["gl"] = gl
    return params


class SerpAPIClient:
    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()

    @property
    def _enabled(self) -> bool:
        return bool(self._settings.serpapi_key)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5))
    async def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = {**params, "api_key": self._settings.serpapi_key}
        client = get_http_client()
        resp = await client.get(self._settings.serpapi_base_url, params=params, timeout=10.0)
        resp.raise_for_status()
        return resp.json()

    async def _get_locale_aware(self, base_params: Dict[str, Any], currency: Optional[str]) -> Dict[str, Any]:
        """Not every Google country code is a supported storefront for every engine
        (e.g. Google Shopping doesn't support gl=bd for Bangladesh) — SerpAPI rejects
        those with a 400. Rather than losing the whole search over an unsupported
        locale, retry once without the currency/gl override."""
        locale_params = _locale_params(currency)
        if not locale_params:
            return await self._get(base_params)
        try:
            return await self._get({**base_params, **locale_params})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Locale-scoped search failed with %s (%s), retrying without locale override", locale_params, exc)
            return await self._get(base_params)

    async def search_places(self, query: str, location: str, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        """Restaurants / activities / gifts-as-shops via Google Local results."""
        if not self._enabled:
            logger.warning("SERPAPI_KEY not set — skipping live search for %r", query)
            return []
        try:
            data = await self._get_locale_aware({
                "engine": "google_local",
                "q": query,
                "location": location,
            }, currency)
        except Exception as exc:  # noqa: BLE001
            logger.error("SerpAPI place search failed for %r: %s", query, exc)
            raise SearchError(str(exc)) from exc

        results = []
        for item in data.get("local_results", [])[:10]:
            results.append({
                "name": item.get("title"),
                "rating": item.get("rating"),
                "price_level": item.get("price"),
                "address": item.get("address"),
                "url": item.get("links", {}).get("website") if isinstance(item.get("links"), dict) else item.get("link"),
                "image_url": item.get("thumbnail"),
            })
        return results

    async def search_products(self, query: str, location: Optional[str] = None) -> List[Dict[str, Any]]:
        """Real purchasable products (used for gift suggestions) via Google Shopping
        results. Always searched in USD — Google Shopping doesn't support every
        country as a storefront (e.g. Bangladesh), so callers convert the user's
        budget/currency around this rather than relying on a per-country storefront
        that may not exist. Google's own `tbs` price-range filter turned out to be
        silently ignored by this engine in testing, so this returns the full result
        page (with each item's real extracted_price_usd) and leaves budget filtering
        to the caller, who can filter/sort on the real numbers instead of trusting
        an unreliable server-side filter."""
        if not self._enabled:
            logger.warning("SERPAPI_KEY not set — skipping live product search for %r", query)
            return []
        params: Dict[str, Any] = {"engine": "google_shopping", "q": query}
        if location:
            params["location"] = location
        try:
            data = await self._get(params)
        except Exception as exc:  # noqa: BLE001
            logger.error("SerpAPI product search failed for %r: %s", query, exc)
            raise SearchError(str(exc)) from exc

        results = []
        for item in data.get("shopping_results", []):
            results.append({
                "name": item.get("title"),
                "rating": item.get("rating"),
                "price_level": item.get("price"),
                "extracted_price_usd": item.get("extracted_price"),
                "url": item.get("product_link") or item.get("link"),
                "image_url": item.get("thumbnail"),
            })
        return results

    async def search_events(self, query: str, location: str, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        """Dated events (concerts, festivals, exhibitions, shows) via Google Events —
        distinct from search_places (static venues, no date/time), matching a
        dedicated "Events" tab in the UI rather than a relabeled activity search."""
        if not self._enabled:
            logger.warning("SERPAPI_KEY not set — skipping live event search for %r", query)
            return []
        try:
            data = await self._get_locale_aware({
                "engine": "google_events",
                "q": f"{query} events in {location}" if location else f"{query} events",
            }, currency)
        except Exception as exc:  # noqa: BLE001
            logger.error("SerpAPI event search failed for %r: %s", query, exc)
            raise SearchError(str(exc)) from exc

        results = []
        for item in data.get("events_results", [])[:10]:
            venue = item.get("venue") or {}
            date_info = item.get("date") or {}
            when = date_info.get("when") or date_info.get("start_date")
            address = ", ".join(item.get("address", [])) if isinstance(item.get("address"), list) else item.get("address")
            thumbnail = item.get("thumbnail") or item.get("image")
            results.append({
                "name": item.get("title"),
                "rating": venue.get("rating"),
                # Google Events doesn't give a normalized price field — surface
                # the date/time here since that's the defining detail for an
                # event (vs. a static venue), not a price we don't actually have.
                "price_level": when,
                "address": address or venue.get("name"),
                "url": item.get("link"),
                "image_url": thumbnail,
            })
        return results

    async def search_flights(self, origin: str, destination: str, start_date: str, end_date: str, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._enabled:
            logger.warning("SERPAPI_KEY not set — skipping live flight search")
            return []
        try:
            data = await self._get_locale_aware({
                "engine": "google_flights",
                "departure_id": origin,
                "arrival_id": destination,
                "outbound_date": start_date,
                "return_date": end_date,
            }, currency)
        except Exception as exc:  # noqa: BLE001
            logger.error("SerpAPI flight search failed: %s", exc)
            raise SearchError(str(exc)) from exc

        results = []
        for item in data.get("best_flights", []) + data.get("other_flights", []):
            price = item.get("price")
            results.append({
                "name": " / ".join(f.get("airline", "") for f in item.get("flights", [])) or "Flight option",
                # Google gives one figure, not a real min/max — "from $X" is honest
                # about it being a starting estimate, not a locked/guaranteed fare.
                "price_level": f"from ${price}" if price is not None else None,
                "url": data.get("search_metadata", {}).get("google_flights_url"),
            })
        return results[:10]

    async def search_hotels(self, destination: str, start_date: str, end_date: str, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._enabled:
            logger.warning("SERPAPI_KEY not set — skipping live hotel search")
            return []
        try:
            data = await self._get_locale_aware({
                "engine": "google_hotels",
                "q": f"hotels in {destination}",
                "check_in_date": start_date,
                "check_out_date": end_date,
            }, currency)
        except Exception as exc:  # noqa: BLE001
            logger.error("SerpAPI hotel search failed: %s", exc)
            raise SearchError(str(exc)) from exc

        results = []
        for item in data.get("properties", [])[:10]:
            rate = item.get("rate_per_night")
            lowest = rate.get("lowest") if isinstance(rate, dict) else None
            images = item.get("images") or []
            thumbnail = images[0].get("thumbnail") if images and isinstance(images[0], dict) else None
            results.append({
                "name": item.get("name"),
                "rating": item.get("overall_rating"),
                # Google gives one figure, not a real min/max — "from $X/night" is
                # honest about it being a starting estimate (varies by room/dates),
                # not a locked/guaranteed rate.
                "price_level": f"from {lowest}/night" if lowest else None,
                "url": item.get("link"),
                "image_url": thumbnail,
            })
        return results


_search_singleton: Optional[SerpAPIClient] = None


def get_search_client() -> SerpAPIClient:
    global _search_singleton
    if _search_singleton is None:
        _search_singleton = SerpAPIClient()
    return _search_singleton


def reset_search_client_for_tests() -> None:
    global _search_singleton
    _search_singleton = None
