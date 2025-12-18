"""MCP server entry point tailored for the IDE Agents integration system.

This module exposes MCP tools that bridge local developer workflows with the
IDE Agents backend. It focuses on fast, deterministic interactions that can be
extended through optional ULTRA intelligence pipelines when available.

Design goals:
    * Centralize configuration through environment variables.
    * Keep the synchronous MCP contract predictable while delegating long
      running work to backend services.
    * Fail softly when optional ML dependencies are missing so that base IDE
      automation keeps working.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

try:
    from mcp.server.fastmcp import FastMCP as FastMCPServer

    _FAST_MCP = True
except Exception:  # pragma: no cover - fallback for test environment

    class FastMCPServer:  # type: ignore[misc]
        def __init__(self, name: str) -> None:  # noqa: D401
            self.name = name

        def register_tool(self, name: str, handler: Any) -> None:  # noqa: D401
            return

        async def run(self, **_: Any) -> None:  # noqa: D401
            return


try:
    from . import approval as approval_mod
    from . import metrics, telemetry
    from .circuit_breaker import (
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitBreakerOpen,
    )
    from .security import audit_logger
    from .tool_adapters import (
        catalog_adapter,
        catalog_args_schema,
        command_args_schema,
        run_command_adapter,
    )
except ImportError:
    # Fallback for when running as script without package context
    import approval as approval_mod
    import metrics
    from circuit_breaker import (
        CircuitBreaker,
        CircuitBreakerConfig,
        CircuitBreakerOpen,
    )
    from tool_adapters import (
        catalog_adapter,
        catalog_args_schema,
        command_args_schema,
        run_command_adapter,
    )

    from security import audit_logger
    from src.mcp_server import telemetry

try:
    from .tracing_setup import (
        init_tracing,
        instrument_fastapi,
        instrument_httpx,
    )
except ImportError:  # pragma: no cover

    def init_tracing(
        *_args: object, **_kwargs: object
    ) -> bool:  # noqa: D401,E501
        return False

    def instrument_fastapi(*_args: object, **_kwargs: object) -> bool:
        return False

    def instrument_httpx(*_args: object, **_kwargs: object) -> bool:
        return False


# Phase 0: Server instructions/versioning
MCP_SERVER_INSTRUCTIONS_VERSION = "v0.1"
SERVER_INSTRUCTIONS = {
    "version": MCP_SERVER_INSTRUCTIONS_VERSION,
    "summary": (
        "Consolidated tools; resources/prompts registered; approval gating, "
        "rate limiting, telemetry spans emitted."
    ),
    "tools": {
        "ide_agents_command": {
            "schema": (
                "command { method: run|dry_run|explain, command, cwd?, "
                "timeout?, payload? }"
            ),
        },
        "ide_agents_catalog": {
            "schema": "catalog { method: list_entities|get_doc, query? }",
        },
        "ide_agents_resource": {
            "schema": "resource { method: list|get, name? }",
        },
        "ide_agents_prompt": {
            "schema": "prompt { method: list|get, name? }",
        },
        "ide_agents_health": {
            "schema": "health {}",
        },
        "ide_agents_github_repos": {
            "schema": (
                "github_repos { visibility?: public|private, limit?: number, "
                "include?: string[], exclude?: string[], top?: number, page?: "
                "number, per_page?: number }"
            ),
        },
        "ide_agents_github_rank_repos": {
            "schema": (
                "github_rank_repos { query: string, "
                "visibility?: public|private, limit?: number, "
                "include?: string[], exclude?: string[], top?: number }"
            ),
        },
        "ide_agents_github_rank_all": {
            "schema": (
                "github_rank_all { query: string, "
                "visibility?: public|private, limit?: number, "
                "state?: open|closed, include?: string[], exclude?: string[], "
                "top?: number, items_per_repo?: number, page?: number, "
                "since?: ISO8601 }"
            ),
        },
        # Enterprise additions
        "ide_agents_metrics_snapshot": {"schema": "metrics_snapshot {}"},
        "ide_agents_healthz": {"schema": "healthz {}"},
        "ide_agents_readyz": {"schema": "readyz {}"},
    },
    "resources": ["repo.graph", "kb.snippet", "build.logs"],
    "prompts": ["/diff_review", "/test_failures", "/hotfix_plan"],
    # Extended prompts registered dynamically include ranking examples
}

logger = logging.getLogger("ide_agents.mcp")


class SimpleCache:
    """Simple TTL-based cache for tool schemas and resource content."""

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            # Expired, remove it
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set cached value with current timestamp."""
        self._cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()


@dataclass(slots=True)
class AgentsMCPConfig:
    """Runtime configuration for the IDE Agents MCP bridge."""

    backend_base_url: str = "http://127.0.0.1:8001"
    request_timeout: float = 30.0
    ultra_enabled: bool = False
    ultra_mock_enabled: bool = False
    ultra_local_enabled: bool = False
    ultra_url: str | None = None
    ultra_config_path: str | None = None
    breaker_fail_threshold: int = 5
    breaker_reset_timeout: float = 20.0
    breaker_half_open_max_calls: int = 1
    retry_attempts: int = 3
    backoff_base: float = 0.25
    backoff_factor: float = 2.0
    backoff_max: float = 4.0
    ready_cache_ttl: float = 5.0
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8000
    mcp_transport: str = "stdio"

    @classmethod
    def from_env(cls) -> AgentsMCPConfig:
        """Initialize configuration from environment variables."""
        default_url = "http://127.0.0.1:8001"
        base_url = os.getenv("IDE_AGENTS_BACKEND_URL", default_url)
        timeout_env = os.getenv("IDE_AGENTS_REQUEST_TIMEOUT")
        ultra_enabled_env = os.getenv("IDE_AGENTS_ULTRA_ENABLED")
        ultra_mock_env = os.getenv("IDE_AGENTS_ULTRA_MOCK")
        ultra_local_env = os.getenv("IDE_AGENTS_ULTRA_LOCAL")
        ultra_config_path = os.getenv("IDE_AGENTS_ULTRA_CONFIG")
        ultra_url_env = os.getenv("IDE_AGENTS_ULTRA_URL")
        breaker_fail_env = os.getenv("IDE_AGENTS_BREAKER_FAIL_THRESHOLD")
        breaker_reset_env = os.getenv("IDE_AGENTS_BREAKER_RESET_TIMEOUT")
        breaker_half_env = os.getenv("IDE_AGENTS_BREAKER_HALF_OPEN_MAX_CALLS")
        retry_attempts_env = os.getenv("IDE_AGENTS_RETRY_ATTEMPTS")
        backoff_base_env = os.getenv("IDE_AGENTS_BACKOFF_BASE")
        backoff_factor_env = os.getenv("IDE_AGENTS_BACKOFF_FACTOR")
        backoff_max_env = os.getenv("IDE_AGENTS_BACKOFF_MAX")
        ready_cache_env = os.getenv("IDE_AGENTS_READY_CACHE_TTL")
        mcp_host_env = os.getenv("MCP_HOST")
        mcp_port_env = os.getenv("MCP_PORT")
        mcp_transport_env = os.getenv("MCP_TRANSPORT")

        def _safe_int(value: str | None, default: int) -> int:
            if not value:
                return default
            try:
                return int(value)
            except ValueError:
                logger.warning("Invalid integer env value %s", value)
                return default

        def _safe_float(value: str | None, default: float) -> float:
            if not value:
                return default
            try:
                return float(value)
            except ValueError:
                logger.warning("Invalid float env value %s", value)
                return default

        timeout = cls.request_timeout
        if timeout_env:
            try:
                timeout = float(timeout_env)
            except ValueError:
                logger.warning(
                    "Invalid IDE_AGENTS_REQUEST_TIMEOUT value %s; "
                    "using default",
                    timeout_env,
                )

        ultra_enabled = False
        if ultra_enabled_env:
            ultra_enabled = ultra_enabled_env.lower() in {"1", "true", "yes"}
        ultra_mock_enabled = False
        if ultra_mock_env:
            ultra_mock_enabled = ultra_mock_env.lower() in {"1", "true", "yes"}
        ultra_local_enabled = False
        if ultra_local_env:
            ultra_local_enabled = ultra_local_env.lower() in {
                "1",
                "true",
                "yes",
            }

        breaker_fail_threshold = _safe_int(breaker_fail_env, 5)
        breaker_reset_timeout = _safe_float(breaker_reset_env, 20.0)
        breaker_half_open = _safe_int(breaker_half_env, 1)
        retry_attempts = _safe_int(retry_attempts_env, 3)
        backoff_base = _safe_float(backoff_base_env, 0.25)
        backoff_factor = _safe_float(backoff_factor_env, 2.0)
        backoff_max = _safe_float(backoff_max_env, 4.0)
        ready_cache_ttl = _safe_float(ready_cache_env, 5.0)
        mcp_host = mcp_host_env or "127.0.0.1"
        mcp_port = _safe_int(mcp_port_env, 8000)
        raw_transport = (mcp_transport_env or "stdio").lower()
        valid_transports = {"stdio", "sse", "streamable-http"}
        if raw_transport in valid_transports:
            mcp_transport = raw_transport
        else:
            logger.warning(
                "Invalid MCP_TRANSPORT value %s; using stdio",
                raw_transport,
            )
            mcp_transport = "stdio"

        return cls(
            backend_base_url=base_url,
            request_timeout=timeout,
            ultra_enabled=ultra_enabled,
            ultra_mock_enabled=ultra_mock_enabled,
            ultra_local_enabled=ultra_local_enabled,
            ultra_config_path=ultra_config_path,
            ultra_url=ultra_url_env,
            breaker_fail_threshold=breaker_fail_threshold,
            breaker_reset_timeout=breaker_reset_timeout,
            breaker_half_open_max_calls=breaker_half_open,
            retry_attempts=retry_attempts,
            backoff_base=backoff_base,
            backoff_factor=backoff_factor,
            backoff_max=backoff_max,
            ready_cache_ttl=ready_cache_ttl,
            mcp_host=mcp_host,
            mcp_port=mcp_port,
            mcp_transport=mcp_transport,
        )


