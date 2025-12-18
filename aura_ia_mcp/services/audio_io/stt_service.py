"""
Vosk Speech-to-Text Service for Aura IA MCP.

ENTERPRISE PRODUCTION SERVICE - NO MOCKS

STT Layer (PRD Section 8.12 compliant):
- Uses Vosk (Kaldi-based) for offline, CPU-only STT
- 94-95% WER parity with Google Cloud for English
- Memory footprint: 50-200 MB
- Latency: 70-120 ms

The embedded model NEVER touches audio directly - only routes through this service.
This ensures PRD compliance: model explains actions, triggers MCP tools, but doesn't
directly process audio content.

Deployment Requirements:
- vosk>=0.3.45 must be installed
- Model must be downloaded: python scripts/download_vosk_model.py
- Model path: model_artifacts/vosk-model-small-en-us-0.15
"""

from __future__ import annotations

import io
import json
import logging
import os
import wave
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import Vosk at module level - required for enterprise deployment
try:
    import vosk

    vosk.SetLogLevel(-1)  # Suppress Vosk logging
    VOSK_AVAILABLE = True
except ImportError as e:
    VOSK_AVAILABLE = False
    VOSK_IMPORT_ERROR = str(e)

# ============================================================================
# Configuration
# ============================================================================


@dataclass
class VoskConfig:
    """Configuration for Vosk STT service."""

    # Model path - defaults to models folder
    model_path: str = field(
        default_factory=lambda: os.getenv(
            "VOSK_MODEL_PATH",
            str(
                Path(__file__).parent.parent.parent.parent
                / "model_artifacts"
                / "vosk-model-small-en-us-0.15"
            ),
        )
    )

    # Audio settings
    sample_rate: int = 16000  # 16kHz required by Vosk
    channels: int = 1  # Mono
    sample_width: int = 2  # 16-bit PCM

    # Performance settings
    max_audio_length_seconds: float = 60.0  # Max 60 seconds per request
    chunk_size: int = 4096  # Bytes per chunk for streaming

    # Feature flags
    show_words: bool = True  # Include word-level timestamps
    show_partial: bool = False  # Stream partial results

    # Logging
    log_transcriptions: bool = True


# ============================================================================
# Response Models
# ============================================================================


class STTResult(BaseModel):
    """Speech-to-text result."""

    text: str
    confidence: float = 0.0
    words: list[dict[str, Any]] = []
    processing_time_ms: float = 0.0
    sample_rate: int = 16000
    audio_duration_seconds: float = 0.0


class STTStatus(BaseModel):
    """STT service status."""

    available: bool
    model_loaded: bool
    model_name: str
    sample_rate: int
    supported_languages: list[str]


# ============================================================================
# Vosk STT Service
# ============================================================================


