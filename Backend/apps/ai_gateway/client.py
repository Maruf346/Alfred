"""
HTTP client for the external Alfred FastAPI service.

The Django backend owns auth, persistence, and business rules. This client only
knows how to call AI endpoints and normalize transport errors.
"""

import logging
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class AlfredAIError(Exception):
    """Raised when the AI service cannot complete a request."""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class AlfredAIClient:
    def __init__(self):
        self.base_url = settings.ALFRED_AI_BASE_URL.rstrip("/")
        self.timeout = settings.ALFRED_AI_TIMEOUT_SECONDS
        self.api_key = settings.ALFRED_AI_API_KEY

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=self._headers())
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            detail = self._safe_json(exc.response)
            logger.warning(
                "AI service returned an error",
                extra={
                    "path": path,
                    "status_code": exc.response.status_code,
                    "detail": detail,
                },
            )
            raise AlfredAIError(
                "AI service rejected the request.",
                status_code=exc.response.status_code,
                detail=detail,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning(
                "AI service request failed",
                extra={"path": path, "error": str(exc)},
            )
            raise AlfredAIError(
                "AI service is unavailable.",
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise AlfredAIError("AI service returned an invalid JSON response.") from exc

    def post_audio(self, path: str, payload: dict[str, Any]) -> tuple[bytes, str]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=self._headers())
                response.raise_for_status()
                return response.content, response.headers.get("content-type", "audio/mpeg")
        except httpx.HTTPStatusError as exc:
            raise AlfredAIError(
                "AI voice service rejected the request.",
                status_code=exc.response.status_code,
                detail=self._safe_json(exc.response),
            ) from exc
        except httpx.RequestError as exc:
            raise AlfredAIError("AI voice service is unavailable.") from exc

    @staticmethod
    def _safe_json(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text
