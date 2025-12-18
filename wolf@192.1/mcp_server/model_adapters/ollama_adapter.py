"""Ollama model adapter (local models)."""

from __future__ import annotations

from typing import Any

from .base import AdapterError, ModelAdapter, safe_import


class OllamaAdapter(ModelAdapter):
    def __init__(self, model: str = "llama2") -> None:
        super().__init__(name=f"ollama:{model}")
        self._model = model
        self._client = safe_import("ollama")

    def generate(self, prompt: str, **kwargs: Any) -> str:  # noqa: ANN401
        if not self._client:
            raise AdapterError("ollama package not available")
        try:
            response = self._client.generate(  # noqa: E501
                model=self._model,
                prompt=prompt,
                options={
                    "temperature": float(kwargs.get("temperature", 0.7)),
                    "num_predict": int(kwargs.get("max_tokens", 256)),
                },
            )
            return str(response.get("response", ""))
        except Exception as exc:  # noqa: BLE001
            raise AdapterError(str(exc)) from exc

    def supports_streaming(self) -> bool:
        return True


__all__ = ["OllamaAdapter"]
