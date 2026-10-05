"""
STT/TTS providers aren't configured in tests (no ElevenLabs/OpenAI voice creds),
so these confirm the "not configured" path degrades to a clean 502 instead of
leaking a raw 500 - this is the exact bug found during manual testing, where
tenacity's @retry swallowed VoiceError into a RetryError unless reraise=True.
"""


def test_speak_without_elevenlabs_config_returns_502(client, auth_headers):
    resp = client.post("/voice/speak", json={"text": "Good evening."}, headers=auth_headers)
    assert resp.status_code == 502
    assert "not configured" in resp.json()["detail"]


def test_speak_rejects_empty_text(client, auth_headers):
    resp = client.post("/voice/speak", json={"text": "   "}, headers=auth_headers)
    assert resp.status_code == 422


def test_transcribe_without_openai_key_returns_502(client, auth_headers, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    resp = client.post(
        "/voice/transcribe",
        files={"audio": ("test.wav", b"fake audio bytes", "audio/wav")},
        headers=auth_headers,
    )
    assert resp.status_code == 502
    assert "not configured" in resp.json()["detail"]


def test_transcribe_rejects_empty_audio(client, auth_headers):
    resp = client.post(
        "/voice/transcribe",
        files={"audio": ("test.wav", b"", "audio/wav")},
        headers=auth_headers,
    )
    assert resp.status_code == 422
