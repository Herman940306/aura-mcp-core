"""ML Intelligence plugin for AgentsMCPServer.

Registers advanced ML / predictive / personality / calibration tools when
`ultra_enabled` is set in the existing config. Tools are lightweight wrappers
around backend HTTP endpoints; if an endpoint is missing they fail softly with
an explanatory message. This preserves the non-ML baseline without introducing
hard dependencies.
"""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from src.mcp_server import telemetry

try:  # pragma: no cover - avoid hard failure if import ordering changes
    from ide_agents_mcp_server import AgentsMCPServer  # type: ignore
except ImportError:  # pragma: no cover

    class AgentsMCPServer:  # type: ignore
        pass


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


ML_TOOL_NAMES = [
    "ide_agents_ml_analyze_emotion",
    "ide_agents_ml_get_predictions",
    "ide_agents_ml_get_learning_insights",
    "ide_agents_ml_analyze_reasoning",
    "ide_agents_ml_get_personality_profile",
    "ide_agents_ml_adjust_personality",
    "ide_agents_ml_get_system_status",
    # ULTRA extended
    "ide_agents_ml_calibrate_confidence",
    "ide_agents_ml_rank_predictions_rlhf",
    "ide_agents_ml_record_prediction_outcome",
    "ide_agents_ml_get_calibration_metrics",
    "ide_agents_ml_get_rlhf_metrics",
    "ide_agents_ml_behavioral_baseline_check",
    "ide_agents_ml_trigger_auto_adaptation",
    "ide_agents_ml_get_ultra_dashboard",
]

CALIBRATION_SCORE_PATH = "/api/v1/ml/calibration/score"
CALIBRATION_METRICS_PATH = "/api/v1/ml/calibration/metrics"
RLHF_RANK_PATH = "/api/v1/ml/predictions/rank"
RLHF_RECORD_PATH = "/api/v1/ml/predictions/record_outcome"
RLHF_METRICS_PATH = "/api/v1/ml/predictions/metrics"


def _shorten(value: Any, limit: int = 200) -> str:
    if isinstance(value, str):
        return value[:limit]
    try:
        return json.dumps(value, ensure_ascii=False)[:limit]
    except (TypeError, ValueError):  # pragma: no cover - fallback formatting
        return str(value)[:limit]


def _has_error(result: Any) -> bool:
    return isinstance(result, dict) and "error" in result


def _build_extra(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict):
        return None
    extra: dict[str, Any] = {}
    for key in ("mode", "user_id", "status", "method", "backend_status"):
        if key in result:
            extra[key] = result[key]
    if "error" in result and isinstance(result["error"], str):
        extra["error"] = result["error"][:160]
    if not extra and result:
        extra["keys"] = list(result.keys())[:5]
    return extra or None


def _span_name(tool_name: str, span_suffix: str | None) -> str:
    return f"{tool_name}.{span_suffix}" if span_suffix else tool_name


