"""Unit tests for model adapters (mock clients)."""

from __future__ import annotations

import pytest

from src.mcp_server.model_adapters.base import AdapterError, ModelAdapter
from src.mcp_server.model_adapters.ollama_adapter import OllamaAdapter
from src.mcp_server.model_adapters.openai_adapter import OpenAIAdapter


def test_adapter_interface():
    """Ensure base ModelAdapter defines contract."""

    class DummyAdapter(ModelAdapter):
        def generate(self, prompt: str, **kwargs) -> str:  # type: ignore[no-untyped-def]
            return f"echo:{prompt}"

    adapter = DummyAdapter("dummy")
    assert adapter.name == "dummy"
    assert adapter.generate("test") == "echo:test"
    assert not adapter.supports_streaming()


def test_ollama_adapter_missing_client():
    """Verify Ollama adapter raises when ollama package unavailable."""
    adapter = OllamaAdapter("llama2")
    # If ollama not installed, generate should raise AdapterError
    if adapter._client is None:
        with pytest.raises(AdapterError, match="ollama package not available"):
            adapter.generate("test")


def test_openai_adapter_missing_credentials():
    """Verify OpenAI adapter raises when credentials missing."""
    import os

    # Clear env
    old_key = os.environ.get("OPENAI_API_KEY")
    os.environ.pop("OPENAI_API_KEY", None)
    adapter = OpenAIAdapter("gpt-4o-mini")
    # Should raise AdapterError if client or key unavailable
    if adapter._api_key is None:
        with pytest.raises(AdapterError, match="API key not available"):
            adapter.generate("test")
    # Restore
    if old_key:
        os.environ["OPENAI_API_KEY"] = old_key


def test_adapter_supports_streaming():
    """Check streaming flag per adapter."""
    ollama = OllamaAdapter("llama2")
    openai = OpenAIAdapter("gpt-4o-mini")
    assert ollama.supports_streaming() is True
    assert openai.supports_streaming() is False
