# audio_service/main.py
# FastAPI wrapper for Vosk STT + Coqui TTS with PII redaction + policy hooks
import io
import logging
import os
import tempfile
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Minimal PII filter stub - replace with your production implementation
PII_PATTERNS = [
    r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",  # simplistic SSN-ish
    r"\b(?:\d[ -]*?){13,16}\b",  # credit-card-ish
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",  # email
]

import re


def pii_filter(text: str):
    redacted = False
    out = text
    for p in PII_PATTERNS:
        out_new = re.sub(p, "[REDACTED]", out)
        if out_new != out:
            redacted = True
            out = out_new
    return out, redacted


# Simple policy hook - replace with call to HNSC Layer 6
def policy_check_transcript(transcript: str) -> bool:
    # Deny if transcript contains explicit banned commands (example)
    banned = ["delete all", "override policy", "sudo rm -rf /"]
    low = transcript.lower()
    for b in banned:
        if b in low:
            return False
    return True


# config via env
VOSK_SERVER_URL = os.environ.get("VOSK_SERVER_URL", "http://vosk:2700")
COQUI_TTS_URL = os.environ.get("COQUI_TTS_URL", "http://coqui:5002")
MAX_AUDIO_SECONDS = int(os.environ.get("MAX_AUDIO_SECONDS", "60"))
STT_ENGINE = os.environ.get("STT_ENGINE", "vosk")
TTS_ENGINE = os.environ.get("TTS_ENGINE", "coqui")

app = FastAPI(title="Aura Audio Service")

logger = logging.getLogger("uvicorn.error")


class STTResponse(BaseModel):
    text: str
    confidence: float | None = None
    redacted: bool = False
    policy_blocked: bool = False


class TTSPayload(BaseModel):
    text: str
    voice: str | None = "default"
    language: str | None = "en"
    format: str | None = "wav"


@app.post("/api/audio/stt", response_model=STTResponse)
async def stt_endpoint(audio: UploadFile = File(...)):
    # Validate content type / size
    contents = await audio.read()
    # crude length check (assumes 16kHz 16bit PCM -> ~32 KB/s)
    if len(contents) > (MAX_AUDIO_SECONDS * 32000 * 2):
        raise HTTPException(status_code=413, detail="Audio too long")
    # write to temp WAV (assume client sends WAV/PCM16)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.write(contents)
    tmp.flush()
    tmp.close()
    try:
        # Call the configured STT engine wrapper
        if STT_ENGINE == "vosk":
            transcript, confidence = run_vosk_stt(tmp.name)
        else:
            raise HTTPException(
                status_code=500, detail="STT engine not supported"
            )

        # PII filter
        redacted_text, redacted_flag = pii_filter(transcript)

        # Policy check
        policy_ok = policy_check_transcript(redacted_text)
        if not policy_ok:
            logger.warning("Policy blocked transcript: %s", redacted_text)
            return STTResponse(
                text="", redacted=redacted_flag, policy_blocked=True
            )

        # Minimal audit log (no raw audio)
        logger.info(
            "STT processed session=%s len=%d redacted=%s",
            str(uuid.uuid4()),
            len(contents),
            redacted_flag,
        )
        return STTResponse(
            text=redacted_text, confidence=confidence, redacted=redacted_flag
        )
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@app.post("/api/audio/tts")
async def tts_endpoint(payload: TTSPayload):
    # Validate text limits
    if len(payload.text) > 20000:
        raise HTTPException(status_code=413, detail="TTS text too long")
    # policy: no unredacted PII
    redacted_text, redacted_flag = pii_filter(payload.text)
    if redacted_flag:
        # optionally allow but mark - here we require rephrase
        return JSONResponse(
            status_code=400,
            content={
                "detail": "PII detected in TTS text; please redact or confirm."
            },
        )

    if TTS_ENGINE == "coqui":
        audio_bytes = run_coqui_tts(
            redacted_text, payload.voice, payload.language, payload.format
        )
    else:
        raise HTTPException(status_code=500, detail="TTS engine not supported")

    # audit
    logger.info("TTS generated len_chars=%d", len(redacted_text))
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/wav")


# -------------------------
# Engine wrapper implementations
# -------------------------
import requests