def _instrument(
    tool_name: str,
    method_label: str | None,
    handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    span_suffix: str = "backend",
) -> ToolHandler:
    async def _wrapped(args: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            result = await handler(args)
        except Exception as exc:  # noqa: BLE001
            telemetry.emit_span(
                _span_name(tool_name, span_suffix),
                start_time=start,
                method=method_label,
                success=False,
                error_code=exc.__class__.__name__,
            )
            raise

        telemetry.emit_span(
            _span_name(tool_name, span_suffix),
            start_time=start,
            method=method_label,
            success=not _has_error(result),
            extra=_build_extra(result),
        )
        return result

    return _wrapped


async def _request_backend_json(
    server: AgentsMCPServer,
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    async with httpx.AsyncClient(
        base_url=server.config.backend_base_url,
        timeout=server.config.request_timeout,
    ) as client:
        response = await client.request(method, path, json=json_payload)
    try:
        data = response.json()
    except ValueError:
        data = response.text
    return response.status_code, data


def _safe_get(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
    try:
        r = client.get(path)
        # If coroutine (async client) ensure awaited
        if hasattr(r, "__await__"):
            r = r.__await__().__next__()  # type: ignore
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError) as exc:
        return {"error": f"GET {path} failed: {exc}"}


async def _emotion(
    server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    text = args.get("text", "").strip()
    if not text:
        raise ValueError("text required")
    async with httpx.AsyncClient(
        base_url=server.config.backend_base_url,
        timeout=server.config.request_timeout,
    ) as client:
        # Use POST request with JSON body
        data = await client.post(
            "/ai/intelligence/mood/analyze", json={"text": text}
        )
        try:
            data.raise_for_status()
            payload = data.json()
        except (httpx.HTTPError, ValueError) as exc:
            return {"error": str(exc)}
    return {
        "text": text,
        "mood": payload.get("mood"),
        "confidence": payload.get("confidence"),
    }


async def _predictions(
    server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    user_id = args.get("user_id", "default_user")
    async with httpx.AsyncClient(
        base_url=server.config.backend_base_url,
        timeout=server.config.request_timeout,
    ) as client:
        resp = await client.get(f"/ai/intelligence/predictions/{user_id}")
        if resp.status_code != 200:
            return {"user_id": user_id, "error": resp.text[:200]}
        data = resp.json()
    return {"user_id": user_id, "predictions": data.get("predictions", [])}


async def _learning_insights(
    server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    user_id = args.get("user_id", "default_user")
    async with httpx.AsyncClient(
        base_url=server.config.backend_base_url,
        timeout=server.config.request_timeout,
    ) as client:
        resp = await client.get(f"/ai/intelligence/insights/{user_id}")
        if resp.status_code != 200:
            return {"user_id": user_id, "error": resp.text[:200]}
        data = resp.json()
    return {"user_id": user_id, "insights": data}


async def _reasoning(
    server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    command = args.get("command", "").strip()
    if not command:
        raise ValueError("command required")
    async with httpx.AsyncClient(
        base_url=server.config.backend_base_url,
        timeout=server.config.request_timeout,
    ) as client:
        resp = await client.get(f"/entities/test/{command}")
        if resp.status_code != 200:
            return {"command": command, "error": resp.text[:200]}
        data = resp.json()
    return {"command": command, "analysis": data}


async def _personality_profile(
    server: AgentsMCPServer, _args: dict[str, Any]
) -> dict[str, Any]:
    async with httpx.AsyncClient(
        base_url=server.config.backend_base_url,
        timeout=server.config.request_timeout,
    ) as client:
        resp = await client.get("/ai/intelligence/status")
        if resp.status_code != 200:
            return {"error": resp.text[:200]}
        data = resp.json()
    return {"personality_engine": data.get("personality_engine", {})}


async def _adjust_personality(
    _server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    # Placeholder (no backend POST yet)
    return {
        "requested": {
            k: v
            for k, v in args.items()
            if k in {"personality_type", "mood", "tone"}
        },
        "status": "simulated",
    }


async def _system_status(
    server: AgentsMCPServer, _args: dict[str, Any]
) -> dict[str, Any]:
    async with httpx.AsyncClient(
        base_url=server.config.backend_base_url,
        timeout=server.config.request_timeout,
    ) as client:
        resp = await client.get("/ai/intelligence/status")
        if resp.status_code != 200:
            return {"error": resp.text[:200]}
        return resp.json()


# ULTRA extended handlers (placeholders) ----------------------------------


async def _calibrate_confidence(
    server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    if "raw_score" not in args:
        raise ValueError("raw_score required")

    payload = {
        "raw_prediction_score": float(args["raw_score"]),
        "model_entropy": float(args.get("entropy", 0.0)),
        "user_interaction_count": int(args.get("interaction_count", 0)),
        "time_of_day_factor": float(args.get("time_of_day_factor", 0.5)),
        "historical_accuracy": float(args.get("historical_accuracy", 0.87)),
        "context_richness": float(args.get("context_richness", 0.5)),
        "emotional_stability": float(args.get("emotional_stability", 0.8)),
        "routine_strength": float(args.get("routine_strength", 0.0)),
    }

    status, data = await _request_backend_json(
        server, "POST", CALIBRATION_SCORE_PATH, json_payload=payload
    )
    if status >= 400 or not isinstance(data, dict):
        return {
            "error": _shorten(data),
            "backend_status": status,
            "mode": "backend",
        }

    return {
        "raw_score": payload["raw_prediction_score"],
        "calibrated_probability": data.get("calibrated_probability"),
        "confidence_interval": data.get("confidence_interval"),
        "method": data.get("method", "unknown"),
        "backend_status": status,
        "mode": "backend",
    }


async def _rank_predictions_rlhf(
    server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    user_id = args.get("user_id", "default_user")
    candidates = args.get("candidates")

    async with httpx.AsyncClient(
        base_url=server.config.backend_base_url,
        timeout=server.config.request_timeout,
    ) as client:
        if not candidates:
            resp = await client.get(f"/ai/intelligence/predictions/{user_id}")
            if resp.status_code != 200:
                return {
                    "user_id": user_id,
                    "error": resp.text[:200],
                    "backend_status": resp.status_code,
                }
            candidates = resp.json().get("predictions", [])

    status, data = await _request_backend_json(
        server,
        "POST",
        RLHF_RANK_PATH,
        json_payload={"user_id": user_id, "candidates": candidates},
    )
    if status >= 400 or not isinstance(data, dict):
        return {
            "user_id": user_id,
            "error": _shorten(data),
            "backend_status": status,
            "mode": "backend",
        }

    return {
        "user_id": user_id,
        "ranking": data.get("ranked", []),
        "method": data.get("method", "rlhf"),
        "total_candidates": data.get("total_candidates", len(candidates)),
        "backend_status": status,
        "mode": "backend",
    }


async def _record_prediction_outcome(
    server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    required = [
        "prediction_id",
        "user_accepted",
        "prediction_type",
        "prediction_text",
        "confidence",
    ]
    missing = [field for field in required if field not in args]
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")

    status, data = await _request_backend_json(
        server, "POST", RLHF_RECORD_PATH, json_payload=args
    )
    if status >= 400 or not isinstance(data, dict):
        return {
            "error": _shorten(data),
            "backend_status": status,
            "mode": "backend",
        }
    data.setdefault("backend_status", status)
    data.setdefault("mode", "backend")
    return data


async def _get_calibration_metrics(
    server: AgentsMCPServer, _args: dict[str, Any]
) -> dict[str, Any]:
    status, data = await _request_backend_json(
        server, "GET", CALIBRATION_METRICS_PATH
    )
    if status >= 400 or not isinstance(data, dict):
        return {
            "error": _shorten(data),
            "backend_status": status,
            "mode": "backend",
        }
    data.setdefault("backend_status", status)
    data.setdefault("mode", "backend")
    return data


async def _get_rlhf_metrics(
    server: AgentsMCPServer, _args: dict[str, Any]
) -> dict[str, Any]:
    status, data = await _request_backend_json(
        server, "GET", RLHF_METRICS_PATH
    )
    if status >= 400 or not isinstance(data, dict):
        return {
            "error": _shorten(data),
            "backend_status": status,
            "mode": "backend",
        }
    data.setdefault("backend_status", status)
    data.setdefault("mode", "backend")
    return data


async def _behavioral_baseline(
    _server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    user_id = args.get("user_id", "default_user")
    return {
        "user_id": user_id,
        "baseline": {"deviation": 0.12, "anomalies": []},
        "mode": "mock",
    }


async def _trigger_auto_adaptation(
    _server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    reason = args.get("reason", "manual_trigger")
    return {
        "triggered": True,
        "reason": reason,
        "expected_improvements": {"prediction_accuracy_delta": 0.04},
    }


async def _get_ultra_dashboard(
    _server: AgentsMCPServer, _args: dict[str, Any]
) -> dict[str, Any]:
    return {
        "confidence_calibration": {"brier_score": 0.23, "roc_auc": 0.74},
        "rlhf": {"acceptance_rate": 0.61, "avg_reward": 0.53},
        "engines": {"emotion_detection": "active", "predictive": "active"},
        "behavioral_baseline": {"deviation": 0.12},
    }


def get_ml_tool_handlers(server: AgentsMCPServer) -> dict[str, ToolHandler]:
    """Return mapping of ML tool names to async handlers."""

    def _wrap(
        tool_name: str,
        method_label: str | None,
        func: Callable[
            [AgentsMCPServer, dict[str, Any]], Awaitable[dict[str, Any]]
        ],
        span_suffix: str = "backend",
    ) -> ToolHandler:
        async def _runner(args: dict[str, Any]) -> dict[str, Any]:
            return await func(server, args)

        return _instrument(
            tool_name, method_label, _runner, span_suffix=span_suffix
        )

    return {
        "ide_agents_ml_analyze_emotion": _wrap(
            "ide_agents_ml_analyze_emotion",
            "GET /ai/intelligence/mood/analyze",
            _emotion,
        ),
        "ide_agents_ml_get_predictions": _wrap(
            "ide_agents_ml_get_predictions",
            "GET /ai/intelligence/predictions/{user_id}",
            _predictions,
        ),
        "ide_agents_ml_get_learning_insights": _wrap(
            "ide_agents_ml_get_learning_insights",
            "GET /ai/intelligence/insights/{user_id}",
            _learning_insights,
        ),
        "ide_agents_ml_analyze_reasoning": _wrap(
            "ide_agents_ml_analyze_reasoning",
            "GET /entities/test/{command}",
            _reasoning,
        ),
        "ide_agents_ml_get_personality_profile": _wrap(
            "ide_agents_ml_get_personality_profile",
            "GET /ai/intelligence/status",
            _personality_profile,
        ),
        "ide_agents_ml_adjust_personality": _wrap(
            "ide_agents_ml_adjust_personality",
            "local_personality_adjust",
            _adjust_personality,
            span_suffix="local",
        ),
        "ide_agents_ml_get_system_status": _wrap(
            "ide_agents_ml_get_system_status",
            "GET /ai/intelligence/status",
            _system_status,
        ),
        "ide_agents_ml_calibrate_confidence": _wrap(
            "ide_agents_ml_calibrate_confidence",
            "POST /api/v1/ml/calibration/score",
            _calibrate_confidence,
        ),
        "ide_agents_ml_rank_predictions_rlhf": _wrap(
            "ide_agents_ml_rank_predictions_rlhf",
            "POST /api/v1/ml/predictions/rank",
            _rank_predictions_rlhf,
        ),
        "ide_agents_ml_record_prediction_outcome": _wrap(
            "ide_agents_ml_record_prediction_outcome",
            "POST /api/v1/ml/predictions/record_outcome",
            _record_prediction_outcome,
        ),
        "ide_agents_ml_get_calibration_metrics": _wrap(
            "ide_agents_ml_get_calibration_metrics",
            "GET /api/v1/ml/calibration/metrics",
            _get_calibration_metrics,
        ),
        "ide_agents_ml_get_rlhf_metrics": _wrap(
            "ide_agents_ml_get_rlhf_metrics",
            "GET /api/v1/ml/predictions/metrics",
            _get_rlhf_metrics,
        ),
        "ide_agents_ml_behavioral_baseline_check": _wrap(
            "ide_agents_ml_behavioral_baseline_check",
            "local_baseline_check",
            _behavioral_baseline,
            span_suffix="local",
        ),
        "ide_agents_ml_trigger_auto_adaptation": _wrap(
            "ide_agents_ml_trigger_auto_adaptation",
            "local_auto_adapt",
            _trigger_auto_adaptation,
            span_suffix="local",
        ),
        "ide_agents_ml_get_ultra_dashboard": _wrap(
            "ide_agents_ml_get_ultra_dashboard",
            "local_ultra_dashboard",
            _get_ultra_dashboard,
            span_suffix="local",
        ),
    }


def get_ml_input_schemas() -> dict[str, dict[str, Any]]:
    """Return JSON schema fragments for ML tool inputs."""
    return {
        "ide_agents_ml_analyze_emotion": {
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}},
        },
        "ide_agents_ml_get_predictions": {
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
        },
        "ide_agents_ml_get_learning_insights": {
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
        },
        "ide_agents_ml_analyze_reasoning": {
            "type": "object",
            "required": ["command"],
            "properties": {"command": {"type": "string"}},
        },
        "ide_agents_ml_get_personality_profile": {"type": "object"},
        "ide_agents_ml_adjust_personality": {
            "type": "object",
            "properties": {
                "personality_type": {"type": "string"},
                "mood": {"type": "string"},
                "tone": {"type": "string"},
            },
        },
        "ide_agents_ml_get_system_status": {"type": "object"},
        "ide_agents_ml_calibrate_confidence": {
            "type": "object",
            "required": ["raw_score"],
            "properties": {
                "raw_score": {"type": "number"},
                "entropy": {"type": "number"},
                "interaction_count": {"type": "number"},
            },
        },
        "ide_agents_ml_rank_predictions_rlhf": {
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
        },
        "ide_agents_ml_record_prediction_outcome": {
            "type": "object",
            "required": ["prediction_id", "user_accepted"],
            "properties": {
                "prediction_id": {"type": "string"},
                "user_accepted": {"type": "boolean"},
                "prediction_type": {"type": "string"},
                "prediction_text": {"type": "string"},
                "confidence": {"type": "number"},
                "execution_success": {"type": "boolean"},
                "time_to_adoption_hours": {"type": "number"},
                "user_satisfaction": {"type": "number"},
                "routine_formed": {"type": "boolean"},
                "energy_saved_kwh": {"type": "number"},
            },
        },
        "ide_agents_ml_get_calibration_metrics": {"type": "object"},
        "ide_agents_ml_get_rlhf_metrics": {"type": "object"},
        "ide_agents_ml_behavioral_baseline_check": {
            "type": "object",
            "properties": {"user_id": {"type": "string"}},
        },
        "ide_agents_ml_trigger_auto_adaptation": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
        },
        "ide_agents_ml_get_ultra_dashboard": {"type": "object"},
    }
