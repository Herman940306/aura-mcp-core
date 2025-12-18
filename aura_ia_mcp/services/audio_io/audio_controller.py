"""
Audio Controller Service for Aura IA MCP.

ENTERPRISE MCP-BOUND AUDIO SERVICE

This controller provides MCP tool bindings for all audio I/O operations:
- Wake word detection management
- STT session orchestration
- TTS response synthesis
- Audio session state management

PRD Section 8.12 Compliance:
- All audio operations are MCP tool calls
- No direct audio processing by LLM
- Stateless per-request processing
- PII redaction on all transcripts

Tools Provided (Section 8.12.7):
- Tool #44: stt_transcribe - Convert audio → text
- Tool #45: tts_synthesize - Convert text → audio
- Tool #46: audio_health - Check service status
- Tool #47: get_audio_status - Get detailed status

Additional Dashboard-Bound Tools:
- wake_word_enable - Enable wake word detection
- wake_word_disable - Disable wake word detection
- wake_word_status - Get wake word session status
- audio_session_start - Start an audio interaction session
- audio_session_end - End current audio session
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .stt_service import STTResult, VoskSTTService, get_stt_service
from .tts_service import CoquiTTSService, get_tts_service

logger = logging.getLogger(__name__)


# ============================================================================
# Enums & Constants
# ============================================================================


class AudioSessionState(str, Enum):
    """Audio session states."""

    IDLE = "idle"
    WAKE_LISTENING = "wake_listening"
    COMMAND_LISTENING = "command_listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


# Wake word patterns (case-insensitive)
WAKE_WORDS = [
    r"\bhey\s+aura\b",
    r"\bhi\s+aura\b",
    r"\bok\s+aura\b",
    r"\baura\b",
    r"\bhey\s+aurora\b",
]

# PII Patterns for redaction (PRD 8.12.2)
PII_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "ssn": r"\b\d{3}[-.]?\d{2}[-.]?\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "phone": (
        r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?" r"[0-9]{3}[-.\s]?[0-9]{4}\b"
    ),
}


# ============================================================================
# Request/Response Models
# ============================================================================


class WakeWordConfig(BaseModel):
    """Wake word configuration."""

    enabled: bool = False
    sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    wake_words: list[str] = Field(
        default_factory=lambda: ["hey aura", "hi aura", "aura"]
    )
    timeout_seconds: float = Field(default=30.0, ge=5.0, le=300.0)


class AudioSessionConfig(BaseModel):
    """Audio session configuration."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    auto_send: bool = True  # Auto-send message after transcription
    tts_enabled: bool = True  # Speak responses
    wake_word_enabled: bool = False
    language: str = "en-US"


class WakeWordResult(BaseModel):
    """Result of wake word detection."""

    detected: bool
    wake_word: Optional[str] = None
    command_after: Optional[str] = None  # Text after wake word
    confidence: float = 0.0
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


class AudioSessionStatus(BaseModel):
    """Current audio session status."""

    session_id: Optional[str] = None
    state: AudioSessionState = AudioSessionState.IDLE
    wake_word_enabled: bool = False
    tts_enabled: bool = True
    stt_available: bool = False
    tts_available: bool = False
    last_activity: Optional[str] = None


class TranscriptionRequest(BaseModel):
    """Request for STT transcription via MCP tool."""

    audio_base64: str = Field(..., description="Base64 encoded audio data")
    sample_rate: int = Field(
        default=16000, description="Audio sample rate in Hz"
    )
    format: str = Field(
        default="wav", description="Audio format: wav, webm, pcm"
    )
    redact_pii: bool = Field(
        default=True, description="Redact PII from transcript"
    )


class TranscriptionResponse(BaseModel):
    """Response from STT transcription MCP tool."""

    text: str
    confidence: float
    pii_redacted: bool = False
    pii_count: int = 0
    processing_time_ms: float
    audio_duration_seconds: float
    wake_word_detected: bool = False
    command_text: Optional[str] = None  # Text after wake word


class SynthesisRequest(BaseModel):
    """Request for TTS synthesis via MCP tool."""

    text: str = Field(..., max_length=5000, description="Text to synthesize")
    speed: float = Field(
        default=1.0, ge=0.5, le=2.0, description="Speech speed"
    )
    format: str = Field(default="wav", description="Output format: wav, mp3")


class SynthesisResponse(BaseModel):
    """Response from TTS synthesis MCP tool."""

    audio_base64: str
    text_length: int
    audio_duration_seconds: float
    processing_time_ms: float
    format: str


