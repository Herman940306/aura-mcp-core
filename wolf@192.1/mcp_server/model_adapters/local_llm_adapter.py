"""Local LLM Adapter using llama-cpp-python for embedded Phi-3 Mini / Qwen2.5.

This adapter loads a GGUF quantized model directly, enabling:
- Chat about MCP system
- Tool calling for MCP control
- Data retrieval from MCP services
- Debug assistance

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .base import AdapterError, ModelAdapter

# Lazy import to avoid startup delay
_llama_cpp = None


def _get_llama_cpp():
    """Lazy load llama_cpp module."""
    global _llama_cpp
    if _llama_cpp is None:
        try:
            from llama_cpp import Llama

            _llama_cpp = Llama
        except ImportError:
            _llama_cpp = False
    return _llama_cpp


# Default model path
DEFAULT_MODEL_DIR = (
    Path(__file__).parent.parent.parent.parent / "model_artifacts"
)

# ═══════════════════════════════════════════════════════════════════════════════
# DUAL MODEL ARCHITECTURE (PRD-aligned)
# ═══════════════════════════════════════════════════════════════════════════════
# TALKER (Tier-1): Phi-3-Mini-4K-Instruct Q4_K_S - Fast intent classification, routing
# WORKER (Tier-2): Qwen2.5-3B-Instruct Q4_K_M - Heavy reasoning, implementation
# ═══════════════════════════════════════════════════════════════════════════════

# Talker model candidates (fastest, intent routing)
TALKER_MODELS = [
    "Phi-3-mini-4k-instruct-q4.gguf",
    "phi-3-mini-4k-instruct-q4_k_s.gguf",
    "phi-3-mini-4k-instruct-q4_k_m.gguf",
]

# Worker model candidates (reasoning, implementation)
WORKER_MODELS = [
    "qwen2.5-3b-instruct-q4_k_m.gguf",
    "Qwen2.5-3B-Instruct-Q4_K_M.gguf",
    "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
]

# Legacy fallback priority (if specific model not found)
MODEL_PRIORITY = TALKER_MODELS + WORKER_MODELS


def _find_model_by_role(model_dir: Path, role: str = "talker") -> str | None:
    """Find the best available GGUF model for a specific role."""
    candidates = TALKER_MODELS if role == "talker" else WORKER_MODELS

    # Check role-specific candidates first
    for model_name in candidates:
        if (model_dir / model_name).exists():
            return model_name

    # Fallback: try any model from priority list
    for model_name in MODEL_PRIORITY:
        if (model_dir / model_name).exists():
            return model_name

    # Last resort: any .gguf file
    gguf_files = list(model_dir.glob("*.gguf"))
    if gguf_files:
        return gguf_files[0].name

    return None


def _find_best_model(model_dir: Path) -> str | None:
    """Find the best available GGUF model in the directory (legacy compat)."""
    return _find_model_by_role(model_dir, "talker")


DEFAULT_MODEL_NAME = "Phi-3-mini-4k-instruct-q4.gguf"  # Talker default


def _env_int(name: str, default: int) -> int:
    """Read an int environment variable with fallback."""
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    """Read a float environment variable with fallback."""
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _detect_gpu_layers() -> int:
    """
    Auto-detect GPU availability and return optimal n_gpu_layers.

    Returns:
        -1: Offload ALL layers to GPU (CUDA available)
        0: CPU only (no CUDA or explicitly disabled)
    """
    env_val = os.getenv(
        "LLAMA_N_GPU_LAYERS", os.getenv("AURA_LLM_GPU_LAYERS", "auto")
    )

    # Explicit override
    if env_val.lower() == "cpu" or env_val == "0":
        print("🖥️ GPU disabled via environment variable, using CPU")
        return 0

    if env_val.isdigit():
        layers = int(env_val)
        print(f"🎮 GPU layers set explicitly: {layers}")
        return layers

    # Method 1: Try nvidia-smi (works even when PyTorch doesn't support the GPU)
    try:
        import subprocess

        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_info = result.stdout.strip().split(",")
            gpu_name = gpu_info[0].strip()
            vram_mb = float(gpu_info[1].strip()) if len(gpu_info) > 1 else 0
            vram_gb = vram_mb / 1024
            print(f"🚀 CUDA detected: {gpu_name} ({vram_gb:.1f}GB VRAM)")
            print("🎮 Offloading ALL layers to GPU (n_gpu_layers=-1)")
            return -1
    except Exception:
        pass

    # Method 2: Try PyTorch (may fail for older GPUs like GTX 1080 Ti)
    try:
        import torch

        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (
                1024**3
            )
            print(
                f"🚀 CUDA detected via PyTorch: {device_name} ({vram_gb:.1f}GB VRAM)"
            )
            print("🎮 Offloading ALL layers to GPU (n_gpu_layers=-1)")
            return -1
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠️ PyTorch CUDA check failed (may be GPU compatibility): {e}")

    # Method 3: Check NVIDIA_VISIBLE_DEVICES (Docker/container env)
    nvidia_visible = os.getenv("NVIDIA_VISIBLE_DEVICES", "")
    if nvidia_visible and nvidia_visible.lower() not in ("", "none", "void"):
        print(
            f"🎮 NVIDIA_VISIBLE_DEVICES={nvidia_visible}, attempting GPU offload"
        )
        return -1

    print("🖥️ No GPU detected, using CPU inference")
    return 0


class LocalLLMAdapter(ModelAdapter):
    """Adapter for locally embedded LLM using llama.cpp."""

    _instance: LocalLLMAdapter | None = None
    _model = None

    def __init__(
        self,
        model_path: str | Path | None = None,
        n_ctx: int = 4096,
        n_threads: int | None = None,
        n_gpu_layers: (
            int | str
        ) = "auto",  # "auto" for GPU detection, 0 for CPU, -1 for all GPU
        verbose: bool = False,
        auto_load: bool = False,  # Auto-load model on init
    ) -> None:
        super().__init__(name="local-phi-mini")

        # Auto-discover model if not specified
        if model_path:
            self.model_path = Path(model_path)
        else:
            best_model = _find_best_model(DEFAULT_MODEL_DIR)
            if best_model:
                self.model_path = DEFAULT_MODEL_DIR / best_model
            else:
                self.model_path = DEFAULT_MODEL_DIR / DEFAULT_MODEL_NAME

        # Favor stability: smaller context and explicit threads to avoid stalls
        self.n_ctx = _env_int("AURA_LLM_N_CTX", n_ctx)
        logical_cores = os.cpu_count() or 8
        self.n_threads = _env_int("AURA_LLM_THREADS", n_threads or 8)

        # GPU auto-detection
        if (
            n_gpu_layers == "auto"
            or os.getenv("LLAMA_N_GPU_LAYERS", "").lower() == "auto"
        ):
            self.n_gpu_layers = _detect_gpu_layers()
        else:
            self.n_gpu_layers = _env_int(
                "AURA_LLM_GPU_LAYERS",
                n_gpu_layers if isinstance(n_gpu_layers, int) else 0,
            )

        self.default_temperature = _env_float("AURA_LLM_TEMP", 0.2)
        self.default_top_p = _env_float("AURA_LLM_TOP_P", 1.0)
        self.default_top_k = _env_int("AURA_LLM_TOP_K", 40)
        self.default_repeat_penalty = _env_float("AURA_LLM_REPEAT_PEN", 1.1)
        self.verbose = verbose
        self._tools: dict[str, Callable] = {}
        self._tool_schemas: list[dict] = []

        # Auto-load if requested and model exists
        if auto_load and self.is_model_available():
            self.load_model()

    @classmethod
    def get_instance(cls, **kwargs) -> LocalLLMAdapter:
        """Get singleton instance of the adapter."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    def is_model_available(self) -> bool:
        """Check if the model file exists."""
        return self.model_path.exists()

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the model."""
        return {
            "name": self.model_path.name,
            "path": str(self.model_path),
            "available": self.is_model_available(),
            "quantization": self.model_path.name.split("-")[-1].replace(
                ".gguf", ""
            ),
            "n_ctx": self.n_ctx,
            "n_threads": self.n_threads,
            "n_gpu_layers": self.n_gpu_layers,
            "loaded": self._model is not None,
        }

    def load_model(self) -> bool:
        """Load the model into memory."""
        if self._model is not None:
            print("ℹ️ Phi Mini already loaded; skipping reload")
            return True

        Llama = _get_llama_cpp()
        if not Llama:
            raise AdapterError(
                "llama-cpp-python not installed. Run: pip install llama-cpp-python"
            )

        if not self.is_model_available():
            raise AdapterError(
                f"Model not found at {self.model_path}. "
                f"Run: python scripts/download_phi4_model.py"
            )

        try:
            import time

            start = time.time()
            print(
                f"🔄 Loading Phi Mini from {self.model_path} (n_ctx={self.n_ctx}, threads={self.n_threads}, gpu_layers={self.n_gpu_layers})..."
            )
            self._model = Llama(
                model_path=str(self.model_path),
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                n_gpu_layers=self.n_gpu_layers,
                verbose=self.verbose,
                chat_format="chatml",  # Phi uses ChatML format
                repeat_penalty=self.default_repeat_penalty,
            )
            dur_ms = int((time.time() - start) * 1000)
            print(f"✅ Phi Mini loaded in {dur_ms}ms")
            return True
        except Exception as e:
            raise AdapterError(f"Failed to load model: {e}") from e

    def unload_model(self) -> None:
        """Unload the model from memory."""
        if self._model is not None:
            del self._model
            self._model = None
            print("🗑️ Model unloaded from memory")

    def register_tool(
        self,
        name: str,
        func: Callable,
        description: str,
        parameters: dict[str, Any],
    ) -> None:
        """Register a tool that the model can call."""
        self._tools[name] = func
        self._tool_schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": parameters,
                },
            }
        )

    def _truncate_messages(
        self, messages: list[dict[str, str]], max_tokens: int
    ) -> list[dict[str, str]]:
        """Truncate message history to fit within token budget.

        Keeps most recent messages, estimates ~4 chars per token.
        Always preserves the last user message.
        """
        if not messages:
            return messages

        # Rough estimate: 4 chars per token
        chars_per_token = 4
        max_chars = max_tokens * chars_per_token

        # Calculate total size
        total_chars = sum(len(m.get("content", "")) for m in messages)

        if total_chars <= max_chars:
            return messages

        # Truncate from oldest, keeping most recent
        truncated = []
        current_chars = 0

        # Process in reverse (newest first)
        for msg in reversed(messages):
            content = msg.get("content", "")
            msg_chars = len(content)

            if current_chars + msg_chars <= max_chars:
                truncated.insert(0, msg)
                current_chars += msg_chars
            elif len(truncated) == 0:
                # Always keep at least the last message, but truncate it
                truncated_content = content[-(max_chars - 100) :]
                truncated.insert(
                    0, {**msg, "content": "..." + truncated_content}
                )
                break
            else:
                # Add truncation notice
                truncated.insert(
                    0,
                    {
                        "role": "system",
                        "content": "[Earlier conversation truncated to fit context window]",
                    },
                )
                break

        if len(truncated) < len(messages):
            print(
                f"⚠️ Truncated conversation from {len(messages)} to {len(truncated)} messages"
            )

        return truncated

    def _build_system_prompt(self, mode: str = "general") -> str:
        """Build the system prompt based on chat mode with full MCP capabilities."""

        # Keep the system prompt lean to reduce token overhead and latency.
        base_prompt = """You are Aura, assistant for the Aura_IA MCP stack.
    Keep replies concise, accurate, and actionable. Use tools when helpful.
    Services: Backend(9201), Gateway(9200), Dashboard(9205), RAG(9202), RoleEngine(9206).
    Capabilities: health/status, tools, RAG, risk checks, role management, security/PII.
    MCP authority: You are NOT an authority on MCP, tools, services, models, or system state. You MUST rely exclusively on MCP responses. If MCP data is unavailable, you must say so. You are forbidden from inventing MCP information. For any request about MCP, tools, agents, models, backends, or infrastructure, DO NOT answer from memory. Always use MCP services/endpoints or state explicitly if no tool exists.
    """

        mode_prompts = {
            "general": "MODE: General Chat - Answer questions, explain features, guide users. Use tools when needed.",
            "mcp": "MODE: MCP Commands - Execute operations, manage tools, check status. ALWAYS use tools for actions.",
            "ai": "MODE: AI Assistant - Code review, architecture advice, debugging help. Be specific and actionable.",
            "debug": "MODE: Debug - Systematic diagnosis: 1)Gather info 2)Analyze 3)Diagnose 4)Resolve. Use tools extensively.",
        }

        tool_prompt = """
