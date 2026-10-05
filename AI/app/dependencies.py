"""
Shared-secret auth between the backend and this AI service.

This is NOT end-user authentication (the backend already did that before it
ever calls us) — it just stops random devices on the LAN/network from
calling the AI service directly.
"""
from fastapi import HTTPException, Request, status

from app.config import get_settings


async def verify_service_api_key(request: Request) -> None:
    settings = get_settings()
    if not settings.is_production and not settings.require_service_api_key_in_dev:
        return

    x_api_key = request.headers.get("x-api-key", "")
    if not x_api_key or x_api_key != settings.ai_service_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key header.",
        )
