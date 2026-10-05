"""
Centralized, env-driven configuration.

Nothing in this service is hardcoded to a particular machine or network —
HOST/PORT control local-vs-LAN binding, and everything secret comes from .env.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- LLM provider ---
    llm_provider: str = "anthropic"          # anthropic | openai
    llm_model: str = "claude-sonnet-4-6"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7

    # --- Search ---
    serpapi_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search"

    # --- Voice (turn-based: audio -> text -> /chat -> text -> audio) ---
    stt_provider: str = "openai"             # openai (Whisper)
    tts_provider: str = "elevenlabs"         # elevenlabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""            # a calm, measured, older-sounding voice fits Alfred
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"
    stt_model: str = "whisper-1"

    # --- Currency conversion (free, keyless FX-rate API) ---
    exchange_rate_base_url: str = "https://open.er-api.com/v6/latest"
    exchange_rate_cache_seconds: int = 21600  # 6 hours

    # --- Service auth ---
    ai_service_api_key: str = "change-me"
    require_service_api_key_in_dev: bool = False

    # --- App ---
    env: str = "development"                 # development | production
    app_name: str = "Alfred AI Concierge"
    log_level: str = "INFO"
    allowed_origins: str = "http://localhost:3000"

    # --- Hosting ---
    host: str = "127.0.0.1"
    port: int = 8001

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
