import logging
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Support direct execution: `python app/main.py`.
if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.http_client import aclose_http_client
from app.llm_client import LLMError
from app.logging_config import configure_logging
from app.routers import budget, chat, coach, gift, health, plan_date, recommend, travel, voice
from app.schemas import ErrorResponse
from app.search_client import SearchError
from app.voice_client import VoiceError

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger("alfred.main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await aclose_http_client()


app = FastAPI(
    title=settings.app_name,
    description=(
        "Alfred's AI service layer: conversational concierge, date planning, "
        "recommendations, coaching, gifts, travel, and AI budget analysis. /chat optionally holds "
        "short-lived, in-memory session state keyed by session_id; every other "
        "endpoint remains stateless and relies on the caller's own context."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(recommend.router)
app.include_router(plan_date.router)
app.include_router(coach.router)
app.include_router(gift.router)
app.include_router(travel.router)
app.include_router(voice.router)
app.include_router(budget.router)


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError) -> JSONResponse:
    logger.error("Unhandled LLMError on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorResponse(error="ai_provider_unavailable", detail=str(exc)).model_dump(),
    )


@app.exception_handler(SearchError)
async def search_error_handler(request: Request, exc: SearchError) -> JSONResponse:
    logger.error("Unhandled SearchError on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorResponse(
            error="search_provider_unavailable",
            detail=str(exc),
            follow_up_question="Live search isn't available right now — want general advice instead?",
        ).model_dump(),
    )


@app.exception_handler(VoiceError)
async def voice_error_handler(request: Request, exc: VoiceError) -> JSONResponse:
    logger.error("Unhandled VoiceError on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=ErrorResponse(error="voice_provider_unavailable", detail=str(exc)).model_dump(),
    )


@app.get("/", tags=["health"])
async def root():
    return {"service": settings.app_name, "docs": "/docs"}


def _detect_lan_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    import uvicorn

    lan_ip = _detect_lan_ip()
    print(f"[alfred] Local docs: http://127.0.0.1:{settings.port}/docs")
    print(f"[alfred] LAN URL to share: http://{lan_ip}:{settings.port}")
    if settings.host != "0.0.0.0":
        print("[alfred] Set HOST=0.0.0.0 in .env to allow LAN access.")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=not settings.is_production,
    )
