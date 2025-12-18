"""
Aura IA Model Lifecycle Manager

Intelligent Model Lifecycle Management for Ollama models with:
- Auto-offload: Heavy models offload after idle timeout
- Always-loaded: phi3.5:3.8b stays resident for fast fallback
- Pre-warm: Load models based on usage patterns
- RAM Protection: Prevent loading too many concurrent models

PRD Section 8.13 compliant - Ollama Agent Integration
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ChatMode(str, Enum):
    """Chat modes that determine model selection."""

    CHAT = "chat"  # Quick responses, phi3.5
    CONCIERGE = "concierge"  # Best reasoning, llama3.1
    MCP_COMMAND = "mcp_command"  # Tool calling, qwen2.5-coder
    DEBUG = "debug"  # Code-focused, qwen2.5-coder
    DEBATE = "debate"  # Multi-model debates


@dataclass
class ModelConfig:
    """Configuration for a single Ollama model."""

    name: str
    idle_timeout_minutes: int
    always_loaded: bool = False
    ram_estimate_gb: float = 4.0
    context_window: int = 4096
    strengths: list[str] = field(default_factory=list)
    primary_mode: Optional[ChatMode] = None


# Model configurations based on quality assessment
MODEL_CONFIGS: dict[str, ModelConfig] = {
    # Always loaded - never offload (Chat mode, fast fallback)
    "phi3.5:3.8b": ModelConfig(
        name="phi3.5:3.8b",
        idle_timeout_minutes=0,  # Never offload
        always_loaded=True,
        ram_estimate_gb=3.0,
        context_window=4096,
        strengths=["fast_response", "routing", "quick_tasks"],
        primary_mode=ChatMode.CHAT,
    ),
    # Concierge - best reasoner (longer timeout, used frequently)
    "llama3.1:8b": ModelConfig(
        name="llama3.1:8b",
        idle_timeout_minutes=0,  # Never offload (User Request)
        always_loaded=True,
        ram_estimate_gb=5.0,
        context_window=128000,  # 128K context!
        strengths=["reasoning", "long_context", "general"],
        primary_mode=ChatMode.CONCIERGE,
    ),
    # MCP Command / Debug - best for tool calling & code
    "qwen2.5-coder:7b": ModelConfig(
        name="qwen2.5-coder:7b",
        idle_timeout_minutes=10,  # Offload after 10 min idle
        always_loaded=False,
        ram_estimate_gb=5.0,
        context_window=32768,
        strengths=["coding", "tool_calling", "implementation"],
        primary_mode=ChatMode.MCP_COMMAND,
    ),
    # Debate model - short timeout (only used in scheduled debates)
    "deepseek-r1:8b": ModelConfig(
        name="deepseek-r1:8b",
        idle_timeout_minutes=5,  # Offload quickly after debate ends
        always_loaded=False,
        ram_estimate_gb=5.0,
        context_window=65536,
        strengths=["reasoning", "debates", "analysis"],
        primary_mode=ChatMode.DEBATE,
    ),
}

# Mode to model mapping
MODE_TO_MODEL: dict[ChatMode, str] = {
    ChatMode.CHAT: "phi3.5:3.8b",
    ChatMode.CONCIERGE: "llama3.1:8b",
    ChatMode.MCP_COMMAND: "qwen2.5-coder:7b",
    ChatMode.DEBUG: "qwen2.5-coder:7b",
    ChatMode.DEBATE: "deepseek-r1:8b",
}

# RAM limits
MAX_TOTAL_RAM_GB = 20.0  # Leave buffer from 24GB
MAX_CONCURRENT_MODELS = 3  # Prevent loading all 4 at once


@dataclass
class LoadedModel:
    """Tracks a currently loaded model."""

    name: str
    loaded_at: datetime
    last_used: datetime
    ram_estimate_gb: float


class ModelLifecycleManager:
    """
    Manages model loading/offloading based on usage patterns.

    Features:
    - Automatic offloading of idle models
    - RAM budget protection
    - Pre-warming based on mode
    - Fallback chain for reliability
    """

    def __init__(
        self,
        ollama_url: str = "http://aura-ia-ollama:11434",
        max_ram_gb: float = MAX_TOTAL_RAM_GB,
        max_concurrent: int = MAX_CONCURRENT_MODELS,
    ):
        self.ollama_url = ollama_url
        self.max_ram_gb = max_ram_gb
        self.max_concurrent = max_concurrent
        self.loaded_models: dict[str, LoadedModel] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        """Start the lifecycle manager background tasks."""
        if self._started:
            return

        self._started = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Sync with Ollama to see what's already loaded
        await self._sync_with_ollama()

        # Ensure phi3.5 is always loaded on startup
        always_loaded = [m for m in MODEL_CONFIGS.values() if m.always_loaded]
        for model in always_loaded:
            if model.name not in self.loaded_models:
                await self._load_model(model.name)
                logger.info(f"✅ Pre-loaded always-on model: {model.name}")

    async def _sync_with_ollama(self) -> None:
        """Sync loaded_models with Ollama's actual state."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Ollama /api/ps shows currently loaded models
                response = await client.get(f"{self.ollama_url}/api/ps")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    for model_info in models:
                        model_name = model_info.get("name", "")
                        if model_name and model_name not in self.loaded_models:
                            # Get RAM estimate from config or use default
                            config = MODEL_CONFIGS.get(
                                model_name, ModelConfig(model_name, 10)
                            )
                            self.loaded_models[model_name] = LoadedModel(
                                name=model_name,
                                loaded_at=datetime.now(),
                                last_used=datetime.now(),
                                ram_estimate_gb=config.ram_estimate_gb,
                            )
                            logger.info(f"🔄 Synced existing model: {model_name}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to sync with Ollama: {e}")

    async def stop(self) -> None:
        """Stop the lifecycle manager."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self._started = False

    async def _cleanup_loop(self) -> None:
        """Background task that offloads idle models."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._offload_idle_models()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _offload_idle_models(self) -> None:
        """Offload models that have exceeded their idle timeout."""
        now = datetime.now()

        async with self._lock:
            for model_name, loaded in list(self.loaded_models.items()):
                config = MODEL_CONFIGS.get(model_name)

                if not config or config.always_loaded:
                    continue  # Skip always-loaded models

                idle_minutes = (now - loaded.last_used).total_seconds() / 60

                if idle_minutes > config.idle_timeout_minutes:
                    await self._offload_model(model_name)
                    logger.info(
                        f"♻️ Offloaded {model_name} after {idle_minutes:.1f} min idle"
                    )

    def _get_current_ram_usage(self) -> float:
        """Calculate current RAM usage of loaded models."""
        return sum(m.ram_estimate_gb for m in self.loaded_models.values())

    def _can_load_model(self, model_name: str) -> tuple[bool, str]:
        """Check if we can load a model within RAM/concurrency limits."""
        config = MODEL_CONFIGS.get(model_name)
        if not config:
            return False, f"Unknown model: {model_name}"

        # Already loaded?
        if model_name in self.loaded_models:
            return True, "Already loaded"

        # Check concurrent model limit
        non_always_loaded = len(
            [
                m
                for m in self.loaded_models.values()
                if not MODEL_CONFIGS.get(
                    m.name, ModelConfig(m.name, 0)
                ).always_loaded
            ]
        )

        if (
            non_always_loaded >= self.max_concurrent
            and not config.always_loaded
        ):
            return (
                False,
                f"Max concurrent models ({self.max_concurrent}) reached",
            )

        # Check RAM budget
        current_ram = self._get_current_ram_usage()
        if current_ram + config.ram_estimate_gb > self.max_ram_gb:
            return (
                False,
                f"RAM limit exceeded ({current_ram + config.ram_estimate_gb:.1f}GB > {self.max_ram_gb}GB)",
            )

        return True, "OK"

    async def ensure_loaded(self, model_name: str) -> bool:
        """
        Ensure a model is loaded before use.
        Returns True if model is ready.
        """
        async with self._lock:
            if model_name in self.loaded_models:
                # Update last used time
                self.loaded_models[model_name].last_used = datetime.now()
                return True

            # Check if we can load
            can_load, reason = self._can_load_model(model_name)
            if not can_load:
                logger.warning(f"Cannot load {model_name}: {reason}")

                # Try to make room by offloading oldest idle model
                if "concurrent" in reason.lower() or "ram" in reason.lower():
                    if await self._make_room_for_model(model_name):
                        can_load = True

                if not can_load:
                    return False

            # Load the model
            success = await self._load_model(model_name)
            if success:
                config = MODEL_CONFIGS.get(
                    model_name, ModelConfig(model_name, 10)
                )
                self.loaded_models[model_name] = LoadedModel(
                    name=model_name,
                    loaded_at=datetime.now(),
                    last_used=datetime.now(),
                    ram_estimate_gb=config.ram_estimate_gb,
                )
            return success

    async def _make_room_for_model(self, target_model: str) -> bool:
        """Try to offload models to make room for target model."""
        target_config = MODEL_CONFIGS.get(target_model)
        if not target_config:
            return False

        # Sort by last used (oldest first), excluding always-loaded
        candidates = [
            (name, loaded)
            for name, loaded in self.loaded_models.items()
            if not MODEL_CONFIGS.get(name, ModelConfig(name, 0)).always_loaded
        ]
        candidates.sort(key=lambda x: x[1].last_used)

        for name, _ in candidates:
            await self._offload_model(name)
            logger.info(f"♻️ Offloaded {name} to make room for {target_model}")

            can_load, _ = self._can_load_model(target_model)
            if can_load:
                return True

        return False

    async def _load_model(self, model_name: str) -> bool:
        """Load a model into Ollama."""
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                # Ollama loads model on first generate call
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "Hello",  # Minimal prompt to trigger load
                        "stream": False,
                        "options": {"num_predict": 1},  # Generate just 1 token
                    },
                )
                if response.status_code == 200:
                    logger.info(f"✅ Loaded {model_name}")
                    return True
                else:
                    logger.error(
                        f"❌ Failed to load {model_name}: HTTP {response.status_code}"
                    )
        except httpx.TimeoutException:
            logger.error(
                f"❌ Timeout loading {model_name} (model may be pulling)"
            )
        except Exception as e:
            logger.error(f"❌ Failed to load {model_name}: {e}")
        return False

    async def _offload_model(self, model_name: str) -> None:
        """Offload a model from memory."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Ollama uses keep_alive=0 to immediately unload
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "",
                        "keep_alive": 0,  # Immediately unload
                    },
                )
                if response.status_code == 200:
                    self.loaded_models.pop(model_name, None)
        except Exception as e:
            logger.warning(f"⚠️ Failed to offload {model_name}: {e}")
            # Still remove from tracking even if offload failed
            self.loaded_models.pop(model_name, None)

    def get_model_for_mode(self, mode: ChatMode) -> str:
        """Get the recommended model for a chat mode."""
        return MODE_TO_MODEL.get(mode, "phi3.5:3.8b")

    def get_fallback_chain(self, model_name: str) -> list[str]:
        """Get fallback models if primary fails."""
        # phi3.5 is always the final fallback
        fallbacks = {
            "llama3.1:8b": ["qwen2.5-coder:7b", "phi3.5:3.8b"],
            "qwen2.5-coder:7b": ["llama3.1:8b", "phi3.5:3.8b"],
            "deepseek-r1:8b": ["llama3.1:8b", "phi3.5:3.8b"],
            "phi3.5:3.8b": [],  # No fallback, it's always loaded
        }
        return fallbacks.get(model_name, ["phi3.5:3.8b"])

    async def ensure_loaded_with_fallback(
        self, model_name: str
    ) -> tuple[str, bool]:
        """
        Ensure a model is loaded, falling back if needed.
        Returns (actual_model_used, is_primary).
        """
        if await self.ensure_loaded(model_name):
            return model_name, True

        # Try fallbacks
        for fallback in self.get_fallback_chain(model_name):
            if await self.ensure_loaded(fallback):
                logger.warning(
                    f"Using fallback {fallback} instead of {model_name}"
                )
                return fallback, False

        # Ultimate fallback - phi3.5 should always be loaded
        return "phi3.5:3.8b", False

    async def get_status(self) -> dict:
        """Get current model loading status."""
        # Sync with Ollama before returning status
        await self._sync_with_ollama()
        
        now = datetime.now()
        return {
            "loaded_models": list(self.loaded_models.keys()),
            "current_ram_gb": self._get_current_ram_usage(),
            "max_ram_gb": self.max_ram_gb,
            "max_concurrent": self.max_concurrent,
            "model_details": {
                name: {
                    "loaded_at": loaded.loaded_at.isoformat(),
                    "last_used": loaded.last_used.isoformat(),
                    "idle_minutes": round(
                        (now - loaded.last_used).total_seconds() / 60, 1
                    ),
                    "timeout_minutes": MODEL_CONFIGS.get(
                        name, ModelConfig(name, 10)
                    ).idle_timeout_minutes,
                    "ram_gb": loaded.ram_estimate_gb,
                    "always_loaded": MODEL_CONFIGS.get(
                        name, ModelConfig(name, 10)
                    ).always_loaded,
                }
                for name, loaded in self.loaded_models.items()
            },
            "available_models": list(MODEL_CONFIGS.keys()),
            "mode_mappings": {
                mode.value: model for mode, model in MODE_TO_MODEL.items()
            },
        }

    async def health_check(self) -> dict:
        """Check Ollama service health."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    available = [
                        m.get("name", "") for m in data.get("models", [])
                    ]
                    return {
                        "status": "healthy",
                        "ollama_url": self.ollama_url,
                        "available_models": available,
                        "loaded_models": list(self.loaded_models.keys()),
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "ollama_url": self.ollama_url,
                "error": str(e),
            }

        return {"status": "unhealthy", "error": "Unknown error"}


# Singleton instance
model_manager = ModelLifecycleManager()


async def get_model_manager() -> ModelLifecycleManager:
    """Get or initialize the model manager singleton."""
    if not model_manager._started:
        await model_manager.start()
    return model_manager