class VoskSTTService:
    """
    Vosk-based Speech-to-Text service.

    ENTERPRISE PRODUCTION SERVICE - NO MOCKS

    Features:
    - Offline operation (no internet required)
    - CPU-only (works on any home server)
    - Low memory footprint (50-200 MB)
    - Fast inference (70-120 ms latency)
    - 94-95% WER on CommonVoice/LibriSpeech

    PRD Compliance:
    - Audio never touches the LLM directly
    - Gateway routes audio to this service
    - Returns structured text for HNSC processing

    Deployment:
    - Requires vosk package: pip install vosk
    - Requires model: python scripts/download_vosk_model.py
    """

    def __init__(self, config: VoskConfig | None = None):
        self.config = config or VoskConfig()
        self._model = None
        self._recognizer = None
        self._model_loaded = False
        self._initialization_error: str | None = None

        # Validate Vosk is available at construction time
        if not VOSK_AVAILABLE:
            self._initialization_error = (
                f"Vosk package not installed: {VOSK_IMPORT_ERROR}. "
                f"Install with: pip install vosk>=0.3.45"
            )
            logger.error(self._initialization_error)

    async def initialize(self) -> bool:
        """
        Initialize the Vosk model.

        REQUIRED before using the service. Will fail if:
        - Vosk package not installed
        - Model not downloaded

        Returns:
            True if initialization successful

        Raises:
            RuntimeError: If Vosk not installed or model not found
        """
        if not VOSK_AVAILABLE:
            raise RuntimeError(
                "Vosk package not installed. Install with: pip install vosk>=0.3.45"
            )

        model_path = Path(self.config.model_path)

        if not model_path.exists():
            error_msg = (
                f"Vosk model not found at {model_path}. "
                f"Download with: python scripts/download_vosk_model.py"
            )
            self._initialization_error = error_msg
            raise RuntimeError(error_msg)

        try:
            logger.info(f"Loading Vosk model from {model_path}")
            self._model = vosk.Model(str(model_path))
            self._model_loaded = True
            self._initialization_error = None
            logger.info("Vosk model loaded successfully")
            return True

        except Exception as e:
            self._initialization_error = f"Failed to load Vosk model: {e}"
            logger.error(self._initialization_error)
            raise RuntimeError(self._initialization_error) from e

    def _ensure_initialized(self) -> None:
        """Ensure the service is initialized before use."""
        if not self._model_loaded:
            if self._initialization_error:
                raise RuntimeError(
                    f"STT service not initialized: {self._initialization_error}"
                )
            raise RuntimeError(
                "STT service not initialized. Call initialize() first."
            )

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int | None = None,
    ) -> STTResult:
        """
        Transcribe audio to text.

        Args:
            audio_data: Raw PCM16 audio bytes (16kHz mono)
            sample_rate: Sample rate of audio (default: 16000)

        Returns:
            STTResult with transcription and metadata

        Raises:
            RuntimeError: If service not initialized
            ValueError: If audio too long
            HTTPException: If transcription fails
        """
        self._ensure_initialized()

        start_time = datetime.now()
        sample_rate = sample_rate or self.config.sample_rate

        # Calculate audio duration
        audio_duration = len(audio_data) / (
            sample_rate * self.config.sample_width
        )

        # Validate audio length
        if audio_duration > self.config.max_audio_length_seconds:
            raise ValueError(
                f"Audio too long: {audio_duration:.1f}s > {self.config.max_audio_length_seconds}s max"
            )

        try:
            # Create recognizer for this request
            recognizer = vosk.KaldiRecognizer(self._model, sample_rate)
            recognizer.SetWords(self.config.show_words)

            # Process audio in chunks
            chunk_size = self.config.chunk_size
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i : i + chunk_size]
                recognizer.AcceptWaveform(chunk)

            # Get final result
            result_json = recognizer.FinalResult()
            result = json.loads(result_json)

            # Calculate processing time
            processing_time_ms = (
                datetime.now() - start_time
            ).total_seconds() * 1000

            # Extract words if available
            words = result.get("result", [])

            # Calculate confidence (average of word confidences)
            confidence = 0.0
            if words:
                confidences = [w.get("conf", 0.0) for w in words]
                confidence = sum(confidences) / len(confidences)

            stt_result = STTResult(
                text=result.get("text", "").strip(),
                confidence=confidence,
                words=words,
                processing_time_ms=processing_time_ms,
                sample_rate=sample_rate,
                audio_duration_seconds=audio_duration,
            )

            if self.config.log_transcriptions:
                logger.info(
                    f"STT: '{stt_result.text[:50]}...' "
                    f"(conf={confidence:.2f}, {processing_time_ms:.0f}ms)"
                )

            return stt_result

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Transcription failed: {e}"
            )

    async def transcribe_wav(self, wav_file: io.BytesIO) -> STTResult:
        """
        Transcribe a WAV file.

        Args:
            wav_file: BytesIO containing WAV data

        Returns:
            STTResult with transcription
        """
        try:
            with wave.open(wav_file, "rb") as wf:
                # Validate format
                if wf.getnchannels() != 1:
                    raise ValueError(
                        f"Expected mono audio, got {wf.getnchannels()} channels"
                    )
                if wf.getsampwidth() != 2:
                    raise ValueError(
                        f"Expected 16-bit audio, got {wf.getsampwidth() * 8}-bit"
                    )

                sample_rate = wf.getframerate()
                audio_data = wf.readframes(wf.getnframes())

            return await self.transcribe(audio_data, sample_rate)

        except wave.Error as e:
            raise ValueError(f"Invalid WAV file: {e}")

    def get_status(self) -> STTStatus:
        """Get service status."""
        return STTStatus(
            available=VOSK_AVAILABLE,
            model_loaded=self._model_loaded,
            model_name="vosk-model-small-en-us-0.15",
            sample_rate=self.config.sample_rate,
            supported_languages=["en-US"],  # Can be extended
        )

    def is_ready(self) -> bool:
        """Check if service is ready to accept requests."""
        return VOSK_AVAILABLE and self._model_loaded

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._model = None
        self._recognizer = None
        self._model_loaded = False
        logger.info("Vosk STT service shutdown complete")