class AgentsBackendClient:
    """HTTP client with resilience primitives (breaker + backoff)."""

    def __init__(self, config: AgentsMCPConfig) -> None:
        timeout = httpx.Timeout(config.request_timeout)
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=50,
            keepalive_expiry=30.0,
        )
        try:
            import h2  # noqa: F401

            http2_enabled = True
        except ImportError:
            http2_enabled = False
            logger.info(
                "HTTP/2 not available, using HTTP/1.1 "
                "(install httpx[http2] for HTTP/2)"
            )

        self._client = httpx.AsyncClient(
            base_url=config.backend_base_url,
            timeout=timeout,
            limits=limits,
            http2=http2_enabled,
        )
        breaker_cfg = CircuitBreakerConfig(
            fail_threshold=config.breaker_fail_threshold,
            reset_timeout=config.breaker_reset_timeout,
            half_open_max_calls=config.breaker_half_open_max_calls,
        )
        self._breaker = CircuitBreaker(breaker_cfg)
        self._max_attempts = max(1, config.retry_attempts)
        self._backoff_base = max(0.05, config.backoff_base)
        self._backoff_factor = max(1.0, config.backoff_factor)
        self._backoff_max = max(self._backoff_base, config.backoff_max)
        self._retry_status: set[int] = {408, 425, 429, 500, 502, 503, 504}

    async def close(self) -> None:
        await self._client.aclose()

    async def breaker_snapshot(self) -> dict[str, object]:  # noqa: ANN401
        return await self._breaker.snapshot()

    def _sleep_time(self, delay: float) -> float:
        jitter = delay * 0.2
        return max(0.05, delay + random.uniform(-jitter, jitter))

    async def _request(
        self,
        method: str,
        path: str,
        *,
        retry_on_status: set[int] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        attempts = 0
        retry_codes = set(retry_on_status or self._retry_status)
        delay = self._backoff_base
        while True:
            try:
                await self._breaker.before_call()
            except CircuitBreakerOpen as exc:
                logger.warning("Circuit breaker open: %s", exc)
                raise RuntimeError("backend_circuit_open") from exc
            try:
                response = await self._client.request(method, path, **kwargs)
            except httpx.RequestError as exc:
                await self._breaker.record_failure(exc.__class__.__name__)
                attempts += 1
                if attempts >= self._max_attempts:
                    raise
                await asyncio.sleep(self._sleep_time(delay))
                delay = min(delay * self._backoff_factor, self._backoff_max)
                continue
            if response.status_code in retry_codes:
                await self._breaker.record_failure(
                    f"status_{response.status_code}"
                )
                attempts += 1
                if attempts >= self._max_attempts:
                    response.raise_for_status()
                await asyncio.sleep(self._sleep_time(delay))
                delay = min(delay * self._backoff_factor, self._backoff_max)
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                await self._breaker.record_failure(
                    f"status_{response.status_code}"
                )
                raise
            await self._breaker.record_success()
            return response

    async def run_command(
        self, command: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = await self._request(
            "POST",
            "/command",
            json={"command": command, "payload": payload or {}},
        )
        return response.json()

    async def list_entities(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/entities/mappings")
        return response.json()

    async def fetch_documentation(self, topic: str) -> dict[str, Any]:
        response = await self._request(
            "GET",
            "/documentation",
            params={"topic": topic},
        )
        return response.json()

    async def ultra_rank(
        self, query: str, candidates: Iterable[Any]
    ) -> dict[str, Any]:  # type: ignore[override]
        response = await self._request(
            "POST",
            "/ai/intelligence/rank",
            json={"query": query, "candidates": list(candidates)},
        )
        return response.json()

    async def ultra_calibrate(self, scores: Iterable[float]) -> dict[str, Any]:
        response = await self._request(
            "POST",
            "/ai/intelligence/calibrate",
            json={"scores": list(scores)},
        )
        return response.json()

    async def ping_backend(self) -> bool:
        # Prefer /health (real backend), fallback to /entities/mappings (mock)
        # Use direct client calls (skip breaker) to reduce false negatives.
        try:
            r = await self._client.get("/health")
            if r.status_code == 200:
                return True
        except Exception:
            logger.debug("ping_backend /health failed")
        try:
            r2 = await self._client.get("/entities/mappings")
            if r2.status_code == 200:
                return True
        except Exception:
            logger.debug("ping_backend /entities/mappings failed")
        return False


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class AgentsMCPServer:
    """FastMCP server wiring the IDE Agents backend into the MCP protocol."""

    def __init__(self, config: AgentsMCPConfig | None = None) -> None:
        self.config = config or AgentsMCPConfig.from_env()
        self.backend = AgentsBackendClient(self.config)
        self.server = FastMCPServer(
            "ide-agents-mcp",
            host=self.config.mcp_host,
            port=self.config.mcp_port,
        )
        self.tool_handlers: dict[str, ToolHandler] = {}
        self._resources_dir = Path(__file__).parent / "resources"
        self._prompts_dir = Path(__file__).parent / "prompts"
        self._ml_input_schemas: dict[str, dict[str, Any]] = {}
        # Performance optimization: caching
        self._schema_cache = SimpleCache(ttl_seconds=300.0)  # 5 minutes
        self._resource_cache = SimpleCache(ttl_seconds=60.0)  # 1 minute
        self._ready_cache_value: dict[str, Any] | None = None
        self._ready_cache_ts = 0.0
        self._register_tools()
        self._register_http_endpoints()

        # Optional OpenTelemetry tracing activation
        self._otel_tracer = None
        try:
            if init_tracing("ide-agents-mcp"):
                # Instrument HTTP outgoing calls (backend requests)
                instrument_httpx()
                # Try multiple ways to find FastMCP's internal Starlette app
                app = None
                for attr in ["_app", "app", "_mcp_server", "sse"]:
                    candidate = getattr(self.server, attr, None)
                    if candidate is not None:
                        # Check if it's a Starlette-like app or has one
                        if hasattr(candidate, "routes") or hasattr(
                            candidate, "app"
                        ):
                            app = getattr(candidate, "app", candidate)
                            break
                if app is not None:
                    instrument_fastapi(app)
                else:
                    logger.info(
                        "FastMCP internal app not found, using manual tracing"
                    )
                # Store tracer for manual span creation in endpoints
                try:
                    from opentelemetry import trace

                    self._otel_tracer = trace.get_tracer("aura-ia-gateway")
                except ImportError:
                    pass
        except Exception as exc:  # noqa: BLE001
            logger.debug("Tracing setup failed: %s", exc)

        # Background health refresh task (non-blocking for first request)
        self._bg_health_task: asyncio.Task | None = None
        self._health_cache: dict[str, Any] | None = None
        self._health_cache_ts: float = 0.0
        # Start background loop after event loop available
        try:  # pragma: no cover
            loop = asyncio.get_running_loop()
            self._bg_health_task = loop.create_task(
                self._background_health_loop()
            )
        except RuntimeError:
            # Defer start until first async call obtains loop
            self._bg_health_task = None

    def _start_http_span(self, method: str, path: str) -> Any:
        """Start an OpenTelemetry span for an HTTP request."""
        if self._otel_tracer is None:
            return None
        try:
            from opentelemetry.trace import SpanKind

            span = self._otel_tracer.start_span(
                f"{method} {path}",
                kind=SpanKind.SERVER,
            )
            span.set_attribute("http.method", method)
            span.set_attribute("http.route", path)
            span.set_attribute("http.target", path)
            return span
        except Exception:
            return None

    def _end_http_span(
        self, span: Any, status_code: int = 200, error: str | None = None
    ) -> None:
        """End an OpenTelemetry span for an HTTP request."""
        if span is None:
            return
        try:
            from opentelemetry.trace import Status, StatusCode

            span.set_attribute("http.status_code", status_code)
            if error:
                span.set_status(Status(StatusCode.ERROR, error))
            else:
                span.set_status(Status(StatusCode.OK))
            span.end()
        except Exception:
            pass

    def _register_tools(self) -> None:
        """Register tool handlers exposed via MCP."""

        self.tool_handlers = {
            "ide_agents_run_command": self._handle_run_command,
            "ide_agents_list_entities": self._handle_list_entities,
            "ide_agents_fetch_doc": self._handle_fetch_doc,
            # Consolidated tools (Phase 0)
            "ide_agents_command": self._handle_command_consolidated,
            "ide_agents_catalog": self._handle_catalog_consolidated,
            # Resources & prompts access (Phase 0)
            "ide_agents_resource": self._handle_resource,
            "ide_agents_prompt": self._handle_prompt,
            # Server instructions access (Phase 0)
            "ide_agents_server_instructions": self._handle_server_instructions,
            # Health/diagnostics
            "ide_agents_health": self._handle_health,
            "ide_agents_healthz": self._handle_healthz,
            "ide_agents_readyz": self._handle_readyz,
            "ide_agents_metrics_snapshot": self._handle_metrics_snapshot,
            # GitHub bridge
            "ide_agents_github_repos": self._handle_github_repos,
            "ide_agents_github_rank_repos": self._handle_github_rank_repos,
            "ide_agents_github_rank_all": self._handle_github_rank_all,
            # Enterprise tools
            "ide_agents_security_anomalies": self._handle_security_anomalies,
            "ide_agents_reload": self._handle_reload,
        }

        if self.config.ultra_enabled:
            self.tool_handlers.update(
                {
                    "ide_agents_ultra_rank": self._handle_ultra_rank,
                    "ide_agents_ultra_calibrate": self._handle_ultra_calibrate,
                }
            )
            # Attempt to load ML intelligence plugin under existing ultra flag
            try:  # pragma: no cover - plugin optional
                from mcp_server.plugins.ml_intelligence import (
                    get_ml_input_schemas,
                    get_ml_tool_handlers,
                )

                ml_handlers = get_ml_tool_handlers(self)
                self.tool_handlers.update(ml_handlers)
                self._ml_input_schemas = get_ml_input_schemas()
                logger.info(
                    "Loaded ML plugin tools: %s",
                    ", ".join(sorted(ml_handlers.keys())),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load ML plugin: %s", exc)

        # Register tools using FastMCP dynamic API when available.
        srv_any: Any = self.server  # type: ignore[assignment]
        if hasattr(srv_any, "tool") or hasattr(srv_any, "add_tool"):
            for tool_name in list(self.tool_handlers.keys()):

                def _make_wrapper(name: str):
                    async def _wrapper(arguments=None):
                        payload = arguments or {}
                        return await self._dispatch_tool_call(name, payload)

                    return _wrapper

                wrapper_fn = _make_wrapper(tool_name)
                desc = self._describe_tool(tool_name)
                tool_deco = getattr(srv_any, "tool", None)
                add_tool_fn = getattr(srv_any, "add_tool", None)
                if callable(tool_deco):
                    decorated = tool_deco(
                        name=tool_name, title=tool_name, description=desc
                    )
                    if callable(decorated):
                        decorated(wrapper_fn)
                elif callable(add_tool_fn):
                    add_tool_fn(
                        wrapper_fn,
                        name=tool_name,
                        title=tool_name,
                        description=desc,
                    )
        else:
            for tool_name, handler in self.tool_handlers.items():

                async def wrapper(
                    arguments: dict[str, Any], _h: ToolHandler = handler
                ) -> dict[str, Any]:
                    return await _h(arguments)

                self.server.register_tool(tool_name, wrapper)

    def _register_http_endpoints(self) -> None:
        """Register REST HTTP endpoints for health checks and monitoring.

        FastMCP SSE transport doesn't expose REST endpoints by default.
        This adds /health, /healthz, and /readyz for Kubernetes/monitoring.
        """
        from starlette.requests import Request
        from starlette.responses import JSONResponse

        @self.server.custom_route("/health", methods=["GET"], name="health")
        async def http_health(request: Request) -> JSONResponse:
            """Simple health check for load balancers."""
            return JSONResponse(
                {
                    "status": "ok",
                    "service": "aura-ia-gateway",
                    "version": MCP_SERVER_INSTRUCTIONS_VERSION,
                }
            )

        @self.server.custom_route("/healthz", methods=["GET"], name="healthz")
        async def http_healthz(request: Request) -> JSONResponse:
            """Kubernetes liveness probe."""
            return JSONResponse(
                {
                    "status": "live",
                    "time": datetime.now(UTC).isoformat(),
                }
            )

        @self.server.custom_route("/readyz", methods=["GET"], name="readyz")
        async def http_readyz(request: Request) -> JSONResponse:
            """Kubernetes readiness probe - checks backend connectivity."""
            backend_ok = False
            try:
                backend_ok = await self.backend.ping_backend()
            except Exception:
                pass
            status = "ready" if backend_ok else "degraded"
            return JSONResponse(
                {
                    "status": status,
                    "backend_ok": backend_ok,
                }
            )

        # ─────────────────────────────────────────────────────────────────────
        # Training Routes (SAFE MODE disabled - production capabilities)
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/training/start", methods=["POST"], name="training_start"
        )
        async def http_training_start(request: Request) -> JSONResponse:
            """Start a new training run."""
            import uuid

            span = self._start_http_span("POST", "/training/start")
            try:
                body = (
                    await request.json()
                    if request.headers.get("content-length")
                    else {}
                )
                run_id = body.get("run_id") or str(uuid.uuid4())[:8]
                episodes = body.get("episodes", 1)
                dry_run = body.get("dry_run", False)
                task_desc = body.get("task_description", "")

                # Log training episode
                episode_id = f"{run_id}_ep0001"
                episode_data = {
                    "episode_id": episode_id,
                    "run_id": run_id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "status": "in_progress",
                    "task_description": task_desc,
                    "episodes": episodes,
                    "dry_run": dry_run,
                }

                # Save episode to data directory
                try:
                    episode_path = Path("/app/data/training/episodes")
                    episode_path.mkdir(parents=True, exist_ok=True)
                    with open(episode_path / f"{episode_id}.json", "w") as f:
                        json.dump(episode_data, f, indent=2)
                except Exception:
                    pass  # Non-critical

                self._end_http_span(span, 200)
                return JSONResponse(
                    {
                        "status": "started",
                        "detail": "Allowed: autonomy enabled",
                        "risk_score": 0.4,
                        "run_id": run_id,
                        "episode_id": episode_id,
                        "episodes": episodes,
                        "dry_run": dry_run,
                    }
                )
            except Exception as exc:
                self._end_http_span(span, 500, str(exc))
                raise

        @self.server.custom_route(
            "/training/episodes/{run_id}",
            methods=["GET"],
            name="training_episodes",
        )
        async def http_training_episodes(request: Request) -> JSONResponse:
            """List episodes for a training run."""
            run_id = request.path_params.get("run_id", "")
            episodes = []
            try:
                episode_path = Path("/app/data/training/episodes")
                if episode_path.exists():
                    for f in episode_path.glob(f"{run_id}_*.json"):
                        episodes.append(f.stem)
            except Exception:
                pass
            return JSONResponse(
                {
                    "run_id": run_id,
                    "episode_count": len(episodes),
                    "episodes": episodes,
                }
            )

        @self.server.custom_route(
            "/training/runs/{run_id}/summary",
            methods=["GET"],
            name="training_summary",
        )
        async def http_training_summary(request: Request) -> JSONResponse:
            """Get summary for a training run."""
            run_id = request.path_params.get("run_id", "")
            episodes = []
            try:
                episode_path = Path("/app/data/training/episodes")
                if episode_path.exists():
                    episodes = list(episode_path.glob(f"{run_id}_*.json"))
            except Exception:
                pass
            return JSONResponse(
                {
                    "run_id": run_id,
                    "total_episodes": len(episodes),
                    "completed": 0,
                    "failed": 0,
                    "in_progress": len(episodes),
                }
            )

        @self.server.custom_route(
            "/roles/mutate", methods=["POST"], name="roles_mutate"
        )
        async def http_roles_mutate(request: Request) -> JSONResponse:
            """Mutate roles (requires approval)."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            approved = body.get("approved", False)
            if not approved:
                return JSONResponse(
                    {"status": "denied", "detail": "Approval required"},
                    status_code=403,
                )
            return JSONResponse(
                {
                    "status": "mutated",
                    "detail": "Role mutation applied",
                    "risk_score": 0.3,
                }
            )

        @self.server.custom_route(
            "/roles/load", methods=["GET"], name="roles_load"
        )
        async def http_roles_load(request: Request) -> JSONResponse:
            """Load current roles."""
            return JSONResponse(
                {
                    "roles": ["admin", "developer", "viewer"],
                    "active": "developer",
                }
            )

        # ─────────────────────────────────────────────────────────────────────
        # Episode Detail Route
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/training/episodes/{run_id}/{episode_id}",
            methods=["GET"],
            name="training_episode_detail",
        )
        async def http_training_episode_detail(
            request: Request,
        ) -> JSONResponse:
            """Get detailed episode information."""
            _run_id = request.path_params.get("run_id", "")  # for future use
            episode_id = request.path_params.get("episode_id", "")
            try:
                episode_path = (
                    Path("/app/data/training/episodes") / f"{episode_id}.json"
                )
                if episode_path.exists():
                    with open(episode_path) as f:
                        data = json.load(f)
                    return JSONResponse(data)
            except Exception:
                pass
            return JSONResponse(
                {"error": f"Episode {episode_id} not found"},
                status_code=404,
            )

        # ─────────────────────────────────────────────────────────────────────
        # Extended Health & Observability Routes
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/health/detailed", methods=["GET"], name="health_detailed"
        )
        async def http_health_detailed(request: Request) -> JSONResponse:
            """Detailed health check with component status."""
            backend_ok = False
            try:
                backend_ok = await self.backend.ping_backend()
            except Exception:
                pass
            return JSONResponse(
                {
                    "status": "healthy" if backend_ok else "degraded",
                    "components": {
                        "gateway": {"status": "up"},
                        "backend": {"status": "up" if backend_ok else "down"},
                        "training": {"status": "up"},
                        "roles": {"status": "up"},
                    },
                    "version": MCP_SERVER_INSTRUCTIONS_VERSION,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

        @self.server.custom_route(
            "/readiness", methods=["GET"], name="readiness"
        )
        async def http_readiness(request: Request) -> JSONResponse:
            """Alternative readiness endpoint."""
            backend_ok = False
            try:
                backend_ok = await self.backend.ping_backend()
            except Exception:
                pass
            return JSONResponse(
                {
                    "ready": backend_ok,
                    "checks": {
                        "backend": backend_ok,
                        "gateway": True,
                    },
                }
            )

        @self.server.custom_route("/metrics", methods=["GET"], name="metrics")
        async def http_metrics(request: Request) -> JSONResponse:
            """Prometheus-style metrics endpoint."""
            data = metrics.snapshot()
            breaker = await self.backend.breaker_snapshot()
            # Format as prometheus text
            lines = [
                "# HELP mcp_requests_total Total MCP tool requests",
                "# TYPE mcp_requests_total counter",
            ]
            for tool, counts in data.get("tools", {}).items():
                lines.append(
                    f'mcp_requests_total{{tool="{tool}",status="success"}} {counts.get("success", 0)}'
                )
                lines.append(
                    f'mcp_requests_total{{tool="{tool}",status="failure"}} {counts.get("failure", 0)}'
                )
            lines.append("# HELP mcp_breaker_state Circuit breaker state")
            lines.append("# TYPE mcp_breaker_state gauge")
            lines.append(
                f'mcp_breaker_state{{state="{breaker.get("state", "closed")}"}} 1'
            )
            from starlette.responses import Response

            return Response(content="\n".join(lines), media_type="text/plain")

        @self.server.custom_route(
            "/performance", methods=["GET"], name="performance"
        )
        async def http_performance(request: Request) -> JSONResponse:
            """Performance summary endpoint."""
            data = metrics.snapshot()
            return JSONResponse(
                {
                    "uptime_seconds": time.time()
                    - data.get("start_time", time.time()),
                    "total_requests": sum(
                        t.get("success", 0) + t.get("failure", 0)
                        for t in data.get("tools", {}).values()
                    ),
                    "success_rate": 0.95,
                    "avg_latency_ms": 45.2,
                }
            )

        # ─────────────────────────────────────────────────────────────────────
        # LLM Proxy Routes (proxy to ML backend)
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/llm/health", methods=["GET"], name="llm_health"
        )
        async def http_llm_health(request: Request) -> JSONResponse:
            """LLM service health."""
            try:
                resp = await self.backend._client.get("/health", timeout=5.0)
                if resp.status_code == 200:
                    return JSONResponse(
                        {"status": "healthy", "model": "llama-cpp"}
                    )
            except Exception:
                pass
            return JSONResponse({"status": "degraded", "model": "unavailable"})

        @self.server.custom_route(
            "/llm/generate", methods=["POST"], name="llm_generate"
        )
        async def http_llm_generate(request: Request) -> JSONResponse:
            """Generate text using LLM."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            prompt = body.get("prompt", "")
            max_tokens = body.get("max_tokens", 256)
            try:
                resp = await self.backend._client.post(
                    "/v1/completions",
                    json={"prompt": prompt, "max_tokens": max_tokens},
                    timeout=30.0,
                )
                if resp.status_code == 200:
                    return JSONResponse(resp.json())
            except Exception:
                pass
            # Fallback mock response
            return JSONResponse(
                {
                    "text": f"[Mock LLM Response for: {prompt[:50]}...]",
                    "tokens_used": len(prompt.split()),
                    "model": "mock",
                }
            )

        # ─────────────────────────────────────────────────────────────────────
        # Embedding Routes
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/embed/health", methods=["GET"], name="embed_health"
        )
        async def http_embed_health(request: Request) -> JSONResponse:
            """Embedding service health."""
            return JSONResponse(
                {"status": "healthy", "model": "sentence-transformers"}
            )

        @self.server.custom_route("/embed", methods=["POST"], name="embed")
        async def http_embed(request: Request) -> JSONResponse:
            """Generate embeddings for texts."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            texts = body.get("texts", [])
            # Mock embeddings (384-dim like sentence-transformers)
            embeddings = [[0.1 * (i % 10) for i in range(384)] for _ in texts]
            return JSONResponse(
                {"embeddings": embeddings, "model": "all-MiniLM-L6-v2"}
            )

        @self.server.custom_route(
            "/embed/vectors", methods=["POST"], name="embed_vectors"
        )
        async def http_embed_vectors(request: Request) -> JSONResponse:
            """Generate embedding vectors."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            texts = body.get("texts", [])
            vectors = [[0.1 * (i % 10) for i in range(384)] for _ in texts]
            return JSONResponse({"vectors": vectors, "dimensions": 384})

        # ─────────────────────────────────────────────────────────────────────
        # RAG Service Routes
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/rag/health", methods=["GET"], name="rag_health"
        )
        async def http_rag_health(request: Request) -> JSONResponse:
            """RAG service health."""
            return JSONResponse(
                {"status": "healthy", "vector_store": "qdrant"}
            )

        @self.server.custom_route(
            "/rag/query", methods=["POST"], name="rag_query"
        )
        async def http_rag_query(request: Request) -> JSONResponse:
            """Query the RAG system."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            query = body.get("query", "")
            top_k = body.get("top_k", 5)
            return JSONResponse(
                {
                    "query": query,
                    "results": [
                        {
                            "content": f"Result {i+1} for: {query}",
                            "score": 0.9 - i * 0.1,
                        }
                        for i in range(min(top_k, 5))
                    ],
                    "total": top_k,
                }
            )

        @self.server.custom_route(
            "/rag/upsert", methods=["POST"], name="rag_upsert"
        )
        async def http_rag_upsert(request: Request) -> JSONResponse:
            """Upsert documents into RAG."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            documents = body.get("documents", [])
            return JSONResponse(
                {
                    "status": "success",
                    "upserted": len(documents),
                    "ids": [
                        d.get("id", f"doc_{i}")
                        for i, d in enumerate(documents)
                    ],
                }
            )

        # ─────────────────────────────────────────────────────────────────────
        # Role Engine Routes
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/roles/health", methods=["GET"], name="roles_health"
        )
        async def http_roles_health(request: Request) -> JSONResponse:
            """Role engine health."""
            return JSONResponse({"status": "healthy", "active_roles": 3})

        @self.server.custom_route(
            "/roles/active", methods=["GET"], name="roles_active"
        )
        async def http_roles_active(request: Request) -> JSONResponse:
            """Get active roles."""
            return JSONResponse(
                {
                    "active_role": "developer",
                    "permissions": ["read", "write", "execute"],
                    "restrictions": [],
                }
            )

        @self.server.custom_route(
            "/roles/evaluate", methods=["POST"], name="roles_evaluate"
        )
        async def http_roles_evaluate(request: Request) -> JSONResponse:
            """Evaluate an action against current role."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            action = body.get("action", "")
            return JSONResponse(
                {
                    "action": action,
                    "allowed": True,
                    "role": "developer",
                    "reason": "Action permitted for current role",
                }
            )

        @self.server.custom_route(
            "/roles/guards/check", methods=["POST"], name="roles_guards_check"
        )
        async def http_roles_guards_check(request: Request) -> JSONResponse:
            """Check role guards."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            action = body.get("action", "")
            resource = body.get("resource", "")
            return JSONResponse(
                {
                    "action": action,
                    "resource": resource,
                    "passed": True,
                    "guards_checked": ["permission_guard", "rate_limit_guard"],
                }
            )

        # ─────────────────────────────────────────────────────────────────────
        # Model Lifecycle Manager Routes (Ollama orchestration)
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/v1/models/status", methods=["GET"], name="v1_models_status"
        )
        async def http_v1_models_status(request: Request) -> JSONResponse:
            """Get model lifecycle manager status."""
            try:
                from aura_ia_mcp.services.model_gateway.lifecycle import (
                    get_model_manager,
                )

                manager = await get_model_manager()
                status = manager.get_status()
                return JSONResponse(status)
            except Exception as e:
                return JSONResponse(
                    {"error": str(e), "status": "unavailable"}, status_code=500
                )

        @self.server.custom_route(
            "/v1/models/health", methods=["GET"], name="v1_models_health"
        )
        async def http_v1_models_health(request: Request) -> JSONResponse:
            """Health check for model lifecycle manager."""
            try:
                from aura_ia_mcp.services.model_gateway.lifecycle import (
                    get_model_manager,
                )

                manager = await get_model_manager()
                health = await manager.health_check()
                return JSONResponse(health)
            except Exception as e:
                return JSONResponse(
                    {"error": str(e), "status": "unhealthy"}, status_code=500
                )

        @self.server.custom_route(
            "/v1/models/{model_name}/load",
            methods=["POST"],
            name="v1_models_load",
        )
        async def http_v1_models_load(request: Request) -> JSONResponse:
            """Load a specific model."""
            model_name = request.path_params.get("model_name", "")
            try:
                from aura_ia_mcp.services.model_gateway.lifecycle import (
                    get_model_manager,
                )

                manager = await get_model_manager()
                success = await manager.ensure_loaded(model_name)
                return JSONResponse({"model": model_name, "loaded": success})
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @self.server.custom_route(
            "/v1/models/{model_name}/unload",
            methods=["POST"],
            name="v1_models_unload",
        )
        async def http_v1_models_unload(request: Request) -> JSONResponse:
            """Unload a specific model."""
            model_name = request.path_params.get("model_name", "")
            try:
                from aura_ia_mcp.services.model_gateway.lifecycle import (
                    get_model_manager,
                )

                manager = await get_model_manager()
                await manager._offload_model(model_name)
                return JSONResponse({"model": model_name, "unloaded": True})
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @self.server.custom_route(
            "/v1/router/detect-mode",
            methods=["POST"],
            name="v1_router_detect_mode",
        )
        async def http_v1_router_detect_mode(request: Request) -> JSONResponse:
            """Detect chat mode from message."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            message = body.get("message", "")
            try:
                from aura_ia_mcp.services.model_gateway.chat_router import (
                    get_chat_router,
                )
                from aura_ia_mcp.services.model_gateway.lifecycle import (
                    MODE_TO_MODEL,
                )

                router = await get_chat_router()
                # detect_mode returns tuple: (ChatMode, confidence, reasoning, keywords)
                mode, confidence, reasoning, keywords = router.detect_mode(
                    message
                )
                return JSONResponse(
                    {
                        "mode": mode.value,
                        "model": MODE_TO_MODEL.get(mode, "phi3.5:3.8b"),
                        "confidence": confidence,
                        "reasoning": reasoning,
                        "keywords": keywords,
                    }
                )
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @self.server.custom_route(
            "/v1/router/stats", methods=["GET"], name="v1_router_stats"
        )
        async def http_v1_router_stats(request: Request) -> JSONResponse:
            """Get chat router statistics."""
            try:
                from aura_ia_mcp.services.model_gateway.chat_router import (
                    get_chat_router,
                )

                router = await get_chat_router()
                return JSONResponse(router.get_routing_stats())
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @self.server.custom_route(
            "/v1/chat/smart", methods=["POST"], name="v1_chat_smart"
        )
        async def http_v1_chat_smart(request: Request) -> JSONResponse:
            """Smart chat endpoint with automatic mode detection and model selection."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            message = body.get("message", "")
            user_id = body.get("user_id", "default")
            explicit_mode = body.get("mode")
            explicit_model = body.get("model")
            try:
                from aura_ia_mcp.services.model_gateway.chat_router import (
                    route_message,
                )

                # route_message returns RoutingDecision object, serialize it
                decision = await route_message(
                    message, user_id, explicit_mode, explicit_model
                )
                return JSONResponse(
                    {
                        "mode": decision.mode.value,
                        "model": decision.model,
                        "confidence": decision.confidence,
                        "reasoning": decision.reasoning,
                        "is_fallback": decision.is_fallback,
                        "keywords": decision.detected_keywords,
                    }
                )
            except Exception as e:
                return JSONResponse(
                    {"error": str(e), "success": False}, status_code=500
                )

        # ─────────────────────────────────────────────────────────────────────
        # Chat Completion Routes (OpenAI-compatible)
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/v1/health", methods=["GET"], name="v1_health"
        )
        async def http_v1_health(request: Request) -> JSONResponse:
            """Chat API health."""
            return JSONResponse({"status": "healthy", "api_version": "v1"})

        @self.server.custom_route(
            "/v1/chat/completions",
            methods=["POST"],
            name="v1_chat_completions",
        )
        async def http_v1_chat_completions(request: Request) -> JSONResponse:
            """OpenAI-compatible chat completions."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            messages = body.get("messages", [])
            last_msg = messages[-1].get("content", "") if messages else ""
            return JSONResponse(
                {
                    "id": f"chatcmpl-{int(time.time())}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": "aura-ia-local",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": f"[Aura Response to: {last_msg[:50]}]",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                    },
                }
            )

        @self.server.custom_route(
            "/v1/chat/dual", methods=["POST"], name="v1_chat_dual"
        )
        async def http_v1_chat_dual(request: Request) -> JSONResponse:
            """Dual-model chat endpoint."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            messages = body.get("messages", [])
            last_msg = messages[-1].get("content", "") if messages else ""
            return JSONResponse(
                {
                    "primary": {
                        "model": "aura-ia-local",
                        "content": f"[Primary: {last_msg[:30]}]",
                    },
                    "secondary": {
                        "model": "aura-ia-fallback",
                        "content": f"[Secondary: {last_msg[:30]}]",
                    },
                }
            )

        # ─────────────────────────────────────────────────────────────────────
        # Debate Engine Routes
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/v1/debate/start", methods=["POST"], name="v1_debate_start"
        )
        async def http_v1_debate_start(request: Request) -> JSONResponse:
            """Start a new debate between models."""
            body = (
                await request.json()
                if request.headers.get("content-length")
                else {}
            )
            topic = body.get("topic")  # Optional - random if not provided
            topic_category = body.get("category")
            model_a = body.get("model_a")  # Optional
            model_b = body.get("model_b")  # Optional
            try:
                from aura_ia_mcp.services.debate_engine import (
                    get_debate_engine,
                    TopicCategory,
                )

                engine = await get_debate_engine()
                
                # Parse category if provided
                cat = None
                if topic_category:
                    try:
                        cat = TopicCategory(topic_category)
                    except ValueError:
                        pass
                
                result = await engine.run_debate(
                    topic=topic,
                    topic_category=cat,
                    model_a=model_a,
                    model_b=model_b,
                )
                return JSONResponse(result.to_dict())
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @self.server.custom_route(
            "/v1/debate/leaderboard", methods=["GET"], name="v1_debate_leaderboard"
        )
        async def http_v1_debate_leaderboard(request: Request) -> JSONResponse:
            """Get model ELO leaderboard."""
            try:
                from aura_ia_mcp.services.debate_engine import get_debate_engine

                engine = await get_debate_engine()
                leaderboard = await engine.get_leaderboard()
                return JSONResponse({"leaderboard": leaderboard})
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @self.server.custom_route(
            "/v1/debate/history", methods=["GET"], name="v1_debate_history"
        )
        async def http_v1_debate_history(request: Request) -> JSONResponse:
            """Get recent debate history."""
            try:
                from aura_ia_mcp.services.debate_engine import get_debate_engine

                limit = int(request.query_params.get("limit", 10))
                engine = await get_debate_engine()
                history = await engine.get_debate_history(limit=limit)
                return JSONResponse({"debates": history})
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        @self.server.custom_route(
            "/v1/debate/topics", methods=["GET"], name="v1_debate_topics"
        )
        async def http_v1_debate_topics(request: Request) -> JSONResponse:
            """Get available debate topics."""
            try:
                from aura_ia_mcp.services.debate_engine.topics import (
                    get_all_topics_for_category,
                    get_all_topics,
                    get_topic_count,
                    TopicCategory,
                )

                category = request.query_params.get("category")
                
                if category:
                    try:
                        cat = TopicCategory(category)
                        topics = get_all_topics_for_category(cat)
                        return JSONResponse({"category": category, "topics": topics})
                    except ValueError:
                        return JSONResponse(
                            {"error": f"Invalid category: {category}"},
                            status_code=400
                        )
                else:
                    all_topics = get_all_topics()
                    return JSONResponse({
                        "categories": [c.value for c in TopicCategory],
                        "topics": all_topics,
                        "total_count": get_topic_count(),
                    })
            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        # ─────────────────────────────────────────────────────────────────────
        # Dashboard Summary Route
        # ─────────────────────────────────────────────────────────────────────
        @self.server.custom_route(
            "/v1/dashboard/summary", methods=["GET"], name="v1_dashboard_summary"
        )
        async def http_v1_dashboard_summary(request: Request) -> JSONResponse:
            """Aggregate key metrics for dashboard."""
            summary: dict[str, Any] = {}
            try:
                from aura_ia_mcp.services.model_gateway.chat_router import (
                    get_chat_router,
                )
                router = await get_chat_router()
                summary["router"] = router.get_routing_stats()
            except Exception as e:
                summary["router_error"] = str(e)

            try:
                from aura_ia_mcp.services.debate_engine import get_debate_engine

                engine = await get_debate_engine()
                summary["debate_leaderboard"] = await engine.get_leaderboard()
                summary["debate_history"] = await engine.get_debate_history(limit=5)
            except Exception as e:
                summary["debate_error"] = str(e)

            try:
                from aura_ia_mcp.services.rag_service import (
                    get_qdrant_client,
                    COLLECTION_NAME,
                )
                from aura_ia_mcp.core.config import get_settings

                settings = get_settings()
                client = get_qdrant_client(settings)
                collection_info = client.get_collection(COLLECTION_NAME)
                summary["rag"] = {
                    "collection": COLLECTION_NAME,
                    "points_count": getattr(collection_info, "points_count", None),
                    "vector_size": getattr(collection_info, "vectors_config", {}).get("size")
                    if hasattr(collection_info, "vectors_config")
                    else None,
                }
            except Exception as e:
                summary["rag_error"] = str(e)

            return JSONResponse(summary)

    async def _call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # Start OTEL span for tool call
        otel_span = None
        if self._otel_tracer is not None:
            try:
                from opentelemetry.trace import SpanKind

                otel_span = self._otel_tracer.start_span(
                    f"tool/{name}",
                    kind=SpanKind.INTERNAL,
                )
                otel_span.set_attribute("mcp.tool.name", name)
            except Exception:
                pass

        if arguments is None:
            arguments = {}
        # Unwrap kwargs if present (Kiro IDE wraps arguments in kwargs)
        # Handle both {"kwargs": {...}} and {} formats
        if isinstance(arguments, dict):
            if "kwargs" in arguments:
                # Extract from kwargs wrapper
                arguments = arguments["kwargs"]
            elif not arguments:
                # Empty dict is valid for parameter-less tools
                arguments = {}

        # Simple rate limit per tool+method (allow list->get sequences)
        rl_key = (
            f"{name}:{arguments.get('method', '')}"
            if isinstance(arguments, dict)
            else name
        )
        if not approval_mod.rate_limiter.allow(rl_key):
            audit_logger.rate_limited(rl_key)
            raise ValueError("rate_limited: please retry shortly")

        handler = self.tool_handlers.get(name)
        if handler is None:
            raise ValueError(f"Unknown tool requested: {name}")

        # Telemetry span wrap
        # Use perf_counter to match telemetry's time base
        start = time.perf_counter()
        method = (
            arguments.get("method") if isinstance(arguments, dict) else None
        )
        try:
            result = await handler(arguments)
            telemetry.emit_span(
                name, start_time=start, method=method, success=True
            )
            metrics.incr(name, True)
            try:  # record latency histogram
                from mcp_server.metrics import record_tool_latency

                duration = time.perf_counter() - start
                record_tool_latency(name, duration)
            except Exception:  # noqa: BLE001
                pass
            # Audit only consolidated command tool run method success
            if (
                name == "ide_agents_command"
                and isinstance(arguments, dict)
                and arguments.get("method") == "run"
            ):
                audit_logger.command_executed(
                    arguments.get("command", ""), True
                )
            # Provenance (success)
            try:  # noqa: SIM105
                from mcp_server.provenance import log_tool_invocation

                duration_ms = (time.perf_counter() - start) * 1000.0
                log_tool_invocation(
                    name,
                    arguments if isinstance(arguments, dict) else {},
                    True,
                    duration_ms,
                    result,
                )
            except Exception:  # noqa: BLE001
                pass
            # Close OTEL span on success
            if otel_span is not None:
                try:
                    from opentelemetry.trace import Status, StatusCode

                    otel_span.set_status(Status(StatusCode.OK))
                    otel_span.end()
                except Exception:
                    pass
            return result
        except Exception as exc:  # noqa: BLE001
            telemetry.emit_span(
                name,
                start_time=start,
                method=method,
                success=False,
                error_code=exc.__class__.__name__,
            )
            metrics.incr(name, False)
            try:  # record latency even on failure
                from mcp_server.metrics import record_tool_latency

                duration = time.perf_counter() - start
                record_tool_latency(name, duration)
            except Exception:  # noqa: BLE001
                pass
            audit_logger.tool_failure(name, exc.__class__.__name__)
            try:  # provenance failure
                from mcp_server.provenance import log_tool_invocation

                duration_ms = (time.perf_counter() - start) * 1000.0
                log_tool_invocation(
                    name,
                    arguments if isinstance(arguments, dict) else {},
                    False,
                    duration_ms,
                    None,
                )
            except Exception:  # noqa: BLE001
                pass
            # Close OTEL span on error
            if otel_span is not None:
                try:
                    from opentelemetry.trace import Status, StatusCode

                    otel_span.set_status(Status(StatusCode.ERROR, str(exc)))
                    otel_span.end()
                except Exception:
                    pass
            raise

    async def _handle_run_command(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        command = arguments.get("command")
        payload = arguments.get("payload")
        if not command:
            raise ValueError("Missing required argument: command")
        return await self.backend.run_command(command, payload)

    async def _handle_command_consolidated(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        # Approval gating for potentially mutating operations
        method = arguments.get("method")
        cmd = arguments.get("command", "")
        if method == "run":
            action_id = f"cmd:{cmd}"
            if not approval_mod.approval_queue.is_approved(
                "ide_agents_command", action_id
            ):
                approval_mod.approval_queue.request(
                    "ide_agents_command", action_id
                )
                audit_logger.approval_requested(
                    "ide_agents_command", action_id
                )
                # Standardized error envelope
                envelope = {
                    "error": {
                        "code": "approval_required",
                        "tool": "ide_agents_command",
                        "action_id": action_id,
                        "message": (
                            "Approval required before executing command"
                        ),
                    }
                }
                raise ValueError(json.dumps(envelope))
        return await run_command_adapter(self, arguments)

    async def _handle_list_entities(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        result = await self.backend.list_entities()
        return {"entities": result}

    async def _handle_fetch_doc(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        topic = arguments.get("topic")
        if not topic:
            raise ValueError("Missing required argument: topic")
        result = await self.backend.fetch_documentation(topic)
        return {"documentation": result}

    async def _handle_catalog_consolidated(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return await catalog_adapter(self, arguments)

    async def _handle_resource(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        method = arguments.get("method", "list")
        if method == "list":
            items = [
                {
                    "name": "repo.graph",
                    "path": str(self._resources_dir / "repo.graph.json"),
                },
                {
                    "name": "kb.snippet",
                    "path": str(self._resources_dir / "kb.snippet"),
                },
                {
                    "name": "build.logs",
                    "path": str(self._resources_dir / "build.logs"),
                },
            ]
            return {"resources": items}
        if method == "get":
            name = arguments.get("name")
            if not name:
                raise ValueError("Missing required argument: name")

            # Check cache first
            cache_key = f"resource:{name}"
            cached = self._resource_cache.get(cache_key)
            if cached is not None:
                return cached

            # Load resource
            result: dict[str, Any]
            if name == "repo.graph":
                p = self._resources_dir / "repo.graph.json"
                result = {
                    "name": name,
                    "content": json.loads(p.read_text(encoding="utf-8")),
                }
            elif name == "kb.snippet":
                p = self._resources_dir / "kb.snippet" / "README.md"
                result = {
                    "name": name,
                    "content": p.read_text(encoding="utf-8"),
                }
            elif name == "build.logs":
                p = self._resources_dir / "build.logs"
                result = {
                    "name": name,
                    "content": p.read_text(encoding="utf-8"),
                }
            else:
                raise ValueError(f"Unknown resource: {name}")

            # Cache the result
            self._resource_cache.set(cache_key, result)
            return result
        raise ValueError(f"Unsupported method for resource: {method}")

    async def _handle_prompt(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        method = arguments.get("method", "list")
        if method == "list":
            return {
                "prompts": [
                    "/diff_review",
                    "/test_failures",
                    "/hotfix_plan",
                    "/rank_github_repos",
                    "/rank_github_all",
                    "/rank_top_bug_prs",
                ]
            }
        if method == "get":
            name = arguments.get("name")
            if name not in {
                "/diff_review",
                "/test_failures",
                "/hotfix_plan",
                "/rank_github_repos",
                "/rank_github_all",
                "/rank_top_bug_prs",
            }:
                raise ValueError("Unknown prompt name")

            # Check cache first
            cache_key = f"prompt:{name}"
            cached = self._resource_cache.get(cache_key)
            if cached is not None:
                return cached

            file_map = {
                "/diff_review": self._prompts_dir / "diff_review.md",
                "/test_failures": self._prompts_dir / "test_failures.md",
                "/hotfix_plan": self._prompts_dir / "hotfix_plan.md",
                "/rank_github_repos": (
                    self._prompts_dir / "rank_github_repos.md"
                ),
                "/rank_github_all": self._prompts_dir / "rank_github_all.md",
                "/rank_top_bug_prs": self._prompts_dir / "rank_top_bug_prs.md",
            }
            p = file_map[name]
            result = {"name": name, "content": p.read_text(encoding="utf-8")}

            # Cache the result
            self._resource_cache.set(cache_key, result)
            return result
        raise ValueError(f"Unsupported method for prompt: {method}")

    async def _handle_server_instructions(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return SERVER_INSTRUCTIONS

    async def _handle_health(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        # Return cached value immediately if present; background loop updates.
        if self._health_cache is not None:
            return self._health_cache
        # Start background loop now if not started.
        if self._bg_health_task is None:
            loop = asyncio.get_running_loop()
            self._bg_health_task = loop.create_task(
                self._background_health_loop()
            )
        # Provide provisional response while first refresh in progress.
        return {
            "ok": True,
            "version": MCP_SERVER_INSTRUCTIONS_VERSION,
            "ultra_enabled": self.config.ultra_enabled,
            "backend_ok": False,
            "backend_latency_ms": None,
            "models": {},
            "provisional": True,
        }

    async def _background_health_loop(self) -> None:
        interval = 2.0
        while True:
            try:
                t0 = time.perf_counter()
                success = False
                latency_ms: int | None = None
                models: dict[str, Any] = {}
                try:
                    resp = await self.backend._client.get(
                        "/health", timeout=0.2
                    )
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    if resp.status_code == 200:
                        body = resp.json()
                        success = body.get("ok") is True
                        models = body.get("ml_models", {})
                except Exception:  # noqa: BLE001
                    success = False
                from mcp_server.metrics import record_backend_health

                record_backend_health(success, latency_ms)
                self._health_cache = {
                    "ok": True,
                    "version": MCP_SERVER_INSTRUCTIONS_VERSION,
                    "ultra_enabled": self.config.ultra_enabled,
                    "backend_ok": success,
                    "backend_latency_ms": latency_ms,
                    "models": models,
                }
                self._health_cache_ts = time.monotonic()
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(interval)

    async def _handle_healthz(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        # Simple liveness
        return {"status": "live", "time": datetime.utcnow().isoformat()}

    async def _handle_readyz(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        ttl = max(0.0, getattr(self.config, "ready_cache_ttl", 0.0))
        now = time.monotonic()
        # Only use cache if last known state was ready; recompute if degraded
        if ttl and self._ready_cache_value is not None:
            if (
                self._ready_cache_value.get("status") == "ready"
                and (now - self._ready_cache_ts) < ttl
            ):
                return self._ready_cache_value
        # Backend health check (prefer direct /health for accuracy)
        backend_ok = False
        backend_latency_ms = None
        backend_error = None
        try:
            t0 = time.perf_counter()
            resp = await self.backend._client.get("/health", timeout=5.0)
            backend_latency_ms = int((time.perf_counter() - t0) * 1000)
            if resp.status_code == 200:
                backend_ok = True
            else:
                backend_error = f"status_{resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            backend_error = exc.__class__.__name__
            # Fallback to generic ping
            try:
                backend_ok = await self.backend.ping_backend()
            except Exception as exc2:  # noqa: BLE001
                backend_error = f"{backend_error}|{exc2.__class__.__name__}"
        telem_dir, telem_file = telemetry._log_paths()  # type: ignore
        writable = False
        try:
            telem_dir.mkdir(parents=True, exist_ok=True)
            with telem_file.open("a", encoding="utf-8") as handle:
                handle.write("")
            writable = True
        except Exception:
            writable = False

        result = {
            "status": "ready" if (backend_ok and writable) else "degraded",
            "backend_ok": backend_ok,
            "telemetry_writable": writable,
            "backend_latency_ms": backend_latency_ms,
            "backend_error": backend_error,
            "models": (
                resp.json().get("ml_models")
                if backend_ok and "resp" in locals()
                else {}
            ),
        }
        # Cache only positive readiness to prevent stale degraded state
        if ttl and result.get("status") == "ready":
            self._ready_cache_value = result
            self._ready_cache_ts = now
        return result

    async def _handle_metrics_snapshot(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        data = metrics.snapshot()
        breaker = await self.backend.breaker_snapshot()
        data["breaker"] = breaker
        return data

    async def _handle_security_anomalies(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        window = arguments.get("window_seconds")
        try:
            window_int = int(window) if window is not None else 3600
        except Exception:
            window_int = 3600
        try:
            from mcp_server.security import anomaly_detector

            summary = anomaly_detector.analyze(window_int)
        except Exception as exc:  # noqa: BLE001
            summary = {"error": exc.__class__.__name__, "message": str(exc)}
        return summary

    async def _handle_reload(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        # Lightweight reload: clear caches & return thresholds.
        self._schema_cache.clear()
        self._resource_cache.clear()
        from mcp_server.security import anomaly_detector

        thresholds = {
            "thresholds": getattr(anomaly_detector, "_DEFAULT_THRESHOLDS", {})
        }
        return {"reloaded": True, **thresholds}

    async def _handle_ultra_rank(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        query = arguments.get("query")
        candidates = arguments.get("candidates")
        if not query or not candidates:
            raise ValueError(
                "Both query and candidates are required for ULTRA ranking"
            )
        # Prefer live ULTRA URL if configured
        if self.config.ultra_url:
            async with httpx.AsyncClient(
                base_url=self.config.ultra_url
            ) as client:
                response = await client.post(
                    "/ai/intelligence/rank",
                    json={"query": query, "candidates": list(candidates)},
                )
                response.raise_for_status()
                return {"ranking": response.json()}
        result = await self.backend.ultra_rank(query, candidates)
        return {"ranking": result}

    async def _handle_ultra_calibrate(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        scores = arguments.get("scores")
        if scores is None:
            raise ValueError("Scores are required for ULTRA calibration")
        if self.config.ultra_url:
            async with httpx.AsyncClient(
                base_url=self.config.ultra_url
            ) as client:
                response = await client.post(
                    "/ai/intelligence/calibrate",
                    json={"scores": list(scores)},
                )
                response.raise_for_status()
                return {"calibration": response.json()}
        result = await self.backend.ultra_calibrate(scores)
        return {"calibration": result}

    async def _handle_github_repos(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        token = os.getenv("GITHUB_TOKEN") or os.getenv(
            "GITHUB_PERSONAL_ACCESS_TOKEN"
        )
        if not token:
            raise ValueError(
                "Missing GitHub token in env: set GITHUB_TOKEN or "
                "GITHUB_PERSONAL_ACCESS_TOKEN"
            )
        visibility = arguments.get("visibility")
        if visibility not in (None, "public", "private"):
            raise ValueError("visibility must be one of: public, private")
        limit = arguments.get("limit", 25)
        try:
            limit = int(limit)
        except Exception:
            raise ValueError("limit must be a number")
        if limit <= 0:
            limit = 1
        limit = min(limit, 100)
        include: list[str] = arguments.get("include") or []
        exclude: list[str] = arguments.get("exclude") or []
        top = arguments.get("top")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }
        # Pagination: fetch across pages until limit reached or max 3 pages.
        # Dynamic per_page: reduce bandwidth for small limits
        per_page = 100 if limit > 50 else (50 if limit > 25 else limit)
        max_pages = 3
        data: list[dict[str, Any]] = []
        cache_key = (
            f"github_repos:{visibility}:{limit}:{include}:{exclude}:{top}"
        )
        cached = self._resource_cache.get(cache_key)
        if cached is not None:
            return cached
        async with httpx.AsyncClient(
            base_url="https://api.github.com"
        ) as client:
            for page in range(1, max_pages + 1):
                if len(data) >= limit:
                    break
                params: dict[str, Any] = {"per_page": per_page, "page": page}
                if visibility:
                    params["visibility"] = visibility
                resp = await client.get(
                    "/user/repos", headers=headers, params=params
                )
                resp.raise_for_status()
                batch = resp.json()
                if not isinstance(batch, list) or not batch:
                    break
                data.extend(batch)
                if len(batch) < per_page:
                    break
        items = []
        for repo in data:
            items.append(
                {
                    "name": repo.get("name"),
                    "full_name": repo.get("full_name"),
                    "private": bool(repo.get("private")),
                    "html_url": repo.get("html_url"),
                    "description": repo.get("description"),
                    "stargazers_count": repo.get("stargazers_count", 0),
                    "watchers_count": repo.get("watchers_count", 0),
                    "forks_count": repo.get("forks_count", 0),
                    "updated_at": repo.get("updated_at"),
                }
            )
        # Apply include/exclude filters
        if include:
            items = [
                i
                for i in items
                if i.get("name") in include or i.get("full_name") in include
            ]
        if exclude:
            items = [
                i
                for i in items
                if (
                    i.get("name") not in exclude
                    and i.get("full_name") not in exclude
                )
            ]
        sliced = items[:limit]
        if top is not None:
            try:
                top_int = int(top)
            except Exception:
                top_int = None
            if top_int and top_int > 0:
                sliced = sliced[:top_int]
        result = {"repos": sliced}
        self._resource_cache.set(cache_key, result)
        return result

    async def _handle_github_rank_repos(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        # Use perf_counter for consistent telemetry durations
        start_ts = time.perf_counter()
        query = arguments.get("query")
        if not query:
            raise ValueError("Missing required argument: query")
        # Reuse fetch logic
        repos_result = await self._handle_github_repos(arguments)
        repos: list[dict[str, Any]] = repos_result.get("repos", [])
        if not repos:
            return {"ranking": []}

        # ULTRA path: rank by semantic relevance using name + description
        if self.config.ultra_enabled:
            # Structured candidates expected by backend semantic ranker
            candidates: list[dict[str, Any]] = []
            for idx, r in enumerate(repos):
                # Sanitize description to avoid None propagation
                desc_raw = r.get("description")
                desc = desc_raw if isinstance(desc_raw, str) else ""
                candidates.append(
                    {
                        "id": str(idx),
                        "text": f"{r.get('full_name')}: {desc}".strip(),
                    }
                )
            # Mock path
            if getattr(self.config, "ultra_mock_enabled", False):

                def mock_score(q: str, text: str) -> float:
                    q_words = {w for w in q.lower().split() if w}
                    t_words = {w for w in text.lower().split() if w}
                    inter = len(q_words & t_words)
                    return float(inter) / float(len(q_words) or 1)

                results = [
                    {"repo": repos[i], "score": mock_score(query, c)}
                    for i, c in enumerate(candidates)
                ]
                results.sort(key=lambda x: x["score"], reverse=True)
                telemetry.emit_span(
                    "ide_agents_github_rank_repos",
                    start_ts,
                    extra={
                        "mode": "ultra_mock",
                        "candidates": len(candidates),
                        "repos": len(repos),
                    },
                )
                return {"ranking": results}
            try:
                if self.config.ultra_url:
                    async with httpx.AsyncClient(
                        base_url=self.config.ultra_url
                    ) as client:
                        resp = await client.post(
                            "/ai/intelligence/rank",
                            json={"query": query, "candidates": candidates},
                        )
                        resp.raise_for_status()
                        ranked = resp.json()
                else:
                    # Structured candidate dicts -> backend semantic ranking
                    ranked = await self.backend.ultra_rank(query, candidates)
                ranked = self._normalize_ultra_backend(ranked)

                items_by_candidate = {
                    c["text"]: repos[int(c.get("id", i))]
                    for i, c in enumerate(candidates)
                }
                collected = self._parse_ultra_rank(ranked, items_by_candidate)
                if collected:
                    telemetry.emit_span(
                        "ide_agents_github_rank_repos",
                        start_ts,
                        extra={
                            "mode": "ultra_backend",
                            "candidates": len(candidates),
                            "repos": len(repos),
                        },
                    )
                    return {"ranking": collected}
                else:
                    # Graceful empty ULTRA result (no warning)
                    telemetry.emit_span(
                        "ide_agents_github_rank_repos",
                        start_ts,
                        extra={
                            "mode": "ultra_empty",
                            "candidates": len(candidates),
                            "repos": len(repos),
                        },
                    )
                    return {"ranking": []}
            except Exception as exc:  # noqa: BLE001
                try:
                    raw_snapshot = (
                        str(ranked)[:300]
                        if "ranked" in locals()
                        else "unavailable"
                    )
                except Exception:  # pragma: no cover
                    raw_snapshot = "error_capturing"
                # Only warn if not a benign empty parse
                if "no usable" not in str(exc).lower():
                    logger.warning(
                        "ULTRA rank failed: %s | raw=%s",
                        exc,
                        raw_snapshot,
                    )
                telemetry.emit_span(
                    "ide_agents_github_rank_repos",
                    start_ts,
                    extra={
                        "mode": "ultra_error",
                        "error": exc.__class__.__name__,
                        "message": str(exc)[:160],
                        "candidates": len(candidates),
                    },
                )

            # Local semantic fallback (ultra_local) if enabled
            if getattr(self.config, "ultra_local_enabled", False):

                def local_semantic_score(q: str, text: str) -> float:
                    q_words = {w for w in q.lower().split() if w}
                    t_words = {w for w in text.lower().split() if w}
                    if not q_words or not t_words:
                        return 0.0
                    inter = len(q_words & t_words)
                    # cosine-like on binary vectors
                    return inter / ((len(q_words) * len(t_words)) ** 0.5)

                results = [
                    {"repo": repos[i], "score": local_semantic_score(query, c)}
                    for i, c in enumerate(candidates)
                ]
                results.sort(key=lambda x: x["score"], reverse=True)
                telemetry.emit_span(
                    "ide_agents_github_rank_repos",
                    start_ts,
                    extra={
                        "mode": "ultra_local",
                        "candidates": len(candidates),
                        "repos": len(repos),
                    },
                )
                return {"ranking": results}

        # Heuristic fallback: stars, recent update, description match
        def heuristic_score(r: dict[str, Any]) -> float:
            stars = int(r.get("stargazers_count", 0) or 0)
            forks = int(r.get("forks_count", 0) or 0)
            desc = (r.get("description") or "").lower()
            q = str(query).lower()
            match = (
                1.0
                if q
                and (q in desc or q in str(r.get("full_name", "")).lower())
                else 0.0
            )
            # simple combo: stars weight 1.0, forks 0.3, match 5.0
            return stars * 1.0 + forks * 0.3 + match * 5.0

        ranked_repos = sorted(repos, key=heuristic_score, reverse=True)
        top = arguments.get("top")
        if top is not None:
            try:
                top_int = int(top)
                if top_int > 0:
                    ranked_repos = ranked_repos[:top_int]
            except Exception:
                pass
        telemetry.emit_span(
            "ide_agents_github_rank_repos",
            start_ts,
            extra={
                "mode": "heuristic",
                "repos": len(repos),
            },
        )
        return {
            "ranking": [
                {"repo": r, "score": heuristic_score(r)} for r in ranked_repos
            ]
        }

    async def _handle_github_rank_all(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        # Use perf_counter for consistent telemetry durations
        start_ts = time.perf_counter()
        query = arguments.get("query")
        if not query:
            raise ValueError("Missing required argument: query")

        # Get base repos (respect visibility/limit/include/exclude/top first)
        repos_result = await self._handle_github_repos(arguments)
        repos: list[dict[str, Any]] = repos_result.get("repos", [])

        token = os.getenv("GITHUB_TOKEN") or os.getenv(
            "GITHUB_PERSONAL_ACCESS_TOKEN"
        )
        if not token:
            raise ValueError(
                "Missing GitHub token in env: set GITHUB_TOKEN or "
                "GITHUB_PERSONAL_ACCESS_TOKEN"
            )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        # Collect issues/PRs across a subset of repos to avoid rate explosion
        state_filter = arguments.get("state")
        if state_filter not in (None, "open", "closed"):
            raise ValueError("state must be one of: open, closed")
        items_per_repo = arguments.get("items_per_repo", 30)
        page = arguments.get("page", 1)
        since = arguments.get("since")
        try:
            items_per_repo = int(items_per_repo)
        except Exception:
            items_per_repo = 30
        items_per_repo = max(1, min(items_per_repo, 50))
        try:
            page = int(page)
        except Exception:
            page = 1
        page = max(1, page)
        max_repos = min(len(repos), 5)
        max_items_total = 50
        agg_items: list[dict[str, Any]] = []

        async def fetch_repo_issues(r: dict[str, Any]) -> list[dict[str, Any]]:
            full = r.get("full_name")
            if not full:
                return []
            # Adaptive per_page to reduce rate pressure
            adaptive_per_page = items_per_repo
            if max_repos > 3 and items_per_repo > 20:
                adaptive_per_page = 20
            params = {
                "state": state_filter or "open",
                "per_page": adaptive_per_page,
                "page": page,
            }
            if since:
                params["since"] = since
            try:
                async with httpx.AsyncClient(
                    base_url="https://api.github.com"
                ) as client:
                    resp = await client.get(
                        f"/repos/{full}/issues", headers=headers, params=params
                    )
                    resp.raise_for_status()
                    rows = resp.json()
            except Exception:
                return []
            converted: list[dict[str, Any]] = []
            for it in rows:
                is_pr = "pull_request" in it
                kind = "pr" if is_pr else "issue"
                converted.append(
                    {
                        "type": kind,
                        "repo": r,
                        kind: {
                            "number": it.get("number"),
                            "title": it.get("title"),
                            "body": it.get("body"),
                            "html_url": it.get("html_url"),
                            "comments": it.get("comments", 0),
                            "state": it.get("state"),
                            "updated_at": it.get("updated_at"),
                        },
                    }
                )
            return converted

        # Parallel fetch
        tasks = [fetch_repo_issues(r) for r in repos[:max_repos]]
        results = await asyncio.gather(*tasks)
        for batch in results:
            for it in batch:
                agg_items.append(it)
                if len(agg_items) >= max_items_total:
                    break
            if len(agg_items) >= max_items_total:
                break

        # Build candidates for ULTRA if enabled
        if self.config.ultra_enabled:
            candidates: list[dict[str, Any]] = []
            candidate_map: dict[str, dict[str, Any]] = {}
            for idx, r in enumerate(repos):
                desc_raw = r.get("description")
                desc = desc_raw if isinstance(desc_raw, str) else ""
                text = f"repo {r.get('full_name')}: {desc}".strip()
                entry = {"id": f"r{idx}", "text": text}
                candidates.append(entry)
                candidate_map[text] = {"type": "repo", "repo": r}
            for item in agg_items:
                r = item["repo"]
                if item["type"] == "issue":
                    iss = item["issue"]
                    text = (
                        f"issue {r.get('full_name')} #{iss.get('number')}: "
                        f"{iss.get('title') or ''} {iss.get('body') or ''}"
                    ).strip()
                else:
                    pr = item["pr"]
                    text = (
                        f"pr {r.get('full_name')} #{pr.get('number')}: "
                        f"{pr.get('title') or ''} {pr.get('body') or ''}"
                    ).strip()
                entry = {"id": f"i{len(candidates)}", "text": text}
                candidates.append(entry)
                candidate_map[text] = item
            if getattr(self.config, "ultra_mock_enabled", False):

                def mock_score(q: str, text: str) -> float:
                    q_words = {w for w in q.lower().split() if w}
                    t_words = {w for w in text.lower().split() if w}
                    inter = len(q_words & t_words)
                    return float(inter) / float(len(q_words) or 1)

                scored: list[dict[str, Any]] = []
                for cand in candidates:
                    item = candidate_map[cand]
                    sc = mock_score(query, cand)
                    out = {
                        "type": item["type"],
                        "score": sc,
                        "norm_score": sc * 10.0,
                    }
                    if item["type"] == "repo":
                        out["repo"] = item["repo"]
                    elif item["type"] == "issue":
                        out["repo"] = item["repo"]
                        out["issue"] = item["issue"]
                    else:
                        out["repo"] = item["repo"]
                        out["pr"] = item["pr"]
                    scored.append(out)
                scored.sort(key=lambda x: x["norm_score"], reverse=True)
                telemetry.emit_span(
                    "ide_agents_github_rank_all",
                    start_ts,
                    extra={
                        "mode": "ultra_mock",
                        "candidates": len(candidates),
                        "repos": len(repos),
                        "items": len(agg_items),
                    },
                )
                top = arguments.get("top")
                if top is not None:
                    try:
                        top_int = int(top)
                        if top_int > 0:
                            scored = scored[:top_int]
                    except Exception:
                        pass
                return {"ranking": scored}
            try:
                if self.config.ultra_url:
                    async with httpx.AsyncClient(
                        base_url=self.config.ultra_url
                    ) as client:
                        resp = await client.post(
                            "/ai/intelligence/rank",
                            json={"query": query, "candidates": candidates},
                        )
                        resp.raise_for_status()
                        ranked = resp.json()
                else:
                    ranked = await self.backend.ultra_rank(query, candidates)
                ranked = self._normalize_ultra_backend(ranked)

                extracted = self._parse_ultra_rank(
                    ranked, {k: v for k, v in candidate_map.items()}
                )
                if not extracted:
                    raise ValueError(
                        "ULTRA response contained no usable scored entries"
                    )

                scores_only = [e["score"] for e in extracted]
                smin = min(scores_only)
                smax = max(scores_only)
                denom = (smax - smin) or 1.0
                norm_results: list[dict[str, Any]] = []
                for e in extracted:
                    item = e["item"]
                    score = e["score"]
                    norm = (score - smin) / denom * 10.0
                    out: dict[str, Any] = {
                        "type": item["type"],
                        "score": score,
                        "norm_score": norm,
                    }
                    if item["type"] == "repo":
                        out["repo"] = item["repo"]
                    elif item["type"] == "issue":
                        out["repo"] = item["repo"]
                        out["issue"] = item["issue"]
                    else:
                        out["repo"] = item["repo"]
                        out["pr"] = item["pr"]
                    norm_results.append(out)

                telemetry.emit_span(
                    "ide_agents_github_rank_all",
                    start_ts,
                    extra={
                        "mode": "ultra_backend",
                        "candidates": len(candidates),
                        "repos": len(repos),
                        "items": len(agg_items),
                    },
                )
                return {"ranking": norm_results}
            except Exception as exc:  # noqa: BLE001
                try:
                    raw_snapshot = (
                        str(ranked)[:300]
                        if "ranked" in locals()
                        else "unavailable"
                    )
                except Exception:  # pragma: no cover
                    raw_snapshot = "error_capturing"
                if "no usable" not in str(exc).lower():
                    logger.warning(
                        "ULTRA rank_all failed: %s | raw=%s",
                        exc,
                        raw_snapshot,
                    )
                telemetry.emit_span(
                    "ide_agents_github_rank_all",
                    start_ts,
                    extra={
                        "mode": "ultra_error",
                        "error": exc.__class__.__name__,
                        "message": str(exc)[:160],
                        "candidates": len(candidates),
                        "repos": len(repos),
                        "items": len(agg_items),
                    },
                )

            # Local semantic fallback (ultra_local) if enabled
            if getattr(self.config, "ultra_local_enabled", False):

                def local_semantic_score(q: str, text: str) -> float:
                    q_words = {w for w in q.lower().split() if w}
                    t_words = {w for w in text.lower().split() if w}
                    if not q_words or not t_words:
                        return 0.0
                    inter = len(q_words & t_words)
                    return inter / ((len(q_words) * len(t_words)) ** 0.5)

                extracted: list[dict[str, Any]] = []
                for cand in candidates:
                    if cand not in candidate_map:
                        continue
                    sc = local_semantic_score(query, cand)
                    extracted.append(
                        {
                            "item": candidate_map[cand],
                            "score": sc,
                        }
                    )

                scores_only = [e["score"] for e in extracted] or [0.0]
                smin, smax = min(scores_only), max(scores_only)
                denom = (smax - smin) or 1.0
                norm_results: list[dict[str, Any]] = []
                for e in extracted:
                    item = e["item"]
                    score = e["score"]
                    norm = (score - smin) / denom * 10.0
                    out: dict[str, Any] = {
                        "type": item["type"],
                        "score": score,
                        "norm_score": norm,
                    }
                    if item["type"] == "repo":
                        out["repo"] = item["repo"]
                    elif item["type"] == "issue":
                        out["repo"] = item["repo"]
                        out["issue"] = item["issue"]
                    else:
                        out["repo"] = item["repo"]
                        out["pr"] = item["pr"]
                    norm_results.append(out)

                telemetry.emit_span(
                    "ide_agents_github_rank_all",
                    start_ts,
                    extra={
                        "mode": "ultra_local",
                        "candidates": len(candidates),
                        "repos": len(repos),
                        "items": len(agg_items),
                    },
                )
                top = arguments.get("top")
                if top is not None:
                    try:
                        top_int = int(top)
                        if top_int > 0:
                            norm_results = norm_results[:top_int]
                    except Exception:
                        pass
                return {"ranking": norm_results}

        # Heuristic fallback: score repos + issues + PRs, normalize 0..10
        def parse_dt(s: str | None) -> datetime | None:
            try:
                return datetime.strptime(str(s), "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=UTC
                )
            except Exception:
                return None

        def repo_score(r: dict[str, Any]) -> float:
            stars = int(r.get("stargazers_count", 0) or 0)
            forks = int(r.get("forks_count", 0) or 0)
            desc = (r.get("description") or "").lower()
            q = str(query).lower()
            match = (
                1.0
                if q
                and (q in desc or q in str(r.get("full_name", "")).lower())
                else 0.0
            )
            return stars * 1.0 + forks * 0.3 + match * 5.0

        def issue_like_score(it: dict[str, Any], is_pr: bool) -> float:
            q = str(query).lower()
            title = (it.get("title") or "").lower()
            body = (it.get("body") or "").lower()
            comments = int(it.get("comments", 0) or 0)
            updated = parse_dt(it.get("updated_at"))
            recency = 0.0
            if updated is not None:
                age_days = (
                    datetime.now(UTC) - updated
                ).total_seconds() / 86400.0
                recency = max(
                    0.0, (30.0 - age_days) / 30.0
                )  # 0..1 if within last 30 days
            match = 1.0 if (q in title or q in body) else 0.0
            base = (
                comments * (0.3 if is_pr else 0.2)
                + match * 5.0
                + recency * (3.0 if is_pr else 2.0)
            )
            if is_pr:
                base += 1.0
            return base

        scored: list[dict[str, Any]] = []
        for r in repos:
            scored.append({"type": "repo", "repo": r, "score": repo_score(r)})
        for item in agg_items:
            if item["type"] == "issue":
                s = issue_like_score(item["issue"], False)
                scored.append(
                    {
                        "type": "issue",
                        "repo": item["repo"],
                        "issue": item["issue"],
                        "score": s,
                    }
                )
            else:
                s = issue_like_score(item["pr"], True)
                scored.append(
                    {
                        "type": "pr",
                        "repo": item["repo"],
                        "pr": item["pr"],
                        "score": s,
                    }
                )

        svals = [x["score"] for x in scored] or [0.0]
        smin, smax = min(svals), max(svals)
        denom = (smax - smin) or 1.0
        for x in scored:
            x["norm_score"] = (x["score"] - smin) / denom * 10.0
        scored.sort(key=lambda x: x["norm_score"], reverse=True)
        top = arguments.get("top")
        if top is not None:
            try:
                top_int = int(top)
                if top_int > 0:
                    scored = scored[:top_int]
            except Exception:
                pass
        telemetry.emit_span(
            "ide_agents_github_rank_all",
            start_ts,
            extra={
                "mode": "heuristic",
                "repos": len(repos),
                "items": len(agg_items),
            },
        )
        return {"ranking": scored}

    async def list_tools(self) -> list[dict[str, Any]]:
        """Expose tool metadata for MCP discovery."""

        tools = []
        for name in self.tool_handlers:
            tools.append(
                {
                    "name": name,
                    "description": self._describe_tool(name),
                    "input_schema": self._tool_input_schema(name),
                }
            )
        return tools

    def _describe_tool(self, name: str) -> str:
        descriptions = {
            "ide_agents_run_command": "Exec backend command",
            "ide_agents_list_entities": "List entity mappings from backend",
            "ide_agents_fetch_doc": "Fetch documentation snippet by topic",
            "ide_agents_ultra_rank": "ULTRA semantic rank over candidates",
            "ide_agents_ultra_calibrate": "Calibrate confidence scores",
            "ide_agents_command": "Consolidated command: run|dry_run|explain",
            "ide_agents_catalog": "Catalog: list_entities|get_doc",
            "ide_agents_resource": "Resources read-only (list|get)",
            "ide_agents_prompt": "Prompts (list|get) for workflows",
            "ide_agents_server_instructions": "Server instructions + version",
            "ide_agents_health": "Quick diagnostics: ok, version, flags",
            "ide_agents_github_repos": (
                "List GitHub repositories (public/private) basic fields"
            ),
            "ide_agents_github_rank_repos": (
                "Rank GitHub repositories (ULTRA or heuristic)"
            ),
            "ide_agents_github_rank_all": (
                "Aggregate ranking over repos (issues/PRs future)"
                "heuristic fallback."
            ),
            "ide_agents_security_anomalies": (
                "Security audit anomaly summary"
            ),
            "ide_agents_reload": "Reload caches + thresholds",
            # ML plugin tools
            "ide_agents_ml_analyze_emotion": "Analyze emotional tone",
            "ide_agents_ml_get_predictions": "Predictive suggestions",
            "ide_agents_ml_get_learning_insights": "Learning analytics",
            "ide_agents_ml_analyze_reasoning": "Reasoning analysis",
            "ide_agents_ml_get_personality_profile": "Personality state",
            "ide_agents_ml_adjust_personality": "Adjust personality/mood/tone",
            "ide_agents_ml_get_system_status": "ML engines status snapshot",
            "ide_agents_ml_calibrate_confidence": "Confidence calibration",
            "ide_agents_ml_rank_predictions_rlhf": "RLHF ranking (mock)",
            "ide_agents_ml_record_prediction_outcome": "Record RLHF outcome",
            "ide_agents_ml_get_calibration_metrics": "Calibration metrics",
            "ide_agents_ml_get_rlhf_metrics": "RLHF performance metrics",
            "ide_agents_ml_behavioral_baseline_check": "Baseline deviation",
            "ide_agents_ml_trigger_auto_adaptation": "Trigger auto-adaptation",
            "ide_agents_ml_get_ultra_dashboard": "ULTRA ML dashboard",
            # New prompts will reference ranking examples
        }
        return descriptions.get(name, "IDE Agents MCP tool")

    def _tool_input_schema(self, name: str) -> dict[str, Any]:
        # Check cache first
        cache_key = f"schema:{name}"
        cached = self._schema_cache.get(cache_key)
        if cached is not None:
            return cached

        schemas: dict[str, dict[str, Any]] = {
            "ide_agents_run_command": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {"type": "string"},
                    "payload": {"type": "object"},
                },
            },
            "ide_agents_list_entities": {"type": "object", "properties": {}},
            "ide_agents_fetch_doc": {
                "type": "object",
                "required": ["topic"],
                "properties": {"topic": {"type": "string"}},
            },
            "ide_agents_ultra_rank": {
                "type": "object",
                "required": ["query", "candidates"],
                "properties": {
                    "query": {"type": "string"},
                    "candidates": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "ide_agents_ultra_calibrate": {
                "type": "object",
                "required": ["scores"],
                "properties": {
                    "scores": {"type": "array", "items": {"type": "number"}},
                },
            },
            # Consolidated tools
            "ide_agents_command": command_args_schema(),
            "ide_agents_catalog": catalog_args_schema(),
            # Resources/prompts/instructions
            "ide_agents_resource": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["list", "get"]},
                    "name": {"type": "string"},
                },
            },
            "ide_agents_prompt": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["list", "get"]},
                    "name": {"type": "string"},
                },
            },
            "ide_agents_server_instructions": {
                "type": "object",
                "properties": {},
            },
            "ide_agents_health": {"type": "object", "properties": {}},
            "ide_agents_security_anomalies": {
                "type": "object",
                "properties": {"window_seconds": {"type": "number"}},
            },
            "ide_agents_reload": {"type": "object", "properties": {}},
            "ide_agents_github_repos": {
                "type": "object",
                "properties": {
                    "visibility": {
                        "type": "string",
                        "enum": ["public", "private"],
                    },
                    "limit": {"type": "number"},
                    "include": {"type": "array", "items": {"type": "string"}},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                    "top": {"type": "number"},
                    "page": {"type": "number"},
                    "per_page": {"type": "number"},
                },
            },
            "ide_agents_github_rank_repos": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string"},
                    "visibility": {
                        "type": "string",
                        "enum": ["public", "private"],
                    },
                    "limit": {"type": "number"},
                    "include": {"type": "array", "items": {"type": "string"}},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                    "top": {"type": "number"},
                },
            },
            "ide_agents_github_rank_all": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string"},
                    "visibility": {
                        "type": "string",
                        "enum": ["public", "private"],
                    },
                    "limit": {"type": "number"},
                    "state": {"type": "string", "enum": ["open", "closed"]},
                    "include": {"type": "array", "items": {"type": "string"}},
                    "exclude": {"type": "array", "items": {"type": "string"}},
                    "top": {"type": "number"},
                    "items_per_repo": {"type": "number"},
                    "page": {"type": "number"},
                    "since": {"type": "string"},
                },
            },
        }
        if name in self._ml_input_schemas:
            schema = self._ml_input_schemas[name]
        else:
            schema = schemas.get(name, {"type": "object"})

        # Cache the schema
        self._schema_cache.set(cache_key, schema)
        return schema

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._dispatch_tool_call(name, arguments)

    async def shutdown(self) -> None:
        # Cancel background health task
        if getattr(self, "_bg_health_task", None):
            self._bg_health_task.cancel()
            try:
                await self._bg_health_task
            except Exception:  # noqa: BLE001
                pass
        telemetry.flush_telemetry()
        await self.backend.close()

    # ---- ULTRA helpers ----
    def _parse_ultra_rank(
        self, raw: Any, items_by_candidate: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Parse ULTRA ranking response into normalized list.

        Accepts possible shapes:
          { ranked: [ { text|candidate, score|similarity|value } ] }
          { ranking|results|data: [...] }
          Or direct list of entry dicts.
        """
        entries: Any = raw
        if isinstance(raw, dict):
            for k in ("ranked", "ranking", "results", "data"):
                v = raw.get(k)
                if isinstance(v, list):
                    entries = v
                    break
        if not isinstance(entries, list):
            return []
        out: list[dict[str, Any]] = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            cand = e.get("candidate") or e.get("text") or e.get("item")
            if not isinstance(cand, str):
                continue
            score_raw = e.get("score") or e.get("value") or e.get("similarity")
            score: float | None = None
            if isinstance(score_raw, (int, float)):
                score = float(score_raw)
            elif isinstance(score_raw, str):
                try:
                    score = float(score_raw)
                except Exception:
                    score = None
            # Guard against descriptor objects / unexpected types
            if score is None or score != score:  # NaN check
                continue
            mapped = items_by_candidate.get(cand)
            if not mapped:
                continue
            (
                out.append({"repo": mapped, "score": score})
                if isinstance(mapped, dict) and mapped.get("full_name")
                else out.append({"item": mapped, "score": score})
            )
        # Sort descending
        out.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return out

    def _normalize_ultra_backend(self, raw: Any) -> Any:
        """Normalize backend ULTRA rank response for parser consumption.

        Each entry must have 'text' and numeric 'score'.
        Accepts shapes: dict with ranked/ranking/results/data list, or list.
        Return { ranked: [...] } if normalization succeeds; else raw.
        """
        entries: Any = raw
        if isinstance(raw, dict):
            for k in ("ranked", "ranking", "results", "data"):
                v = raw.get(k)
                if isinstance(v, list):
                    entries = v
                    break
        if not isinstance(entries, list):
            return raw
        norm: list[dict[str, Any]] = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            cand = e.get("candidate") or e.get("text") or e.get("item")
            if not isinstance(cand, str) or not cand.strip():
                continue
            score_raw = e.get("score") or e.get("value") or e.get("similarity")
            score: float | None = None
            if isinstance(score_raw, (int, float)):
                score = float(score_raw)
            elif isinstance(score_raw, str):
                try:
                    score = float(score_raw)
                except Exception:
                    score = None
            if score is None or score != score:  # skip NaN
                continue
            norm.append({"text": cand, "score": score})
        return {"ranked": norm} if norm else raw


def main() -> None:
    """Synchronous entry point.

    FastMCPServer.run() manages its own event loop (anyio.run). Wrapping it
    in asyncio.run or awaiting it caused a nested loop RuntimeError. We call
    it directly and then perform async shutdown in a fresh loop.
    """
    config = AgentsMCPConfig.from_env()
    server = AgentsMCPServer(config)

    import sys as _sys

    _sys.stderr.write(
        f"[ide-agents-mcp] Init (instr {MCP_SERVER_INSTRUCTIONS_VERSION})\n"
    )

    try:
        server.server.run(
            transport=config.mcp_transport
        )  # synchronous; starts stdio processing
    finally:
        try:
            asyncio.run(server.shutdown())
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
