# Audio I/O Layer for Aura IA MCP
# STT: Vosk (Kaldi-based, offline, CPU-optimized)
# TTS: Coqui TTS (Glow-TTS + HiFi-GAN, near-human quality)
# Controller: MCP-bound audio tools (PRD Section 8.12.7)
# PRD Section 8.12 compliant - Model never touches audio directly

from .audio_controller import (
    AudioControllerService,
    audio_controller_router,
    get_audio_controller,
)
from .stt_service import VoskSTTService, stt_router
from .tts_service import CoquiTTSService, tts_router

__all__ = [
    "VoskSTTService",
    "CoquiTTSService",
    "AudioControllerService",
    "stt_router",
    "tts_router",
    "audio_controller_router",
    "get_audio_controller",
]
