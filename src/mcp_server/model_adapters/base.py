"""Base interfaces for model adapters (LLM / embedding).

Adapters standardize inference across providers so higher-level orchestration
can switch implementations without changing call sites.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ModelAdapter(ABC):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text given prompt; simple blocking API."""

    def embed(self, texts: list[str]) -> list[list[float]]:  # optional
        raise NotImplementedError("Embedding not implemented for adapter")

    def supports_streaming(self) -> bool:
        return False


class AdapterError(RuntimeError):
    pass


def safe_import(module: str) -> Any | None:  # noqa: ANN401
    try:  # narrow exceptions
        import importlib

        return importlib.import_module(module)
    except (ImportError, ValueError):
        return None


__all__ = ["ModelAdapter", "AdapterError", "safe_import"]