# ============================================================================
# FastAPI Router
# ============================================================================

stt_router = APIRouter(prefix="/api/stt", tags=["Speech-to-Text"])

# Singleton instance
_stt_service: VoskSTTService | None = None


def get_stt_service() -> VoskSTTService:
    """Get or create STT service singleton."""
    global _stt_service
    if _stt_service is None:
        _stt_service = VoskSTTService()
    return _stt_service


@stt_router.on_event("startup")
async def startup_stt():
    """Initialize STT service on startup."""
    service = get_stt_service()
    await service.initialize()


@stt_router.on_event("shutdown")
async def shutdown_stt():
    """Cleanup STT service on shutdown."""
    global _stt_service
    if _stt_service:
        await _stt_service.shutdown()
        _stt_service = None


@stt_router.get("/status", response_model=STTStatus)
async def get_stt_status():
    """Get STT service status."""
    service = get_stt_service()
    return service.get_status()


@stt_router.post("/transcribe", response_model=STTResult)
async def transcribe_audio(
    file: UploadFile = File(
        ..., description="WAV audio file (16kHz mono PCM16)"
    ),
):
    """
    Transcribe audio file to text.

    Accepts:
    - WAV files (16kHz mono PCM16 preferred)
    - Raw PCM16 audio (Content-Type: audio/pcm)

    Returns:
    - Transcribed text with confidence scores
    - Word-level timestamps
    - Processing metrics
    """
    service = get_stt_service()

    # Read file content
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # Determine format based on content type or file extension
    content_type = file.content_type or ""
    filename = file.filename or ""

    try:
        if "wav" in content_type or filename.lower().endswith(".wav"):
            # Parse as WAV
            wav_buffer = io.BytesIO(content)
            return await service.transcribe_wav(wav_buffer)
        else:
            # Assume raw PCM16 at 16kHz
            return await service.transcribe(content)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@stt_router.post("/transcribe/raw", response_model=STTResult)
async def transcribe_raw_audio(
    audio_data: bytes = File(
        ..., description="Raw PCM16 audio bytes (16kHz mono)"
    ),
    sample_rate: int = 16000,
):
    """
    Transcribe raw PCM audio bytes.

    For use with MediaRecorder in browsers sending raw PCM chunks.

    Args:
        audio_data: Raw PCM16 bytes
        sample_rate: Sample rate (default 16000)
    """
    service = get_stt_service()

    if not audio_data:
        raise HTTPException(status_code=400, detail="Empty audio data")

    try:
        return await service.transcribe(audio_data, sample_rate)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Registration Function for Gateway
# ============================================================================


def register(app, settings=None) -> None:
    """
    Register STT routes with the FastAPI app.

    Called by gateway.py to include STT endpoints.
    """
    app.include_router(stt_router)
    logger.info("STT service routes registered at /api/stt")
