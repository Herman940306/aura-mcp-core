from abc import ABC, abstractmethod
from typing import Any


class BaseModelBackend(ABC):
    """Abstract base class for model backends."""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Generate text from the model."""
        pass

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embeddings for the text."""
        pass

    @abstractmethod
    async def health(self) -> bool:
        """Check if the backend is healthy."""
        pass
