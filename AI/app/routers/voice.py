from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response

from app.dependencies import verify_service_api_key
from app.schemas import SpeakRequest
from app.voice_client import VoiceError, get_stt_client, get_tts_client

router = APIRouter(prefix="/voice", tags=["voice"], dependencies=[Depends(verify_service_api_key)])


@router.post("/transcribe")
async def transcribe(audio: UploadFile) -> dict:
    """Audio in, transcript out. Client then sends the transcript as `message`
    to /chat (with session_id) as normal — this endpoint has no chat logic."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="Uploaded audio file is empty.")
    stt = get_stt_client()
    try:
        text = await stt.transcribe(audio_bytes, audio.filename or "audio.webm")
    except VoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"text": text}


async def _speak(text: str) -> Response:
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="`text` must not be empty.")
    tts = get_tts_client()
    try:
        audio_bytes = await tts.synthesize(text)
    except VoiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=audio_bytes, media_type="audio/mpeg")


@router.post("/speak")
async def speak(req: SpeakRequest) -> Response:
    """Text in (typically a /chat `reply`), MP3 audio out. This is the real
    integration path for clients — POST avoids URL-length limits and keeps
    text out of server access logs."""
    return await _speak(req.text)


@router.get("/speak")
async def speak_via_link(text: str, download: bool = False) -> Response:
    """Same as POST /speak, but as a plain link (?text=...) so the audio can be
    opened directly in a browser tab for manual listening — Swagger's response
    viewer doesn't reliably play audio/mpeg bodies. Set download=true to download the MP3 file directly."""
    resp = await _speak(text)
    if download:
        resp.headers["Content-Disposition"] = 'attachment; filename="speech.mp3"'
    return resp