class AudioHealthResponse(BaseModel):
    """Response from audio health check MCP tool."""

    status: str  # ok, degraded, unavailable
    stt: dict[str, Any]
    tts: dict[str, Any]
    wake_word: dict[str, Any]


# ============================================================================
# Audio Controller Service
# ============================================================================


class AudioControllerService:
    """
    Central controller for all audio I/O operations.

    All public methods are bound to MCP tools and follow PRD Section 8.12.

    This service:
    1. Manages audio sessions
    2. Orchestrates STT/TTS calls
    3. Handles wake word detection logic
    4. Enforces PII redaction
    5. Provides unified status/health endpoints
    """

    def __init__(self):
        self._sessions: dict[str, AudioSessionConfig] = {}
        self._active_session: Optional[str] = None
        self._wake_config = WakeWordConfig()
        self._last_activity: Optional[datetime] = None

    def _get_stt(self) -> VoskSTTService:
        """Get STT service instance."""
        return get_stt_service()

    def _get_tts(self) -> CoquiTTSService:
        """Get TTS service instance."""
        return get_tts_service()

    # ========================================================================
    # PII Redaction (PRD 8.12.2 Compliance)
    # ========================================================================

    def redact_pii(self, text: str) -> tuple[str, int]:
        """
        Redact PII patterns from text.

        PRD Section 8.12.2 requires sanitization for:
        - Email addresses
        - SSN patterns
        - Credit card numbers
        - Phone numbers

        Returns:
            Tuple of (redacted_text, pii_count)
        """
        pii_count = 0
        redacted = text

        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, redacted, re.IGNORECASE)
            pii_count += len(matches)
            redacted = re.sub(
                pattern,
                f"[{pii_type.upper()}_REDACTED]",
                redacted,
                flags=re.IGNORECASE,
            )

        if pii_count > 0:
            logger.info(f"Redacted {pii_count} PII patterns from transcript")

        return redacted, pii_count

    # ========================================================================
    # Wake Word Detection
    # ========================================================================

    def detect_wake_word(self, text: str) -> WakeWordResult:
        """
        Detect wake word in transcribed text.

        Checks for configured wake words and extracts any command
        that follows the wake word.

        Args:
            text: Transcribed text to check

        Returns:
            WakeWordResult with detection status and extracted command
        """
        text_lower = text.lower().strip()

        for pattern in WAKE_WORDS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                # Extract text after wake word
                command_after = text_lower[match.end() :].strip()

                return WakeWordResult(
                    detected=True,
                    wake_word=match.group(),
                    command_after=command_after if command_after else None,
                    confidence=0.95,  # High confidence for pattern match
                )

        return WakeWordResult(detected=False, confidence=0.0)

    # ========================================================================
    # MCP Tool: stt_transcribe (Tool #44)
    # ========================================================================

    async def stt_transcribe(
        self, request: TranscriptionRequest
    ) -> TranscriptionResponse:
        """
        MCP Tool #44: Transcribe audio to text.

        PRD Section 8.12.7:
        - Input: Base64 audio, sample rate
        - Output: Transcribed text with confidence
        - PII redaction applied by default

        Args:
            request: TranscriptionRequest with audio data

        Returns:
            TranscriptionResponse with transcription and metadata
        """
        import base64

        start_time = datetime.now()

        # Decode base64 audio
        try:
            audio_bytes = base64.b64decode(request.audio_base64)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid base64 audio: {e}"
            )

        # Get STT service and transcribe
        stt = self._get_stt()

        if not stt.is_ready():
            raise HTTPException(
                status_code=503, detail="STT service not ready"
            )

        result: STTResult = await stt.transcribe(
            audio_bytes, request.sample_rate
        )

        # Apply PII redaction if enabled
        text = result.text
        pii_redacted = False
        pii_count = 0

        if request.redact_pii and text:
            text, pii_count = self.redact_pii(text)
            pii_redacted = pii_count > 0

        # Check for wake word
        wake_result = self.detect_wake_word(text)

        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        self._last_activity = datetime.now()

        return TranscriptionResponse(
            text=text,
            confidence=result.confidence,
            pii_redacted=pii_redacted,
            pii_count=pii_count,
            processing_time_ms=processing_time,
            audio_duration_seconds=result.audio_duration_seconds,
            wake_word_detected=wake_result.detected,
            command_text=wake_result.command_after,
        )

    # ========================================================================
    # MCP Tool: tts_synthesize (Tool #45)
    # ========================================================================

    async def tts_synthesize(
        self, request: SynthesisRequest
    ) -> SynthesisResponse:
        """
        MCP Tool #45: Synthesize text to speech.

        PRD Section 8.12.7:
        - Input: Text, speed, format
        - Output: Base64 audio with duration

        Args:
            request: SynthesisRequest with text to speak

        Returns:
            SynthesisResponse with audio and metadata
        """
        import base64

        start_time = datetime.now()

        # Get TTS service and synthesize
        tts = self._get_tts()

        if not tts.is_ready():
            raise HTTPException(
                status_code=503, detail="TTS service not ready"
            )

        audio_bytes, metadata = await tts.synthesize(
            text=request.text,
            speed=request.speed,
            output_format=request.format,
        )

        # Encode to base64
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        self._last_activity = datetime.now()

        return SynthesisResponse(
            audio_base64=audio_base64,
            text_length=len(request.text),
            audio_duration_seconds=metadata.audio_duration_seconds,
            processing_time_ms=processing_time,
            format=request.format,
        )

    # ========================================================================
    # MCP Tool: audio_health (Tool #46)
    # ========================================================================

    def audio_health(self) -> AudioHealthResponse:
        """
        MCP Tool #46: Check audio service health.

        PRD Section 8.12.5 GET /health compliance.

        Returns:
            AudioHealthResponse with service status
        """
        stt = self._get_stt()
        tts = self._get_tts()

        stt_status = stt.get_status()
        tts_status = tts.get_status()

        # Determine overall status
        if stt_status.model_loaded and tts_status.model_loaded:
            overall = "ok"
        elif stt_status.available or tts_status.available:
            overall = "degraded"
        else:
            overall = "unavailable"

        return AudioHealthResponse(
            status=overall,
            stt={
                "available": stt_status.available,
                "model_loaded": stt_status.model_loaded,
                "model_name": stt_status.model_name,
                "engine": "vosk",
            },
            tts={
                "available": tts_status.available,
                "model_loaded": tts_status.model_loaded,
                "model_name": tts_status.model_name,
                "engine": "coqui",
            },
            wake_word={
                "enabled": self._wake_config.enabled,
                "patterns": self._wake_config.wake_words,
                "sensitivity": self._wake_config.sensitivity,
            },
        )

    # ========================================================================
    # MCP Tool: get_audio_status (Tool #47)
    # ========================================================================

    def get_audio_status(self) -> AudioSessionStatus:
        """
        MCP Tool #47: Get detailed audio session status.

        PRD Section 8.12.5 GET /api/audio/status compliance.

        Returns:
            AudioSessionStatus with session and service details
        """
        stt = self._get_stt()
        tts = self._get_tts()

        # Determine current state
        state = AudioSessionState.IDLE
        if self._wake_config.enabled:
            state = AudioSessionState.WAKE_LISTENING

        return AudioSessionStatus(
            session_id=self._active_session,
            state=state,
            wake_word_enabled=self._wake_config.enabled,
            tts_enabled=True,
            stt_available=stt.is_ready() if stt else False,
            tts_available=tts.is_ready() if tts else False,
            last_activity=(
                self._last_activity.isoformat()
                if self._last_activity
                else None
            ),
        )

    # ========================================================================
    # Wake Word Management Tools
    # ========================================================================

    def wake_word_enable(
        self, config: Optional[WakeWordConfig] = None
    ) -> dict[str, Any]:
        """
        Enable wake word detection.

        Dashboard-bound tool for starting always-on listening mode.

        Args:
            config: Optional wake word configuration

        Returns:
            Status dict with enabled state
        """
        if config:
            self._wake_config = config
        self._wake_config.enabled = True
        self._last_activity = datetime.now()

        logger.info(
            f"Wake word detection enabled: {self._wake_config.wake_words}"
        )

        return {
            "enabled": True,
            "wake_words": self._wake_config.wake_words,
            "sensitivity": self._wake_config.sensitivity,
            "timeout_seconds": self._wake_config.timeout_seconds,
        }

    def wake_word_disable(self) -> dict[str, Any]:
        """
        Disable wake word detection.

        Dashboard-bound tool for stopping always-on listening mode.

        Returns:
            Status dict with disabled state
        """
        self._wake_config.enabled = False
        self._last_activity = datetime.now()

        logger.info("Wake word detection disabled")

        return {"enabled": False}

    def wake_word_status(self) -> dict[str, Any]:
        """
        Get wake word detection status.

        Returns:
            Status dict with wake word configuration
        """
        return {
            "enabled": self._wake_config.enabled,
            "wake_words": self._wake_config.wake_words,
            "sensitivity": self._wake_config.sensitivity,
            "timeout_seconds": self._wake_config.timeout_seconds,
        }

    # ========================================================================
    # Session Management Tools
    # ========================================================================

    def audio_session_start(
        self, config: Optional[AudioSessionConfig] = None
    ) -> dict[str, Any]:
        """
        Start an audio interaction session.

        Creates a new session with configuration for:
        - Auto-send after transcription
        - TTS for responses
        - Wake word mode

        Args:
            config: Session configuration

        Returns:
            Session status dict
        """
        if config is None:
            config = AudioSessionConfig()

        self._sessions[config.session_id] = config
        self._active_session = config.session_id

        if config.wake_word_enabled:
            self.wake_word_enable()

        self._last_activity = datetime.now()

        logger.info(f"Audio session started: {config.session_id}")

        return {
            "session_id": config.session_id,
            "auto_send": config.auto_send,
            "tts_enabled": config.tts_enabled,
            "wake_word_enabled": config.wake_word_enabled,
            "language": config.language,
        }

    def audio_session_end(
        self, session_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        End an audio session.

        Cleans up session state and disables wake word if enabled.

        Args:
            session_id: Session to end (default: active session)

        Returns:
            Session end status
        """
        target_id = session_id or self._active_session

        if target_id and target_id in self._sessions:
            del self._sessions[target_id]

        if target_id == self._active_session:
            self._active_session = None
            self.wake_word_disable()

        self._last_activity = datetime.now()

        logger.info(f"Audio session ended: {target_id}")

        return {
            "session_id": target_id,
            "ended": True,
        }


# ============================================================================
# FastAPI Router
# ============================================================================

audio_controller_router = APIRouter(
    prefix="/api/audio", tags=["Audio Controller"]
)

# Singleton instance
_audio_controller: Optional[AudioControllerService] = None


def get_audio_controller() -> AudioControllerService:
    """Get or create audio controller singleton."""
    global _audio_controller
    if _audio_controller is None:
        _audio_controller = AudioControllerService()
    return _audio_controller


# MCP Tool Endpoints


@audio_controller_router.post(
    "/stt/transcribe", response_model=TranscriptionResponse
)
async def mcp_stt_transcribe(request: TranscriptionRequest):
    """
    MCP Tool #44: Speech-to-Text transcription.

    Transcribes base64-encoded audio to text with:
    - PII redaction
    - Wake word detection
    - Confidence scoring
    """
    controller = get_audio_controller()
    return await controller.stt_transcribe(request)


@audio_controller_router.post(
    "/tts/synthesize", response_model=SynthesisResponse
)
async def mcp_tts_synthesize(request: SynthesisRequest):
    """
    MCP Tool #45: Text-to-Speech synthesis.

    Synthesizes text to base64-encoded audio with:
    - Speed control
    - Format selection (wav, mp3)
    """
    controller = get_audio_controller()
    return await controller.tts_synthesize(request)


@audio_controller_router.get("/health", response_model=AudioHealthResponse)
async def mcp_audio_health():
    """
    MCP Tool #46: Audio service health check.

    Returns status of STT, TTS, and wake word services.
    """
    controller = get_audio_controller()
    return controller.audio_health()


@audio_controller_router.get("/status", response_model=AudioSessionStatus)
async def mcp_audio_status():
    """
    MCP Tool #47: Audio session status.

    Returns detailed status of current audio session.
    """
    controller = get_audio_controller()
    return controller.get_audio_status()


# Wake Word Endpoints


@audio_controller_router.post("/wake/enable")
async def mcp_wake_enable(config: Optional[WakeWordConfig] = None):
    """Enable wake word detection."""
    controller = get_audio_controller()
    return controller.wake_word_enable(config)


@audio_controller_router.post("/wake/disable")
async def mcp_wake_disable():
    """Disable wake word detection."""
    controller = get_audio_controller()
    return controller.wake_word_disable()


@audio_controller_router.get("/wake/status")
async def mcp_wake_status():
    """Get wake word status."""
    controller = get_audio_controller()
    return controller.wake_word_status()


# Session Endpoints


@audio_controller_router.post("/session/start")
async def mcp_session_start(config: Optional[AudioSessionConfig] = None):
    """Start an audio interaction session."""
    controller = get_audio_controller()
    return controller.audio_session_start(config)


@audio_controller_router.post("/session/end")
async def mcp_session_end(session_id: Optional[str] = None):
    """End an audio session."""
    controller = get_audio_controller()
    return controller.audio_session_end(session_id)


# ============================================================================
# Registration Function for Gateway
# ============================================================================


def register(app, settings=None) -> None:
    """
    Register Audio Controller routes with the FastAPI app.

    Called by gateway.py to include audio controller endpoints.
    """
    app.include_router(audio_controller_router)
    logger.info("Audio Controller routes registered at /api/audio")
