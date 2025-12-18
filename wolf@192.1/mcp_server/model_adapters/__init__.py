"""Model adapters package exposing base interface and concrete adapters."""

from .base import AdapterError, ModelAdapter, safe_import  # noqa: F401
from .local_llm_adapter import LocalLLMAdapter  # noqa: F401
