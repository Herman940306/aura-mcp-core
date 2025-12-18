# tests/test_audio_stt_end_to_end.py
import os

import pytest
import requests

AUDIO_SERVICE = os.environ.get("AUDIO_SERVICE_URL", "http://localhost:8001")


def test_health():
    """Test audio service health endpoint."""
    r = requests.get(f"{AUDIO_SERVICE}/health", timeout=5)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


@pytest.mark.integration
def test_stt_endpoint_with_small_audio():
    """Test STT endpoint with a small audio file."""
    # Use a tiny synthetic WAV file included in repo test assets
    wav_path = os.path.join(
        os.path.dirname(__file__), "assets", "hello16k.wav"
    )
    if not os.path.exists(wav_path):
        pytest.skip("Test audio file not found: tests/assets/hello16k.wav")

    with open(wav_path, "rb") as f:
        r = requests.post(
            f"{AUDIO_SERVICE}/api/audio/stt",
            files={"audio": ("a.wav", f, "audio/wav")},
            timeout=10,
        )
    assert r.status_code == 200
    j = r.json()
    assert "text" in j
    assert isinstance(j.get("text"), str)


@pytest.mark.integration
def test_tts_endpoint():
    """Test TTS endpoint with simple text."""
    payload = {"text": "Hello world", "voice": "default", "format": "wav"}
    r = requests.post(
        f"{AUDIO_SERVICE}/api/audio/tts", json=payload, timeout=30
    )
    assert r.status_code == 200
    assert r.headers.get("content-type") == "audio/wav"
    assert len(r.content) > 1000  # Should have some audio data


def test_tts_rejects_pii():
    """Test that TTS endpoint rejects text containing PII."""
    payload = {"text": "Contact me at alice@example.com", "voice": "default"}
    r = requests.post(
        f"{AUDIO_SERVICE}/api/audio/tts", json=payload, timeout=10
    )
    assert r.status_code == 400
    assert "PII" in r.json().get("detail", "")


def test_tts_rejects_too_long():
    """Test that TTS endpoint rejects text that is too long."""
    payload = {"text": "x" * 25000, "voice": "default"}
    r = requests.post(
        f"{AUDIO_SERVICE}/api/audio/tts", json=payload, timeout=10
    )
    assert r.status_code == 413
