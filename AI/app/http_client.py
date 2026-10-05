"""
Shared, pooled httpx.AsyncClient for the whole process.

Every outbound HTTP caller (SerpAPI, exchange rates, ElevenLabs) was opening a
brand new httpx.AsyncClient per request — a fresh TCP connection + TLS
handshake every single call, torn down immediately after. Under real traffic
that's the single biggest avoidable latency cost in this service. One shared,
connection-pooled client reuses keep-alive connections across requests.
"""
from typing import Optional

import httpx

_client_singleton: Optional[httpx.AsyncClient] = None


def get_http_client() -> httpx.AsyncClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
    return _client_singleton


async def aclose_http_client() -> None:
    global _client_singleton
    if _client_singleton is not None:
        await _client_singleton.aclose()
        _client_singleton = None


def reset_http_client_for_tests() -> None:
    global _client_singleton
    _client_singleton = None
