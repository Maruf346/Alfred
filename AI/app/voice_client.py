"""
Turn-based voice: audio in -> transcript, reply text -> audio out.

This deliberately does NOT stream or hold a live connection — the caller
records a turn, sends it here, gets text/audio back, same request/response
shape as every other endpoint in this service. A live, interrupt-able voice
call is a materially bigger feature (duplex streaming, turn-taking) and is
out of scope here by design; this covers push-to-talk style voice.
"""
import logging
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings, get_settings
from app.http_client import get_http_client

logger = logging.getLogger("alfred.voice")


class VoiceError(Exception):
    pass


class SpeechToText:
    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._client = None  # lazily built once, reused across calls

    @property
    def _enabled(self) -> bool:
        return self._settings.stt_provider == "openai" and bool(self._settings.openai_api_key)

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._settings.openai_api_key)
        return self._client

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
    async def transcribe(self, audio_bytes: bytes, filename: str) -> str:
        if not self._enabled:
            raise VoiceError("Speech-to-text is not configured (OPENAI_API_KEY missing).")

        client = self._get_client()
        try:
            result = await client.audio.transcriptions.create(
                model=self._settings.stt_model,
                file=(filename, audio_bytes),
            )
            return result.text
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            logger.error("Transcription failed: %s", exc)
            raise VoiceError(str(exc)) from exc


class TextToSpeech:
    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()

    @property
    def _enabled(self) -> bool:
        return (
            self._settings.tts_provider == "elevenlabs"
            and bool(self._settings.elevenlabs_api_key)
            and bool(self._settings.elevenlabs_voice_id)
        )

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=5), reraise=True)
    async def synthesize(self, text: str) -> bytes:
        """Returns MP3 audio bytes for the given text, spoken in Alfred's voice."""
        if not self._enabled:
            raise VoiceError("Text-to-speech is not configured (ELEVENLABS_API_KEY/VOICE_ID missing).")

        url = f"{self._settings.elevenlabs_base_url}/text-to-speech/{self._settings.elevenlabs_voice_id}"
        headers = {"xi-api-key": self._settings.elevenlabs_api_key, "Accept": "audio/mpeg"}
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            # Lower stability + measured similarity reads as calm/composed rather than
            # peppy — matches a butler's register better than default TTS defaults.
            "voice_settings": {"stability": 0.65, "similarity_boost": 0.75},
        }
        try:
            client = get_http_client()
            resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:  # noqa: BLE001
            logger.error("Speech synthesis failed: %s", exc)
            raise VoiceError(str(exc)) from exc


_stt_singleton: Optional[SpeechToText] = None
_tts_singleton: Optional[TextToSpeech] = None


def get_stt_client() -> SpeechToText:
    global _stt_singleton
    if _stt_singleton is None:
        _stt_singleton = SpeechToText()
    return _stt_singleton


def get_tts_client() -> TextToSpeech:
    global _tts_singleton
    if _tts_singleton is None:
        _tts_singleton = TextToSpeech()
    return _tts_singleton


def reset_voice_clients_for_tests() -> None:
    global _stt_singleton, _tts_singleton
    _stt_singleton = None
    _tts_singleton = None
