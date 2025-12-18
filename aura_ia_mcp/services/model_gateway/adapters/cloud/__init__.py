"""
Cloud Model Adapters for Aura IA MCP.

This module provides adapters for cloud-based LLM APIs that follow
the same enterprise patterns as the local Ollama adapter:
- Token budget management (per-provider)
- Circuit breaker for fault tolerance
- Resource offloading rules
- Security validation

Cloud Providers Supported:
- OLLAMA_CLOUD (FREE!) - All models via Ollama Cloud infrastructure:
  * DeepSeek V3.1 671B - Advanced reasoning
  * GPT-OSS 120B - OpenAI-compatible
  * Qwen3 Coder 480B - Code generation specialist
  * Gemini 3 Pro Preview - Google's latest preview
  * Kimi K2 1T - Long context flagship
  * Minimax M2 - Multi-modal specialist
- Google (Gemini) - FREE TIER FIRST!
- Moonshot (Kimi) - Long context
- Minimax - Chinese language specialist
- Alibaba (Qwen) - Enterprise/code capabilities

RESOURCE OFFLOADING RULES:
1. ALWAYS check local Ollama first before cloud
2. Offload to cloud ONLY when:
   - Local model unavailable (circuit open)
   - Context exceeds local capacity (>128K)
   - User explicitly requests cloud model
   - Task requires cloud-specific capabilities
3. Track costs separately per provider
4. Respect rate limits (RPM/TPM quotas)
5. OLLAMA CLOUD FIRST - all models are FREE via Ollama's cloud infrastructure
"""

# Base infrastructure
from .base_cloud import (
    ALIBABA_MODELS,
    ALL_CLOUD_MODELS,
    GOOGLE_MODELS,
    MOONSHOT_MODELS,
    OLLAMA_CLOUD_MODELS,
    BaseCloudAdapter,
    CloudCircuitBreaker,
    CloudModelConfig,
    CloudProvider,
    CloudProviderBudget,
    CloudSecurityManager,
    ResourceOffloadManager,
)

# Factory and gateway
from .factory import (
    CloudAdapterFactory,
    get_cloud_adapter,
    get_cloud_factory,
    get_free_cloud_adapter,
)
from .gateway import (
    RoutingDecision,
    RoutingPolicy,
    RoutingTarget,
    UnifiedModelGateway,
    generate,
    get_unified_gateway,
)

# Provider adapters
from .gemini import GeminiAdapter, create_gemini_adapter
from .kimi import KimiAdapter, create_kimi_adapter
from .minimax import MinimaxAdapter, create_minimax_adapter
from .ollama_cloud import OllamaCloudAdapter, create_ollama_cloud_adapter
from .qwen_cloud import QwenCloudAdapter, create_qwen_adapter

__all__ = [
    # Enums and configs
    "CloudProvider",
    "CloudModelConfig",
    "RoutingTarget",
    "RoutingPolicy",
    "RoutingDecision",
    # Model registries
    "ALL_CLOUD_MODELS",
    "OLLAMA_CLOUD_MODELS",
    "GOOGLE_MODELS",
    "MOONSHOT_MODELS",
    "ALIBABA_MODELS",
    # Base classes
    "BaseCloudAdapter",
    "CloudProviderBudget",
    "CloudCircuitBreaker",
    "CloudSecurityManager",
    "ResourceOffloadManager",
    # Provider adapters
    "GeminiAdapter",
    "MinimaxAdapter",
    "KimiAdapter",
    "QwenCloudAdapter",
    "OllamaCloudAdapter",
    # Factory functions
    "create_gemini_adapter",
    "create_minimax_adapter",
    "create_kimi_adapter",
    "create_qwen_adapter",
    "create_ollama_cloud_adapter",
    # Factory and gateway
    "CloudAdapterFactory",
    "UnifiedModelGateway",
    # Global accessors
    "get_cloud_factory",
    "get_cloud_adapter",
    "get_free_cloud_adapter",
    "get_unified_gateway",
    "generate",
]
