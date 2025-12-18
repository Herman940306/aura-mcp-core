"""LLM Proxy Service with multiple backend support."""

import logging
import os
from enum import Enum

import httpx
from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])


class LLMBackend(str, Enum):
    """Supported LLM backends."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    VLLM = "vllm"


class GenerateRequest(BaseModel):
    """Request to generate text."""

    prompt: str = Field(..., description="Input prompt")
    model: str = Field("llama3.2:1b", description="Model name")
    max_tokens: int = Field(256, description="Maximum tokens to generate")
    temperature: float = Field(0.7, description="Sampling temperature")
    backend: LLMBackend = Field(
        LLMBackend.OLLAMA, description="LLM backend to use"
    )


class GenerateResponse(BaseModel):
    """Generation response."""

    generated_text: str
    model: str
    backend: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


async def generate_ollama(
    prompt: str, model: str, max_tokens: int, temperature: float
) -> dict:
    """Generate using Ollama backend."""
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            },
        )
        response.raise_for_status()
        result = response.json()

        return {
            "generated_text": result.get("response", ""),
            "prompt_tokens": result.get("prompt_eval_count"),
            "completion_tokens": result.get("eval_count"),
        }


async def generate_openai(
    prompt: str, model: str, max_tokens: int, temperature: float
) -> dict:
    """Generate using OpenAI API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="OPENAI_API_KEY not configured"
        )

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        result = response.json()

        choice = result["choices"][0]
        usage = result.get("usage", {})

        return {
            "generated_text": choice["message"]["content"],
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }


async def generate_vllm(
    prompt: str, model: str, max_tokens: int, temperature: float
) -> dict:
    """Generate using vLLM backend."""
    vllm_url = os.getenv("VLLM_URL", "http://localhost:9204")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{vllm_url}/v1/completions",
            json={
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        result = response.json()

        choice = result["choices"][0]
        usage = result.get("usage", {})

        return {
            "generated_text": choice["text"],
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }


@router.post("/generate", response_model=GenerateResponse)
async def generate_text(request: GenerateRequest):
    """Generate text using specified LLM backend.

    Supports multiple backends:
    - ollama: Local Ollama server
    - openai: OpenAI API
    - vllm: vLLM server
    """
    try:
        # Route to appropriate backend
        if request.backend == LLMBackend.OLLAMA:
            result = await generate_ollama(
                request.prompt,
                request.model,
                request.max_tokens,
                request.temperature,
            )
        elif request.backend == LLMBackend.OPENAI:
            result = await generate_openai(
                request.prompt,
                request.model,
                request.max_tokens,
                request.temperature,
            )
        elif request.backend == LLMBackend.VLLM:
            result = await generate_vllm(
                request.prompt,
                request.model,
                request.max_tokens,
                request.temperature,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported backend: {request.backend}",
            )

        return GenerateResponse(
            generated_text=result["generated_text"],
            model=request.model,
            backend=request.backend.value,
            prompt_tokens=result.get("prompt_tokens"),
            completion_tokens=result.get("completion_tokens"),
        )

    except httpx.HTTPStatusError as e:
        logger.error(f"LLM backend error: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Backend error: {e.response.text}",
        )
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def llm_health():
    """Health check for LLM proxy service."""
    backends_status = {}

    # Check Ollama
    try:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
            backends_status["ollama"] = (
                "healthy" if response.status_code == 200 else "unhealthy"
            )
    except Exception:
        backends_status["ollama"] = "unavailable"

    # Check OpenAI (just check if key is set)
    backends_status["openai"] = (
        "configured" if os.getenv("OPENAI_API_KEY") else "not_configured"
    )

    # Check vLLM
    try:
        vllm_url = os.getenv("VLLM_URL", "http://localhost:9204")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{vllm_url}/health")
            backends_status["vllm"] = (
                "healthy" if response.status_code == 200 else "unhealthy"
            )
    except Exception:
        backends_status["vllm"] = "unavailable"

    return {"status": "healthy", "backends": backends_status}


def register(app: FastAPI, settings) -> None:
    """Register LLM proxy service routes."""
    app.include_router(router)
    logger.info("LLM Proxy service registered")