def run_vosk_stt(wav_path: str):
    """
    Simple HTTP POST to Vosk server (asr_server.py websocket has a REST wrapper variant)
    Fallback: call local vsock or use subprocess to vosk-api. Here we assume an HTTP REST:
    POST http://vosk:2700/transcribe
    """
    url = f"{VOSK_SERVER_URL}/transcribe"
    with open(wav_path, "rb") as f:
        resp = requests.post(
            url, files={"audio": ("audio.wav", f, "audio/wav")}, timeout=15
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="STT engine error")
    data = resp.json()
    # expected: {"text":"...", "confidence":0.95}
    return data.get("text", ""), data.get("confidence", None)


def run_coqui_tts(text: str, voice: str, language: str, fmt: str) -> bytes:
    """
    XTTS v2 voice cloning TTS.
    - voice: path to speaker wav file (e.g., "aura.wav") or "default"
    - language: language code (en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, ja, ko, hu)
    """
    url = f"{COQUI_TTS_URL}/api/tts"

    # XTTS v2 uses different parameters
    params = {
        "text": text,
        "language": language or "en",
    }

    # If a custom voice is specified, use speaker_wav
    if voice and voice != "default":
        # Voice file should be in /voices/ directory inside container
        params["speaker_wav"] = f"/voices/{voice}"

    resp = requests.post(url, params=params, timeout=120)  # XTTS is slower
    if resp.status_code != 200:
        logger.error(
            "Coqui TTS error: %s - %s", resp.status_code, resp.text[:500]
        )
        raise HTTPException(
            status_code=502, detail=f"TTS engine error: {resp.text[:200]}"
        )
    return resp.content


@app.post("/api/audio/voices/upload")
async def upload_voice(name: str, audio: UploadFile = File(...)):
    """Upload a voice sample for cloning. Requires 6-30 seconds of clear speech."""
    contents = await audio.read()

    # Validate size (6-30 seconds at ~32KB/s = 192KB - 960KB for 16kHz 16bit)
    if len(contents) < 50000:
        raise HTTPException(
            status_code=400,
            detail="Voice sample too short. Need at least 6 seconds.",
        )
    if len(contents) > 5000000:
        raise HTTPException(
            status_code=400,
            detail="Voice sample too long. Maximum 30 seconds.",
        )

    # Save to voices directory
    voice_path = f"/voices/{name}.wav"

    # Write via the coqui container's mounted volume
    # The volume is mounted at ./models/voices:/voices
    import os

    local_path = os.path.join(
        os.environ.get("VOICES_DIR", "/app/voices"), f"{name}.wav"
    )
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    with open(local_path, "wb") as f:
        f.write(contents)

    logger.info("Voice sample uploaded: %s (%d bytes)", name, len(contents))
    return {
        "status": "ok",
        "voice_name": name,
        "usage": f"Use voice='{name}.wav' in TTS requests",
    }


@app.get("/api/audio/voices")
async def list_voices():
    """List available voice samples for cloning."""
    import os

    voices_dir = os.environ.get("VOICES_DIR", "/app/voices")
    voices = []
    if os.path.exists(voices_dir):
        voices = [f for f in os.listdir(voices_dir) if f.endswith(".wav")]
    return {
        "voices": voices,
        "default": "Built-in XTTS v2 default voice",
        "usage": "Set voice='filename.wav' to use a cloned voice",
    }


# -------------------------
# Health & Status Endpoints
# -------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/audio/status")
async def audio_status():
    """Detailed status of audio engines."""
    stt_ok = False
    tts_ok = False

    # Check STT engine
    try:
        resp = requests.get(f"{VOSK_SERVER_URL}/", timeout=2)
        stt_ok = resp.status_code < 500
    except Exception:
        pass

    # Check TTS engine
    try:
        resp = requests.get(f"{COQUI_TTS_URL}/", timeout=2)
        tts_ok = resp.status_code < 500
    except Exception:
        pass

    return {
        "status": "ok" if (stt_ok and tts_ok) else "degraded",
        "stt": {
            "engine": STT_ENGINE,
            "url": VOSK_SERVER_URL,
            "healthy": stt_ok,
        },
        "tts": {
            "engine": TTS_ENGINE,
            "url": COQUI_TTS_URL,
            "healthy": tts_ok,
        },
        "config": {
            "max_audio_seconds": MAX_AUDIO_SECONDS,
        },
    }


@app.get("/api/audio/engines")
async def list_engines():
    """List available audio engines."""
    return {
        "stt_engines": ["vosk", "whisper_cpp", "coqui_stt"],
        "tts_engines": ["coqui", "espeak_ng", "mozilla_tts"],
        "current_stt": STT_ENGINE,
        "current_tts": TTS_ENGINE,
    }
