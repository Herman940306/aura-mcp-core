import logging
import os

import httpx
from fastapi import FastAPI

from ..core.health import health_aggregator
from . import (
    embedding_service,
    llm_proxy_service,
    model_gateway,
    rag_service,
    role_engine_service,
)
from .audio_io import audio_controller, stt_service, tts_service

logger = logging.getLogger(__name__)

# Each sub-service provides a function register_<name>(app, settings)


async def ping_backend() -> bool:
    """Check health of ML backend."""
    url = os.getenv("IDE_AGENTS_BACKEND_URL", "http://aura-ia-ml:8001")
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            resp = await client.get(f"{url}/health")
            if resp.status_code == 200:
                return True
            logger.warning(
                f"ML Backend health check failed: {resp.status_code}"
            )
            return False
    except Exception as e:
        logger.warning(f"ML Backend health check exception: {e}")
        return False


def register_service_routes(app: FastAPI, settings) -> None:
    # Register core health check
    health_aggregator.register("ml_backend", ping_backend)

    llm_proxy_service.register(app, settings)
    embedding_service.register(app, settings)
    rag_service.register(app, settings)
    role_engine_service.register(app, settings)
    model_gateway.register(app, settings)

    # Audio I/O Layer (PRD Section 8.12)
    stt_service.register(app, settings)
    tts_service.register(app, settings)
    audio_controller.register(app, settings)  # MCP-bound audio tools
