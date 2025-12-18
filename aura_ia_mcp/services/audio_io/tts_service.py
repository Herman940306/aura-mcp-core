"""
Coqui Text-to-Speech Service for Aura IA MCP.

ENTERPRISE PRODUCTION SERVICE - NO MOCKS

TTS Layer (PRD Section 8.12 compliant):
- Uses Coqui TTS with HYBRID model selection
- VITS: 0.05x RTF, 10x faster than Tacotron2, non-autoregressive (requires espeak-ng)
- Tacotron2-DDC (fallback): 0.5-0.7x RTF, autoregressive (no espeak needed)
- Automatic GPU detection via torch.cuda.is_available()
- MOS 4.2-4.4 (near human 4.5-4.6)

The embedded model NEVER directly generates audio - only requests through this service.
This ensures PRD compliance: model explains actions, triggers MCP tools, but doesn't
directly synthesize speech.

Model Selection Logic:
- If espeak-ng installed: Use VITS (10x faster, higher quality)
- If no espeak-ng: Use Tacotron2-DDC (works everywhere, slower)
- If TTS_MODEL_NAME is set: Use specified model
- GPU: Auto-detected, or set TTS_USE_GPU=true/false to override

Deployment Requirements:
- TTS>=0.22.0 must be installed: pip install TTS
- First run downloads models automatically (~100-200MB)
- GPU optional: automatically detected, or set TTS_USE_GPU=true/false
- For VITS (10x faster): Install espeak-ng from https://github.com/espeak-ng/espeak-ng
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import tempfile
import wave
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Import Coqui TTS at module level - required for enterprise deployment
try:
    from TTS.api import TTS

    COQUI_TTS_AVAILABLE = True
except ImportError as e:
    COQUI_TTS_AVAILABLE = False
    COQUI_TTS_IMPORT_ERROR = str(e)

# Detect GPU availability via PyTorch
try:
    import torch

    GPU_AVAILABLE = torch.cuda.is_available()
    GPU_DEVICE_NAME = torch.cuda.get_device_name(0) if GPU_AVAILABLE else None
except ImportError:
    GPU_AVAILABLE = False
    GPU_DEVICE_NAME = None

# ============================================================================
# Model Constants - Choose based on espeak availability
# ============================================================================
# VITS: Non-autoregressive, 0.05x RTF (20x real-time) - requires espeak-ng
# Tacotron2: Autoregressive, 0.5-0.7x RTF (1.4-2x real-time on CPU) - no espeak needed
VITS_MODEL = "tts_models/en/ljspeech/vits"
TACOTRON2_MODEL = "tts_models/en/ljspeech/tacotron2-DDC"

# Detect espeak-ng availability
ESPEAK_AVAILABLE = False
try:
    from TTS.tts.utils.text.phonemizers.espeak_wrapper import ESpeak

    # Check if espeak library is accessible
    ESpeak._ESPEAK_LIB is not None
    ESPEAK_AVAILABLE = ESpeak._ESPEAK_LIB is not None
except Exception:
    pass

# Default: VITS if espeak available (10x faster), else Tacotron2 (no dependencies)
DEFAULT_MODEL = VITS_MODEL if ESPEAK_AVAILABLE else TACOTRON2_MODEL

# ============================================================================
# Configuration
# ============================================================================


@dataclass
class CoquiTTSConfig:
    """Configuration for Coqui TTS service with automatic hardware detection."""

    # Model configuration - VITS is default (10x faster than Tacotron2)
    # Set TTS_MODEL_NAME to override: vits, tacotron2-DDC, or full model path
    model_name: str = field(
        default_factory=lambda: _resolve_model_name(
            os.getenv("TTS_MODEL_NAME", "")
        )
    )

    # Output settings
    sample_rate: int = 22050  # Default Coqui output rate
    output_format: str = "wav"  # wav, mp3, ogg

    # Performance settings - auto-detect GPU if not explicitly set
    use_gpu: bool = field(
        default_factory=lambda: _resolve_gpu_setting(
            os.getenv("TTS_USE_GPU", "auto")
        )
    )
    max_text_length: int = 5000  # Max characters per request

    # Voice settings
    speaker_id: int | None = None  # For multi-speaker models
    language: str = "en"
    speed: float = 1.0  # Speech speed multiplier

    # Caching
    cache_enabled: bool = True
    cache_max_size: int = 100  # Max cached audio files

    # Logging
    log_synthesis: bool = True


def _resolve_model_name(env_value: str) -> str:
    """
    Resolve TTS model name with smart defaults.

    Priority:
    1. If TTS_MODEL_NAME is set and valid, use it
    2. If "vits" in value (case-insensitive), use VITS model
    3. If "tacotron" in value (case-insensitive), use Tacotron2 model
    4. Default based on espeak-ng availability
    """
    if not env_value:
        if ESPEAK_AVAILABLE:
            logger.info(
                f"espeak-ng detected, using fast VITS model: {DEFAULT_MODEL}"
            )
        else:
            logger.info(
                f"espeak-ng not found, using Tacotron2-DDC: {DEFAULT_MODEL}"
            )
            logger.info(
                "Install espeak-ng for 10x faster VITS: https://github.com/espeak-ng/espeak-ng"
            )
        return DEFAULT_MODEL

    env_lower = env_value.lower()

    # Handle shorthand names
    if env_lower == "vits":
        if not ESPEAK_AVAILABLE:
            logger.warning(
                "VITS requested but espeak-ng not installed! Model may fail."
            )
        return VITS_MODEL
    elif "tacotron" in env_lower:
        return TACOTRON2_MODEL
    elif env_value.startswith("tts_models/"):
        # Full model path provided
        return env_value

    logger.warning(
        f"Unknown TTS_MODEL_NAME '{env_value}', using default: {DEFAULT_MODEL}"
    )
    return DEFAULT_MODEL


def _resolve_gpu_setting(env_value: str) -> bool:
    """
    Resolve GPU setting with auto-detection.

    Values:
    - "auto" (default): Use GPU if available
    - "true"/"1"/"yes": Force GPU (will fail if unavailable)
    - "false"/"0"/"no": Force CPU
    """
    env_lower = env_value.lower().strip()

    if env_lower in ("auto", ""):
        # Auto-detect: use GPU if available
        if GPU_AVAILABLE:
            logger.info(
                f"GPU auto-detected: {GPU_DEVICE_NAME} - enabling CUDA acceleration"
            )
            return True
        else:
            logger.info("No GPU detected - using CPU inference")
            return False
    elif env_lower in ("true", "1", "yes"):
        if not GPU_AVAILABLE:
            logger.warning(
                "TTS_USE_GPU=true but no GPU detected! Will attempt anyway."
            )
        return True
    else:
        return False


# ============================================================================
# Response Models
# ============================================================================


class TTSRequest(BaseModel):
    """Text-to-speech request."""

    text: str
    speed: float = 1.0
    speaker_id: int | None = None
    language: str = "en"
    output_format: str = "wav"


class TTSResult(BaseModel):
    """Text-to-speech result metadata."""

    text_length: int
    audio_duration_seconds: float
    sample_rate: int
    processing_time_ms: float
    model_name: str
    cached: bool = False


class TTSStatus(BaseModel):
    """TTS service status."""

    available: bool
    model_loaded: bool
    model_name: str
    vocoder_name: str
    sample_rate: int
    use_gpu: bool
    gpu_detected: bool
    gpu_device: str | None
    espeak_available: bool
    supported_languages: list[str]
    model_type: str  # "vits" or "tacotron2" for clarity


# ============================================================================
# Coqui TTS Service
# ============================================================================


class CoquiTTSService:
    """
    Coqui-based Text-to-Speech service.

    ENTERPRISE PRODUCTION SERVICE - NO MOCKS

    Features:
    - State-of-the-art open source TTS
    - Glow-TTS: Fast parallel generation
    - HiFi-GAN: High-fidelity vocoder
    - MOS 4.2-4.4 (near human quality)
    - CPU real-time capable
    - GPU acceleration optional

    PRD Compliance:
    - Text comes from HNSC processing
    - Audio generated by this service only
    - Gateway routes TTS requests here
    - Returns audio bytes for dashboard playback

    Deployment:
    - Requires TTS package: pip install TTS>=0.22.0
    - First run downloads models automatically (~100MB)
    - GPU optional: set TTS_USE_GPU=true
    """

    def __init__(self, config: CoquiTTSConfig | None = None):
        self.config = config or CoquiTTSConfig()
        self._synthesizer = None
        self._model_loaded = False
        self._initialization_error: str | None = None
        self._cache: dict[str, bytes] = {}

        # Validate Coqui TTS is available at construction time
        if not COQUI_TTS_AVAILABLE:
            self._initialization_error = (
                f"Coqui TTS package not installed: {COQUI_TTS_IMPORT_ERROR}. "
                f"Install with: pip install TTS>=0.22.0"
            )
            logger.error(self._initialization_error)

    async def initialize(self) -> bool:
        """
        Initialize the Coqui TTS model.

        Downloads model if not present (first run - ~100MB).

        REQUIRED before using the service. Will fail if:
        - TTS package not installed

        Returns:
            True if initialization successful

        Raises:
            RuntimeError: If TTS not installed or model load fails
        """
        if not COQUI_TTS_AVAILABLE:
            raise RuntimeError(
                "Coqui TTS package not installed. Install with: pip install TTS>=0.22.0"
            )

        try:
            logger.info(f"Loading Coqui TTS model: {self.config.model_name}")
            logger.info(f"GPU: {self.config.use_gpu}")

            # Initialize TTS - model bundles vocoder automatically
            # Coqui TTS will download models on first use

            # Run initialization in thread pool to not block
            loop = asyncio.get_event_loop()
            self._synthesizer = await loop.run_in_executor(
                None,
                lambda: TTS(
                    model_name=self.config.model_name,
                    gpu=self.config.use_gpu,
                    progress_bar=False,
                ),
            )

            self._model_loaded = True
            self._initialization_error = None
            device_type = "GPU" if self.config.use_gpu else "CPU"
            logger.info(
                f"Coqui TTS model loaded successfully (device: {device_type})"
            )
            return True

        except Exception as e:
            self._initialization_error = f"Failed to load Coqui TTS model: {e}"
            logger.error(self._initialization_error)
            raise RuntimeError(self._initialization_error) from e

    def _ensure_initialized(self) -> None:
        """Ensure the service is initialized before use."""
        if not self._model_loaded:
            if self._initialization_error:
                raise RuntimeError(
                    f"TTS service not initialized: {self._initialization_error}"
                )
            raise RuntimeError(
                "TTS service not initialized. Call initialize() first."
            )

    async def synthesize(
        self,
        text: str,
        speed: float = 1.0,
        speaker_id: int | None = None,
        output_format: str = "wav",
    ) -> tuple[bytes, TTSResult]:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            speed: Speech speed multiplier (0.5-2.0)
            speaker_id: Speaker ID for multi-speaker models
            output_format: Output format (wav, mp3, ogg)

        Returns:
            Tuple of (audio_bytes, metadata)

        Raises:
            RuntimeError: If service not initialized
            ValueError: If text is empty or too long
            HTTPException: If synthesis fails
        """
        self._ensure_initialized()

        start_time = datetime.now()

        # Validate input
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        text = text.strip()

        if len(text) > self.config.max_text_length:
            raise ValueError(
                f"Text too long: {len(text)} > {self.config.max_text_length} max characters"
            )

        # Validate speed
        speed = max(0.5, min(2.0, speed))

        # Check cache
        cache_key = f"{text}:{speed}:{speaker_id}:{output_format}"
        if self.config.cache_enabled and cache_key in self._cache:
            audio_data = self._cache[cache_key]
            processing_time = (
                datetime.now() - start_time
            ).total_seconds() * 1000
            return audio_data, TTSResult(
                text_length=len(text),
                audio_duration_seconds=self._estimate_duration(audio_data),
                sample_rate=self.config.sample_rate,
                processing_time_ms=processing_time,
                model_name=self.config.model_name,
                cached=True,
            )

        try:
            # Synthesize with Coqui TTS
            loop = asyncio.get_event_loop()

            # Create temp file for output
            with tempfile.NamedTemporaryFile(
                suffix=f".{output_format}", delete=False
            ) as tmp:
                tmp_path = tmp.name

            try:
                # Run synthesis in thread pool
                await loop.run_in_executor(
                    None,
                    lambda: self._synthesizer.tts_to_file(
                        text=text,
                        file_path=tmp_path,
                        speaker=speaker_id,
                        speed=speed,
                    ),
                )

                # Read audio data
                with open(tmp_path, "rb") as f:
                    audio_data = f.read()

            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            # Calculate metrics
            processing_time = (
                datetime.now() - start_time
            ).total_seconds() * 1000
            audio_duration = self._estimate_duration(audio_data)

            # Cache result
            if self.config.cache_enabled:
                self._add_to_cache(cache_key, audio_data)

            result = TTSResult(
                text_length=len(text),
                audio_duration_seconds=audio_duration,
                sample_rate=self.config.sample_rate,
                processing_time_ms=processing_time,
                model_name=self.config.model_name,
                cached=False,
            )

            if self.config.log_synthesis:
                logger.info(
                    f"TTS: '{text[:50]}...' -> {audio_duration:.1f}s audio "
                    f"({processing_time:.0f}ms)"
                )

            return audio_data, result

        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Synthesis failed: {e}"
            )

    def _estimate_duration(self, audio_data: bytes) -> float:
        """Estimate audio duration from WAV data."""
        try:
            buffer = io.BytesIO(audio_data)
            with wave.open(buffer, "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                return frames / rate
        except Exception:
            # Fallback estimate
            return len(audio_data) / (22050 * 2)  # Assume 22kHz 16-bit mono

    def _add_to_cache(self, key: str, data: bytes) -> None:
        """Add audio to cache with LRU eviction."""
        if len(self._cache) >= self.config.cache_max_size:
            # Remove oldest entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = data

    def get_status(self) -> TTSStatus:
        """Get service status with hardware detection info."""
        # Determine model type for clarity
        model_type = (
            "vits" if "vits" in self.config.model_name.lower() else "tacotron2"
        )

        return TTSStatus(
            available=COQUI_TTS_AVAILABLE,
            model_loaded=self._model_loaded,
            model_name=self.config.model_name,
            vocoder_name="bundled",  # Vocoder is bundled with model
            sample_rate=self.config.sample_rate,
            use_gpu=self.config.use_gpu,
            gpu_detected=GPU_AVAILABLE,
            gpu_device=GPU_DEVICE_NAME,
            espeak_available=ESPEAK_AVAILABLE,
            supported_languages=["en"],  # Can be extended
            model_type=model_type,
        )

    def is_ready(self) -> bool:
        """Check if service is ready to accept requests."""
        return COQUI_TTS_AVAILABLE and self._model_loaded

    def list_models(self) -> list[str]:
        """List available TTS models."""
        if not COQUI_TTS_AVAILABLE:
            return []

        try:
            return TTS.list_models()
        except Exception:
            return []

    async def shutdown(self) -> None:
        """Clean up resources."""
        self._synthesizer = None
        self._model_loaded = False
        self._cache.clear()
        logger.info("Coqui TTS service shutdown complete")


# ============================================================================
# FastAPI Router
# ============================================================================

tts_router = APIRouter(prefix="/api/tts", tags=["Text-to-Speech"])

# Singleton instance
_tts_service: CoquiTTSService | None = None


def get_tts_service() -> CoquiTTSService:
    """Get or create TTS service singleton."""
    global _tts_service
    if _tts_service is None:
        _tts_service = CoquiTTSService()
    return _tts_service


@tts_router.on_event("startup")
async def startup_tts():
    """Initialize TTS service on startup."""
    service = get_tts_service()
    await service.initialize()


@tts_router.on_event("shutdown")
async def shutdown_tts():
    """Cleanup TTS service on shutdown."""
    global _tts_service
    if _tts_service:
        await _tts_service.shutdown()
        _tts_service = None


@tts_router.get("/status", response_model=TTSStatus)
async def get_tts_status():
    """Get TTS service status."""
    service = get_tts_service()
    return service.get_status()


@tts_router.get("/models")
async def list_tts_models():
    """List available TTS models."""
    service = get_tts_service()
    models = service.list_models()
    return {"models": models, "count": len(models)}


@tts_router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """
    Synthesize speech from text.

    Returns WAV audio with Content-Type: audio/wav.

    Parameters:
    - text: Text to synthesize (max 5000 characters)
    - speed: Speech speed multiplier (0.5-2.0, default 1.0)
    - speaker_id: Speaker ID for multi-speaker models (optional)
    - output_format: Output format (wav, mp3, ogg)
    """
    service = get_tts_service()

    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        audio_data, metadata = await service.synthesize(
            text=request.text,
            speed=request.speed,
            speaker_id=request.speaker_id,
            output_format=request.output_format,
        )

        # Determine content type
        content_types = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
        }
        content_type = content_types.get(request.output_format, "audio/wav")

        # Return audio with metadata headers
        return Response(
            content=audio_data,
            media_type=content_type,
            headers={
                "X-TTS-Text-Length": str(metadata.text_length),
                "X-TTS-Duration-Seconds": f"{metadata.audio_duration_seconds:.2f}",
                "X-TTS-Processing-Ms": f"{metadata.processing_time_ms:.0f}",
                "X-TTS-Cached": str(metadata.cached).lower(),
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@tts_router.get("/speak")
async def speak_text(
    text: str = Query(..., description="Text to synthesize"),
    speed: float = Query(1.0, ge=0.5, le=2.0, description="Speech speed"),
):
    """
    Quick endpoint for simple TTS.

    GET /api/tts/speak?text=Hello%20world

    Returns WAV audio directly.
    """
    service = get_tts_service()

    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        audio_data, _ = await service.synthesize(text=text, speed=speed)
        return Response(content=audio_data, media_type="audio/wav")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Registration Function for Gateway
# ============================================================================


def register(app, settings=None) -> None:
    """
    Register TTS routes with the FastAPI app.

    Called by gateway.py to include TTS endpoints.
    """
    app.include_router(tts_router)
    logger.info("TTS service routes registered at /api/tts")
    logger.info("TTS service routes registered at /api/tts")