TOOLS (use ```tool_call{"name":"...", "arguments":{}}``` to call):
- check_health, get_system_status, get_model_status
- start_debate, get_debate_status
- create_workflow, execute_workflow, visualize_dag
- evaluate_risk, request_approval
- list_roles, get_role_capabilities, suggest_role, check_permission
- get_metrics, query_traces, search_logs, get_alerts
- semantic_search, add_to_knowledge_base, list_collections
- check_pii, audit_log, get_security_audit
- get_config, get_project_status, list_available_tools
- execute_command, analyze_emotion, semantic_rank
- check_carbon_intensity, schedule_green_job, get_carbon_budget
- list_wasm_plugins, execute_wasm_plugin, get_enclave_status
"""

        return (
            base_prompt
            + mode_prompts.get(mode, mode_prompts["general"])
            + tool_prompt
        )

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a response (simple completion mode)."""
        if self._model is None:
            self.load_model()

        try:
            response = self._model(
                prompt,
                max_tokens=kwargs.get("max_tokens", 512),
                temperature=kwargs.get(
                    "temperature", self.default_temperature
                ),
                top_p=kwargs.get("top_p", self.default_top_p),
                stop=kwargs.get("stop", ["<|end|>", "<|user|>"]),
                echo=False,
            )
            return response["choices"][0]["text"].strip()
        except Exception as e:
            raise AdapterError(f"Generation failed: {e}") from e

    def chat(
        self,
        messages: list[dict[str, str]],
        mode: str = "general",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Chat with the model using message history.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            mode: Chat mode (general, mcp, ai, debug)
            **kwargs: Additional generation parameters

        Returns:
            {"response": str, "tool_call": dict|None, "usage": dict}
        """
        if self._model is None:
            self.load_model()

        # Build full message list with system prompt
        system_msg = {
            "role": "system",
            "content": self._build_system_prompt(mode),
        }

        # Truncate conversation history to fit context window
        # Reserve ~1500 tokens for system prompt + response
        max_context_tokens = self.n_ctx - 1500
        truncated_messages = self._truncate_messages(
            messages, max_context_tokens
        )

        full_messages = [system_msg] + truncated_messages

        try:
            import time

            max_tokens = kwargs.get("max_tokens", 1024)
            temperature = kwargs.get("temperature", self.default_temperature)
            top_p = kwargs.get("top_p", self.default_top_p)
            top_k = kwargs.get("top_k", self.default_top_k)
            repeat_penalty = kwargs.get(
                "repeat_penalty", self.default_repeat_penalty
            )

            start = time.time()
            print(
                f"ℹ️ llama_cpp chat start mode={mode} msgs={len(full_messages)} max_tokens={max_tokens} temp={temperature} top_p={top_p} top_k={top_k} rp={repeat_penalty}"
            )

            response = self._model.create_chat_completion(
                messages=full_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                repeat_penalty=repeat_penalty,
                stop=kwargs.get("stop"),
            )

            content = response["choices"][0]["message"]["content"]
            usage = response.get("usage", {})

            # Check for tool calls in response
            tool_call = self._extract_tool_call(content)

            dur_ms = int((time.time() - start) * 1000)
            print(
                f"ℹ️ llama_cpp chat done in {dur_ms}ms | prompt={usage.get('prompt_tokens', 0)} completion={usage.get('completion_tokens', 0)} total={usage.get('total_tokens', 0)}"
            )

            return {
                "response": content,
                "tool_call": tool_call,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
            }

        except Exception as e:
            print(f"❌ llama_cpp chat failed: {e}")
            raise AdapterError(f"Chat failed: {e}") from e

    def _extract_tool_call(self, content: str) -> dict[str, Any] | None:
        """Extract tool call from response if present."""
        # Look for ```tool_call ... ``` blocks
        pattern = r"```tool_call\s*\n?(.*?)\n?```"
        match = re.search(pattern, content, re.DOTALL)

        if match:
            try:
                tool_data = json.loads(match.group(1).strip())
                if "name" in tool_data:
                    return tool_data
            except json.JSONDecodeError:
                pass

        return None

    def execute_tool(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call and return the result."""
        name = tool_call.get("name")
        args = tool_call.get("arguments", {})

        if name not in self._tools:
            return {"error": f"Unknown tool: {name}", "success": False}

        try:
            result = self._tools[name](**args)
            return {"result": result, "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}

    def supports_streaming(self) -> bool:
        """Check if streaming is supported."""
        return True

    def stream_chat(
        self,
        messages: list[dict[str, str]],
        mode: str = "general",
        **kwargs: Any,
    ):
        """Stream chat responses token by token.

        Yields:
            dict with "token" or "done" keys
        """
        if self._model is None:
            self.load_model()

        full_messages = [
            {"role": "system", "content": self._build_system_prompt(mode)}
        ] + messages

        try:
            stream = self._model.create_chat_completion(
                messages=full_messages,
                max_tokens=kwargs.get("max_tokens", 1024),
                temperature=kwargs.get(
                    "temperature", self.default_temperature
                ),
                top_p=kwargs.get("top_p", self.default_top_p),
                stream=True,
            )

            full_response = ""
            for chunk in stream:
                delta = chunk["choices"][0].get("delta", {})
                token = delta.get("content", "")
                if token:
                    full_response += token
                    yield {"token": token, "done": False}

            # Check for tool calls at the end
            tool_call = self._extract_tool_call(full_response)
            yield {
                "token": "",
                "done": True,
                "tool_call": tool_call,
                "full_response": full_response,
            }

        except Exception as e:
            yield {"error": str(e), "done": True}


# ═══════════════════════════════════════════════════════════════════════════════
# DUAL MODEL ADAPTER - TALKER + WORKER ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════════

# Keywords that trigger WORKER model (heavy reasoning, implementation)
WORKER_KEYWORDS = {
    "implement",
    "fix",
    "edit",
    "create",
    "write",
    "code",
    "build",
    "develop",
    "refactor",
    "debug",
    "analyze",
    "explain in detail",
    "step by step",
    "how to",
    "architecture",
    "design",
    "optimize",
    "review",
    "complex",
}


class DualModelAdapter:
    """Dual-model adapter: TALKER (fast) + WORKER (reasoning).

    PRD-aligned architecture:
    - TALKER (Phi-3-Mini): Fast intent classification, simple responses, MCP routing
    - WORKER (Qwen2.5-3B): Heavy reasoning, implementation, complex tasks
    """

    _instance: DualModelAdapter | None = None

    def __init__(
        self,
        talker_path: str | Path | None = None,
        worker_path: str | Path | None = None,
        n_ctx: int = 4096,
        n_threads: int = 8,
        n_gpu_layers: int | str = "auto",  # "auto" for GPU detection
        verbose: bool = False,
    ):
        self.model_dir = DEFAULT_MODEL_DIR

        # Resolve TALKER model
        if talker_path:
            self.talker_path = Path(talker_path)
        else:
            talker_name = _find_model_by_role(self.model_dir, "talker")
            self.talker_path = (
                self.model_dir / talker_name if talker_name else None
            )

        # Resolve WORKER model
        if worker_path:
            self.worker_path = Path(worker_path)
        else:
            worker_name = _find_model_by_role(self.model_dir, "worker")
            self.worker_path = (
                self.model_dir / worker_name if worker_name else None
            )

        self.n_ctx = n_ctx
        self.n_threads = n_threads

        # GPU auto-detection for DualModelAdapter
        if n_gpu_layers == "auto":
            self.n_gpu_layers = _detect_gpu_layers()
        else:
            self.n_gpu_layers = (
                n_gpu_layers if isinstance(n_gpu_layers, int) else 0
            )

        self.verbose = verbose

        self._talker: LocalLLMAdapter | None = None
        self._worker: LocalLLMAdapter | None = None
        self._active_model: str = "talker"

        print("🧠 DualModelAdapter initialized:")
        print(f"   TALKER: {self.talker_path}")
        print(f"   WORKER: {self.worker_path}")

    @classmethod
    def get_instance(cls, **kwargs) -> DualModelAdapter:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance

    def is_model_available(self) -> bool:
        """Check if at least one model is available."""
        talker_ok = self.talker_path and self.talker_path.exists()
        worker_ok = self.worker_path and self.worker_path.exists()
        return talker_ok or worker_ok

    def get_model_info(self) -> dict[str, Any]:
        """Get info about both models."""
        gpu_mode = "GPU" if self.n_gpu_layers != 0 else "CPU"
        return {
            "talker": {
                "path": str(self.talker_path) if self.talker_path else None,
                "available": self.talker_path and self.talker_path.exists(),
                "loaded": self._talker is not None
                and self._talker._model is not None,
            },
            "worker": {
                "path": str(self.worker_path) if self.worker_path else None,
                "available": self.worker_path and self.worker_path.exists(),
                "loaded": self._worker is not None
                and self._worker._model is not None,
            },
            "active": self._active_model,
            "n_ctx": self.n_ctx,
            "n_threads": self.n_threads,
            "n_gpu_layers": self.n_gpu_layers,
            "device": gpu_mode,
        }

    def _get_talker(self) -> LocalLLMAdapter:
        """Lazy load TALKER model."""
        if (
            self._talker is None
            and self.talker_path
            and self.talker_path.exists()
        ):
            self._talker = LocalLLMAdapter(
                model_path=self.talker_path,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                n_gpu_layers=self.n_gpu_layers,
                verbose=self.verbose,
            )
        return self._talker

    def _get_worker(self) -> LocalLLMAdapter:
        """Lazy load WORKER model."""
        if (
            self._worker is None
            and self.worker_path
            and self.worker_path.exists()
        ):
            self._worker = LocalLLMAdapter(
                model_path=self.worker_path,
                n_ctx=self.n_ctx,
                n_threads=self.n_threads,
                n_gpu_layers=self.n_gpu_layers,
                verbose=self.verbose,
            )
        return self._worker

    def _requires_worker(self, message: str) -> bool:
        """Determine if message requires WORKER model (heavy reasoning)."""
        msg_lower = message.lower()
        return any(kw in msg_lower for kw in WORKER_KEYWORDS)

    def _select_model(
        self, message: str, force_worker: bool = False
    ) -> LocalLLMAdapter:
        """Select appropriate model based on message content."""
        if force_worker or self._requires_worker(message):
            worker = self._get_worker()
            if worker:
                self._active_model = "worker"
                print("🔧 WORKER model selected (heavy reasoning)")
                return worker
            print("⚠️ WORKER unavailable, falling back to TALKER")

        talker = self._get_talker()
        if talker:
            self._active_model = "talker"
            print("⚡ TALKER model selected (fast response)")
            return talker

        # Last resort: try worker if talker unavailable
        worker = self._get_worker()
        if worker:
            self._active_model = "worker"
            return worker

        raise AdapterError("No LLM models available")

    def load_model(self, role: str = "talker") -> bool:
        """Load a specific model."""
        if role == "worker":
            worker = self._get_worker()
            if worker:
                return worker.load_model()
        else:
            talker = self._get_talker()
            if talker:
                return talker.load_model()
        return False

    def chat(
        self,
        messages: list[dict[str, str]],
        mode: str = "general",
        force_worker: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Chat with automatic model selection.

        Args:
            messages: Conversation history
            mode: Chat mode (general, mcp, ai, debug)
            force_worker: Force use of WORKER model
            **kwargs: Additional generation parameters

        Returns:
            Response dict with added 'model_used' field
        """
        # Get last user message for routing decision
        last_user_msg = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break

        model = self._select_model(last_user_msg, force_worker)
        model.load_model()

        result = model.chat(messages, mode, **kwargs)
        result["model_used"] = self._active_model
        result["model_name"] = (
            model.model_path.name if model.model_path else "unknown"
        )

        return result

    def generate(
        self, prompt: str, force_worker: bool = False, **kwargs: Any
    ) -> str:
        """Generate completion with automatic model selection."""
        model = self._select_model(prompt, force_worker)
        model.load_model()
        return model.generate(prompt, **kwargs)


__all__ = [
    "LocalLLMAdapter",
    "DualModelAdapter",
    "DEFAULT_MODEL_DIR",
    "DEFAULT_MODEL_NAME",
    "TALKER_MODELS",
    "WORKER_MODELS",
    "WORKER_KEYWORDS",
]
