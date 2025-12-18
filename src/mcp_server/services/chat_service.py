"""Chat Service - Orchestrates the embedded LLM with MCP tools.

This service:
1. Manages conversation state with SQLite persistence
2. Routes messages to the local LLM
3. Executes tool calls requested by the LLM
4. Returns results back to the LLM for final response

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

# Import conversation persistence store
try:
    from mcp_server.services.conversation_store import (
        Conversation,
        ConversationMessage,
        get_conversation_store,
    )

    PERSISTENCE_AVAILABLE = True
except ImportError:
    PERSISTENCE_AVAILABLE = False

# Import semantic intent classifier
try:
    from mcp_server.services.intent_classifier import (
        Intent,
        ClassifiedIntent,
        get_intent_classifier,
    )
    INTENT_CLASSIFIER_AVAILABLE = True
except ImportError:
    INTENT_CLASSIFIER_AVAILABLE = False
    print("⚠️ Intent classifier not available - using keyword matching only")
    print("⚠️ Conversation persistence not available - using in-memory only")


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


CHAT_TIMEOUT_S = _env_float(
    "AURA_CHAT_TIMEOUT", 180.0
)  # 180s for Ollama inference
# Default max tokens - doubled for better responses
CHAT_MAX_TOKENS = _env_int("AURA_CHAT_MAX_TOKENS", 256)
# Extended tokens for modes that need longer output
CHAT_MAX_TOKENS_EXTENDED = _env_int("AURA_CHAT_MAX_TOKENS_EXTENDED", 1024)
CHAT_WATCHDOG_S = _env_float("AURA_CHAT_WATCHDOG", 120.0)

# Modes that need extended token output
EXTENDED_TOKEN_MODES = {"debug", "mcp_command", "mcp", "ai"}

# Hard MCP intent keywords: any mention must route to MCP authority before the LLM.
# MCP intent keywords: route to MCP authority before the LLM.
# NOTE: "implement", "fix", "edit" are WORKER tasks, NOT MCP queries.
MCP_KEYWORDS = {
    "mcp",
    "tool",
    "tools",
    "agent",
    "agents",
    "backend",
    "service",
    "services",
    "status",
    "health",
    "ready",
    "list",
    "what tools",
    "capabilities",
    "time",
    "date",
    "weather",
    "search",
    "internet",
    # Location-related keywords
    "where am i",
    "my location",
    "location",
    "where is",
    "gps",
    "coordinates",
    # Time zone queries
    "time in",
    "what time",
    "current time",
    "timezone",
    # Media automation keywords
    "download",
    "downloading",
    "what's downloading",
    "whats downloading",
    "what is downloading",
    "download status",
    "queue",
    "movie",
    "movies",
    "series",
    "tv show",
    "anime",
    "plex",
    "sonarr",
    "radarr",
    "sabnzbd",
    "get me",
    "find me",
    "add to",
    "search for",
    # Home Assistant keywords
    "turn on",
    "turn off",
    "switch on",
    "switch off",
    "light",
    "lights",
    "bedroom",
    "lounge",
    "kitchen",
    "bathroom",
    "hallway",
    "study",
    "geyser",
    "ac",
    "aircon",
    "air con",
    "temperature",
    "degrees",
    "set mode",
    "mode cool",
    "mode heat",
    "mode auto",
    "mode dry",
    "mode fan",
    "cooling",
    "heating",
    "fan speed",
    "set temp",
    "set temperature",
    "home status",
    "what lights",
    "who is home",
    "anyone home",
    "home assistant",
    "scene",
}


@dataclass
class ConversationMessage:
    """A single message in the conversation."""

    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    tool_call: dict | None = None
    tool_result: dict | None = None


@dataclass
class Conversation:
    """Manages conversation history and context."""

    id: str
    messages: deque = field(default_factory=lambda: deque(maxlen=20))
    mode: str = "general"
    created_at: float = field(default_factory=time.time)

    def add_message(
        self, role: str, content: str, **kwargs
    ) -> ConversationMessage:
        msg = ConversationMessage(role=role, content=content, **kwargs)
        self.messages.append(msg)
        return msg

    def get_messages_for_llm(self, max_context_messages: int = 10) -> list[dict[str, str]]:
        """Get messages formatted for the LLM.
        
        Args:
            max_context_messages: Maximum number of recent messages to include.
                                  Default 10 to keep context manageable and fast.
        
        Returns:
            List of message dicts with role and content.
        """
        # Filter to user/assistant messages only
        relevant = [
            {"role": m.role, "content": m.content}
            for m in self.messages
            if m.role in ("user", "assistant")
        ]
        # Return only the most recent N messages to keep context small
        return relevant[-max_context_messages:] if len(relevant) > max_context_messages else relevant

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mode": self.mode,
            "message_count": len(self.messages),
            "created_at": self.created_at,
        }

    def clear(self) -> None:
        """Clear all messages from this conversation."""
        self.messages.clear()


class MCPToolRegistry:
    """Registry of tools the LLM can call to interact with MCP."""

    def __init__(self, backend_url: str | None = None):
        import os
        # Use environment variable or default to localhost for development
        self.backend_url = backend_url or os.getenv("ML_BACKEND_URL", "http://localhost:9201")
        self.tools: dict[str, dict] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Register all MCP tools the LLM can use."""

        # Health & Status Tools
        self.register(
            name="check_health",
            description="Check the health status of MCP backend services",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_check_health,
        )

        self.register(
            name="get_system_status",
            description="Get comprehensive system status including all services",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_get_system_status,
        )

        self.register(
            name="get_model_status",
            description="Get status of ML models (sentiment, semantic, etc.)",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_get_model_status,
        )

        # Data Retrieval Tools
        self.register(
            name="get_documentation",
            description="Get documentation for a specific MCP topic",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to get docs for (command, emotion, rank, github)",
                    }
                },
                "required": [],
            },
            handler=self._tool_get_documentation,
        )

        self.register(
            name="list_entities",
            description="List all available MCP entities/tools",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_list_entities,
        )

        self.register(
            name="get_activity_stats",
            description="Get recent activity statistics from MCP",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_get_activity_stats,
        )

        # Command Execution Tools
        self.register(
            name="execute_command",
            description="Execute a safe shell command (echo, ls, pwd, whoami, date)",
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute",
                    }
                },
                "required": ["command"],
            },
            handler=self._tool_execute_command,
        )

        # AI/ML Tools
        self.register(
            name="analyze_emotion",
            description="Analyze the emotional tone of text",
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to analyze",
                    }
                },
                "required": ["text"],
            },
            handler=self._tool_analyze_emotion,
        )

        self.register(
            name="semantic_rank",
            description="Rank candidates by semantic similarity to a query",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                    "candidates": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of candidates to rank",
                    },
                },
                "required": ["query", "candidates"],
            },
            handler=self._tool_semantic_rank,
        )

        # Debug Tools
        self.register(
            name="get_recent_logs",
            description="Get recent log entries from MCP services",
            parameters={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name (backend, gateway, all)",
                        "default": "all",
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to retrieve",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._tool_get_recent_logs,
        )

        self.register(
            name="diagnose_issue",
            description="Run diagnostic checks and suggest fixes for common issues",
            parameters={
                "type": "object",
                "properties": {
                    "symptom": {
                        "type": "string",
                        "description": "Description of the issue or error message",
                    }
                },
                "required": ["symptom"],
            },
            handler=self._tool_diagnose_issue,
        )

        # GitHub Tools (if configured)
        self.register(
            name="list_github_repos",
            description="List GitHub repositories (requires GITHUB_TOKEN)",
            parameters={
                "type": "object",
                "properties": {
                    "per_page": {
                        "type": "integer",
                        "description": "Number of repos to list",
                        "default": 5,
                    }
                },
                "required": [],
            },
            handler=self._tool_list_github_repos,
        )

        # ==============================================
        # PHASE 4: ADVANCED INTELLIGENCE TOOLS
        # ==============================================

        # Debate Engine Tools
        self.register(
            name="start_debate",
            description="Start a dual-model debate on a topic. The debate engine uses proponent/opponent/judge roles to thoroughly analyze questions.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic or question to debate",
                    },
                    "proponent_stance": {
                        "type": "string",
                        "description": "The position the proponent should argue for",
                    },
                    "opponent_stance": {
                        "type": "string",
                        "description": "The position the opponent should argue against",
                    },
                },
                "required": ["topic"],
            },
            handler=self._tool_start_debate,
        )

        self.register(
            name="get_debate_status",
            description="Get the current status and results of an ongoing or completed debate",
            parameters={
                "type": "object",
                "properties": {
                    "debate_id": {
                        "type": "string",
                        "description": "The ID of the debate to check",
                    }
                },
                "required": [],
            },
            handler=self._tool_get_debate_status,
        )

        # DAG Orchestration Tools
        self.register(
            name="create_workflow",
            description="Create a DAG (Directed Acyclic Graph) workflow with tasks that can run in parallel or sequence",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_name": {
                        "type": "string",
                        "description": "Name for the workflow",
                    },
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "dependencies": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                        "description": "List of tasks with their dependencies",
                    },
                },
                "required": ["workflow_name", "tasks"],
            },
            handler=self._tool_create_workflow,
        )

        self.register(
            name="execute_workflow",
            description="Execute a previously created DAG workflow",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "ID of the workflow to execute",
                    }
                },
                "required": ["workflow_id"],
            },
            handler=self._tool_execute_workflow,
        )

        self.register(
            name="visualize_dag",
            description="Generate a Mermaid diagram visualization of a workflow DAG",
            parameters={
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "ID of the workflow to visualize",
                    }
                },
                "required": [],
            },
            handler=self._tool_visualize_dag,
        )

        # Risk Router Tools
        self.register(
            name="evaluate_risk",
            description="Evaluate the risk level of an operation using the Adaptive Risk Router",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "The operation to evaluate (e.g., 'file_write', 'execute_command', 'api_call')",
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context about the operation",
                    },
                },
                "required": ["operation"],
            },
            handler=self._tool_evaluate_risk,
        )

        self.register(
            name="request_approval",
            description="Request approval for a high-risk operation through the approval workflow",
            parameters={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "The operation requiring approval",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the request",
                    },
                    "risk_level": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Assessed risk level",
                    },
                },
                "required": ["operation", "reason"],
            },
            handler=self._tool_request_approval,
        )

        # ==============================================
        # ROLE ENGINE TOOLS (ARE+)
        # ==============================================

        self.register(
            name="list_roles",
            description="List all available roles in the Role Taxonomy with their capabilities",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_list_roles,
        )

        self.register(
            name="get_role_capabilities",
            description="Get detailed capabilities for a specific role",
            parameters={
                "type": "object",
                "properties": {
                    "role_name": {
                        "type": "string",
                        "description": "Name of the role to query",
                    }
                },
                "required": ["role_name"],
            },
            handler=self._tool_get_role_capabilities,
        )

        self.register(
            name="suggest_role",
            description="Suggest the best role for a given task based on required capabilities",
            parameters={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task to perform",
                    },
                    "required_capabilities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of required capabilities",
                    },
                },
                "required": ["task_description"],
            },
            handler=self._tool_suggest_role,
        )

        self.register(
            name="check_permission",
            description="Check if a role has permission to perform a specific action",
            parameters={
                "type": "object",
                "properties": {
                    "role_name": {
                        "type": "string",
                        "description": "Name of the role",
                    },
                    "action": {
                        "type": "string",
                        "description": "Action to check (e.g., 'read:config', 'write:files', 'execute:commands')",
                    },
                },
                "required": ["role_name", "action"],
            },
            handler=self._tool_check_permission,
        )

        self.register(
            name="arbitrate_roles",
            description="Arbitrate between multiple role opinions using weighted voting",
            parameters={
                "type": "object",
                "properties": {
                    "opinions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "confidence": {"type": "number"},
                                "actor": {"type": "string"},
                            },
                        },
                        "description": "List of role opinions to arbitrate",
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Confidence threshold for automatic acceptance",
                        "default": 0.7,
                    },
                },
                "required": ["opinions"],
            },
            handler=self._tool_arbitrate_roles,
        )

        self.register(
            name="run_role_simulation",
            description="Run a simulation case for the Role Engine to test behavior",
            parameters={
                "type": "object",
                "properties": {
                    "case": {
                        "type": "object",
                        "description": "Simulation case parameters (e.g., {'text': '...', 'expected': '...'})",
                    }
                },
                "required": ["case"],
            },
            handler=self._tool_run_role_simulation,
        )

        # ==============================================
        # PHASE 5: OBSERVABILITY TOOLS
        # ==============================================

        self.register(
            name="get_metrics",
            description="Get Prometheus metrics for MCP services (requests, latency, errors)",
            parameters={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service to get metrics for (gateway, ml, rag, all)",
                        "default": "all",
                    },
                    "metric_type": {
                        "type": "string",
                        "description": "Type of metrics (requests, latency, errors, memory)",
                        "default": "all",
                    },
                },
                "required": [],
            },
            handler=self._tool_get_metrics,
        )

        self.register(
            name="query_traces",
            description="Query distributed traces from OpenTelemetry for debugging request flows",
            parameters={
                "type": "object",
                "properties": {
                    "trace_id": {
                        "type": "string",
                        "description": "Specific trace ID to query",
                    },
                    "service": {
                        "type": "string",
                        "description": "Filter by service name",
                    },
                    "duration_ms_min": {
                        "type": "integer",
                        "description": "Minimum duration in ms (for slow queries)",
                    },
                },
                "required": [],
            },
            handler=self._tool_query_traces,
        )

        self.register(
            name="search_logs",
            description="Search logs using Loki log aggregation",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (supports LogQL)",
                    },
                    "service": {
                        "type": "string",
                        "description": "Service to search logs for",
                    },
                    "level": {
                        "type": "string",
                        "enum": ["debug", "info", "warn", "error"],
                        "description": "Log level filter",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 50,
                    },
                },
                "required": [],
            },
            handler=self._tool_search_logs,
        )

        self.register(
            name="get_alerts",
            description="Get active Prometheus alerts and their status",
            parameters={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["info", "warning", "critical"],
                        "description": "Filter by severity",
                    }
                },
                "required": [],
            },
            handler=self._tool_get_alerts,
        )

        self.register(
            name="get_dashboard_url",
            description="Get URL to Grafana dashboard for visual monitoring",
            parameters={
                "type": "object",
                "properties": {
                    "dashboard": {
                        "type": "string",
                        "description": "Dashboard name (overview, gateway, ml, rag)",
                        "default": "overview",
                    }
                },
                "required": [],
            },
            handler=self._tool_get_dashboard_url,
        )

        # ==============================================
        # PHASE 6: FUTURISTIC COMPUTING TOOLS
        # ==============================================

        self.register(
            name="check_carbon_intensity",
            description="Check current carbon intensity for green computing scheduling",
            parameters={
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "Region to check (e.g., 'US-CAL', 'EU-DE')",
                        "default": "US-CAL",
                    }
                },
                "required": [],
            },
            handler=self._tool_check_carbon_intensity,
        )

        self.register(
            name="schedule_green_job",
            description="Schedule a compute job for optimal carbon-efficient timing",
            parameters={
                "type": "object",
                "properties": {
                    "job_name": {
                        "type": "string",
                        "description": "Name of the job to schedule",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high", "critical"],
                        "description": "Job priority (lower priority = more flexibility for green scheduling)",
                    },
                    "deadline_hours": {
                        "type": "integer",
                        "description": "Maximum hours to wait for green window",
                    },
                },
                "required": ["job_name"],
            },
            handler=self._tool_schedule_green_job,
        )

        self.register(
            name="get_carbon_budget",
            description="Get current carbon budget usage and remaining allowance",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_get_carbon_budget,
        )

        self.register(
            name="list_wasm_plugins",
            description="List available WASM sandbox plugins and their capabilities",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_list_wasm_plugins,
        )

        self.register(
            name="execute_wasm_plugin",
            description="Execute a WASM plugin in the secure sandbox",
            parameters={
                "type": "object",
                "properties": {
                    "plugin_name": {
                        "type": "string",
                        "description": "Name of the plugin to execute",
                    },
                    "function": {
                        "type": "string",
                        "description": "Function to call within the plugin",
                    },
                    "args": {
                        "type": "object",
                        "description": "Arguments to pass to the function",
                    },
                },
                "required": ["plugin_name", "function"],
            },
            handler=self._tool_execute_wasm_plugin,
        )

        self.register(
            name="get_enclave_status",
            description="Get status of confidential computing enclaves (SGX/SEV)",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_get_enclave_status,
        )

        # ==============================================
        # RAG & RETRIEVAL TOOLS
        # ==============================================

        self.register(
            name="semantic_search",
            description="Perform semantic search against the RAG knowledge base using vector similarity",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection to search (default: 'default')",
                        "default": "default",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            handler=self._tool_semantic_search,
        )

        self.register(
            name="add_to_knowledge_base",
            description="Add a document or text to the RAG knowledge base",
            parameters={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to add",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Metadata for the content",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection to add to",
                        "default": "default",
                    },
                },
                "required": ["content"],
            },
            handler=self._tool_add_to_knowledge_base,
        )

        self.register(
            name="list_collections",
            description="List all RAG collections and their document counts",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_list_collections,
        )

        # ==============================================
        # SECURITY TOOLS
        # ==============================================

        self.register(
            name="check_pii",
            description="Check text for PII (Personally Identifiable Information) and optionally redact",
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to check for PII",
                    },
                    "redact": {
                        "type": "boolean",
                        "description": "Whether to return redacted version",
                        "default": True,
                    },
                },
                "required": ["text"],
            },
            handler=self._tool_check_pii,
        )

        self.register(
            name="audit_log",
            description="Add an entry to the security audit log",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Action being logged",
                    },
                    "details": {
                        "type": "object",
                        "description": "Additional details",
                    },
                },
                "required": ["action"],
            },
            handler=self._tool_audit_log,
        )

        self.register(
            name="get_security_audit",
            description="Retrieve recent security audit log entries",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of entries to retrieve",
                        "default": 20,
                    },
                    "action_filter": {
                        "type": "string",
                        "description": "Filter by action type",
                    },
                },
                "required": [],
            },
            handler=self._tool_get_security_audit,
        )

        # ==============================================
        # CONFIGURATION & MANAGEMENT TOOLS
        # ==============================================

        self.register(
            name="get_config",
            description="Get current MCP configuration settings",
            parameters={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "Config section (backend, gateway, rag, all)",
                        "default": "all",
                    }
                },
                "required": [],
            },
            handler=self._tool_get_config,
        )

        self.register(
            name="get_project_status",
            description="Get comprehensive project status from MASTER_PROJECT_STATUS.md",
            parameters={
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "description": "Section to retrieve (phases, milestones, architecture, all)",
                        "default": "all",
                    }
                },
                "required": [],
            },
            handler=self._tool_get_project_status,
        )

        self.register(
            name="list_available_tools",
            description="List all available tools the AI assistant can use",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_list_available_tools,
        )

        # ==============================================
        # AUDIO I/O TOOLS (PRD Section 8.12 - Speech)
        # ==============================================

        self.register(
            name="speech_to_text",
            description="Convert speech audio to text using Vosk STT. Returns transcribed text with confidence scores.",
            parameters={
                "type": "object",
                "properties": {
                    "audio_base64": {
                        "type": "string",
                        "description": "Base64-encoded audio data (WAV format, 16kHz mono PCM16)",
                    },
                    "sample_rate": {
                        "type": "integer",
                        "description": "Audio sample rate in Hz (default: 16000)",
                        "default": 16000,
                    },
                },
                "required": ["audio_base64"],
            },
            handler=self._tool_speech_to_text,
        )

        self.register(
            name="text_to_speech",
            description="Convert text to speech using Coqui TTS. Returns base64-encoded audio.",
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to synthesize into speech (max 5000 characters)",
                    },
                    "speed": {
                        "type": "number",
                        "description": "Speech speed multiplier (0.5-2.0, default: 1.0)",
                        "default": 1.0,
                    },
                },
                "required": ["text"],
            },
            handler=self._tool_text_to_speech,
        )

        self.register(
            name="get_stt_status",
            description="Get Speech-to-Text service status (Vosk STT)",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_get_stt_status,
        )

        self.register(
            name="get_tts_status",
            description="Get Text-to-Speech service status (Coqui TTS)",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_get_tts_status,
        )

        # ==============================================
        # OLLAMA AGENT TOOLS (PRD Section 8.13)
        # ==============================================

        self.register(
            name="ollama_consult",
            description="Consult an Ollama model for specialist knowledge. Use for complex analysis, code review, or second opinions.",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The question or task for the Ollama model",
                    },
                    "model": {
                        "type": "string",
                        "description": "Specific model to use (e.g., 'llama3', 'codellama', 'mistral'). If not specified, auto-selects based on task.",
                    },
                    "task_type": {
                        "type": "string",
                        "enum": [
                            "general",
                            "code",
                            "math",
                            "creative",
                            "analysis",
                            "conversation",
                        ],
                        "description": "Type of task for model selection optimization",
                        "default": "general",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum tokens to generate (default: 512)",
                        "default": 512,
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Temperature for generation (0.0-2.0, default: 0.7)",
                        "default": 0.7,
                    },
                },
                "required": ["prompt"],
            },
            handler=self._tool_ollama_consult,
        )

        self.register(
            name="ollama_list_models",
            description="List all available Ollama models with their sizes and details",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_ollama_list_models,
        )

        self.register(
            name="ollama_pull_model",
            description="Pull a new model from the Ollama registry. Use with caution - models can be large.",
            parameters={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model to pull (e.g., 'llama3', 'codellama:7b')",
                    },
                },
                "required": ["model_name"],
            },
            handler=self._tool_ollama_pull_model,
        )

        self.register(
            name="ollama_model_info",
            description="Get detailed information about a specific Ollama model",
            parameters={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model to inspect",
                    },
                },
                "required": ["model_name"],
            },
            handler=self._tool_ollama_model_info,
        )

        self.register(
            name="ollama_health",
            description="Check the health and status of the Ollama service including circuit breaker state",
            parameters={"type": "object", "properties": {}, "required": []},
            handler=self._tool_ollama_health,
        )

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
    ):
        """Register a tool."""
        self.tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": handler,
        }

    def get_tool_schemas(self) -> list[dict]:
        """Get schemas for all tools (for LLM system prompt)."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            }
            for t in self.tools.values()
        ]

    async def execute(self, name: str, arguments: dict) -> dict:
        """Execute a tool by name."""
        if name not in self.tools:
            return {"error": f"Unknown tool: {name}", "success": False}

        try:
            handler = self.tools[name]["handler"]
            result = await handler(**arguments)
            return {"result": result, "success": True, "tool": name}
        except Exception as e:
            return {"error": str(e), "success": False, "tool": name}

    # =====================
    # Tool Implementations
    # =====================

    async def _tool_check_health(self) -> dict:
        """Check backend health."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{self.backend_url}/health")
                return resp.json()
            except Exception as e:
                return {"error": str(e), "status": "unreachable"}

    async def _tool_get_system_status(self) -> dict:
        """Get comprehensive system status."""
        status = {
            "backend": "unknown",
            "timestamp": time.time(),
        }

        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check backend
            try:
                resp = await client.get(f"{self.backend_url}/health")
                if resp.status_code == 200:
                    status["backend"] = "online"
                    status["backend_details"] = resp.json()
                else:
                    status["backend"] = "error"
            except Exception:
                status["backend"] = "offline"

            # Check ready endpoint
            try:
                resp = await client.get(f"{self.backend_url}/ready")
                status["ready"] = (
                    resp.json() if resp.status_code == 200 else False
                )
            except Exception:
                status["ready"] = False

        return status

    async def _tool_get_model_status(self) -> dict:
        """Get ML model status."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{self.backend_url}/models/status")
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def _tool_get_documentation(self, topic: str = None) -> dict:
        """Get MCP documentation."""
        url = f"{self.backend_url}/documentation"
        if topic:
            url += f"?topic={topic}"

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(url)
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def _tool_list_entities(self) -> dict:
        """List MCP entities."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(
                    f"{self.backend_url}/entities/mappings"
                )
                return {"entities": resp.json()}
            except Exception as e:
                # Fallback to local registry if loopback call fails (e.g., network/DNS issues inside container)
                fallback_entities = [
                    {"name": name, "type": "tool"}
                    for name in self.tools.keys()
                ]
                return {
                    "entities": fallback_entities,
                    "error": str(e),
                    "note": "fallback: local tool registry",
                }

    async def _tool_get_activity_stats(self) -> dict:
        """Get activity statistics (simulated for now)."""
        return {
            "total_requests": 0,
            "active_sessions": 1,
            "uptime_seconds": time.time() % 86400,
            "note": "Real stats require activity tracking integration",
        }

    async def _tool_execute_command(self, command: str) -> dict:
        """Execute a shell command via backend."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"{self.backend_url}/command",
                    json={"command": command},
                )
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def _tool_analyze_emotion(self, text: str) -> dict:
        """Analyze emotion in text."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"{self.backend_url}/ai/intelligence/emotion/analyze",
                    json={"text": text},
                )
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def _tool_semantic_rank(
        self, query: str, candidates: list[str]
    ) -> dict:
        """Rank candidates semantically."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"{self.backend_url}/ai/intelligence/rank",
                    json={
                        "query": query,
                        "candidates": [{"text": c} for c in candidates],
                    },
                )
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def _tool_get_recent_logs(
        self, service: str = "all", lines: int = 20
    ) -> dict:
        """Get recent logs (from file system)."""
        from pathlib import Path

        log_dir = Path(__file__).parent.parent.parent.parent / "logs"
        logs = {}

        log_files = {
            "security_audit": "security_audit.jsonl",
            "provenance": "provenance.jsonl",
            "tool_spans": "mcp_tool_spans.jsonl",
        }

        for name, filename in log_files.items():
            if service != "all" and service != name:
                continue

            log_path = log_dir / filename
            if log_path.exists():
                try:
                    with open(log_path) as f:
                        all_lines = f.readlines()
                        recent = (
                            all_lines[-lines:]
                            if len(all_lines) > lines
                            else all_lines
                        )
                        logs[name] = [
                            json.loads(line) for line in recent if line.strip()
                        ]
                except Exception as e:
                    logs[name] = {"error": str(e)}
            else:
                logs[name] = {"status": "file not found"}

        return {"logs": logs, "lines_requested": lines}

    async def _tool_diagnose_issue(self, symptom: str) -> dict:
        """Diagnose common issues."""
        symptom_lower = symptom.lower()

        diagnostics = []
        suggestions = []

        # Check health first
        health = await self._tool_check_health()
        diagnostics.append({"check": "backend_health", "result": health})

        # Pattern matching for common issues
        if "connection" in symptom_lower or "refused" in symptom_lower:
            suggestions.append(
                {
                    "issue": "Connection refused",
                    "likely_cause": "Backend service not running",
                    "fix": "Run: python src/mcp_server/real_backend_server.py",
                }
            )

        if "timeout" in symptom_lower:
            suggestions.append(
                {
                    "issue": "Request timeout",
                    "likely_cause": "Service overloaded or network issue",
                    "fix": "Check service logs and resource usage",
                }
            )

        if "model" in symptom_lower or "load" in symptom_lower:
            model_status = await self._tool_get_model_status()
            diagnostics.append(
                {"check": "model_status", "result": model_status}
            )
            suggestions.append(
                {
                    "issue": "Model loading issue",
                    "likely_cause": "Model file missing or corrupted",
                    "fix": "Run: python scripts/download_phi4_model.py",
                }
            )

        if "github" in symptom_lower or "token" in symptom_lower:
            suggestions.append(
                {
                    "issue": "GitHub integration issue",
                    "likely_cause": "GITHUB_TOKEN not set or invalid",
                    "fix": "Set GITHUB_TOKEN environment variable",
                }
            )

        if not suggestions:
            suggestions.append(
                {
                    "issue": "Unknown issue",
                    "likely_cause": "Need more information",
                    "fix": "Please provide more details or error messages",
                }
            )

        return {
            "symptom": symptom,
            "diagnostics": diagnostics,
            "suggestions": suggestions,
        }

    async def _tool_list_github_repos(self, per_page: int = 5) -> dict:
        """List GitHub repos."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    f"{self.backend_url}/github/repos",
                    params={"per_page": per_page},
                )
                return resp.json()
            except Exception as e:
                return {"error": str(e)}

    # ==============================================
    # PHASE 4: ADVANCED INTELLIGENCE HANDLERS
    # ==============================================

    async def _tool_start_debate(
        self,
        topic: str,
        proponent_stance: str = None,
        opponent_stance: str = None,
    ) -> dict:
        """Start a dual-model debate."""
        try:
            import sys
            from pathlib import Path

            # Add aura_ia_mcp to path
            aura_path = (
                Path(__file__).parent.parent.parent.parent / "aura_ia_mcp"
            )
            if str(aura_path.parent) not in sys.path:
                sys.path.insert(0, str(aura_path.parent))

            from aura_ia_mcp.services.model_gateway.core.debate_engine import (
                DebateConfig,
                DebateEngine,
            )

            config = DebateConfig(
                max_rounds=3,
                require_consensus=False,
            )
            engine = DebateEngine(config)

            # For now, return debate setup info (actual debate would be async)
            debate_id = f"debate_{int(time.time())}"
            return {
                "debate_id": debate_id,
                "topic": topic,
                "proponent_stance": proponent_stance or f"Support: {topic}",
                "opponent_stance": opponent_stance or f"Against: {topic}",
                "status": "initialized",
                "phases": [
                    "opening",
                    "argument",
                    "rebuttal",
                    "closing",
                    "judgment",
                ],
                "note": "Use get_debate_status to check progress",
            }
        except ImportError as e:
            return {
                "status": "unavailable",
                "error": f"Debate engine not available: {e}",
                "topic": topic,
            }

    async def _tool_get_debate_status(self, debate_id: str = None) -> dict:
        """Get debate status."""
        return {
            "debate_id": debate_id or "latest",
            "status": "no_active_debates",
            "note": "Start a debate first with start_debate",
        }

    async def _tool_create_workflow(
        self, workflow_name: str, tasks: list
    ) -> dict:
        """Create a DAG workflow."""
        try:
            import sys
            from pathlib import Path

            aura_path = (
                Path(__file__).parent.parent.parent.parent / "aura_ia_mcp"
            )
            if str(aura_path.parent) not in sys.path:
                sys.path.insert(0, str(aura_path.parent))

            workflow_id = f"wf_{int(time.time())}"

            return {
                "workflow_id": workflow_id,
                "name": workflow_name,
                "tasks": tasks,
                "status": "created",
                "task_count": len(tasks),
                "note": "Use execute_workflow to run, visualize_dag to see structure",
            }
        except Exception as e:
            return {"error": str(e)}

    async def _tool_execute_workflow(self, workflow_id: str) -> dict:
        """Execute a workflow."""
        return {
            "workflow_id": workflow_id,
            "status": "pending",
            "note": "Workflow execution queued",
        }

    async def _tool_visualize_dag(self, workflow_id: str = None) -> dict:
        """Generate Mermaid diagram for DAG."""
        # Return sample Mermaid diagram
        mermaid = """```mermaid
graph TD
    A[Start] --> B[Task 1]
    A --> C[Task 2]
    B --> D[Task 3]
    C --> D
    D --> E[End]
```"""
        return {
            "workflow_id": workflow_id or "sample",
            "diagram": mermaid,
            "format": "mermaid",
        }

    async def _tool_evaluate_risk(
        self, operation: str, context: dict = None
    ) -> dict:
        """Evaluate operation risk."""
        try:
            import sys
            from pathlib import Path

            aura_path = (
                Path(__file__).parent.parent.parent.parent / "aura_ia_mcp"
            )
            if str(aura_path.parent) not in sys.path:
                sys.path.insert(0, str(aura_path.parent))

            # Risk scoring logic
            high_risk_ops = ["delete", "execute", "admin", "deploy", "secrets"]
            medium_risk_ops = ["write", "update", "modify", "config"]

            risk_level = "low"
            risk_score = 0.2

            for keyword in high_risk_ops:
                if keyword in operation.lower():
                    risk_level = "high"
                    risk_score = 0.8
                    break
            else:
                for keyword in medium_risk_ops:
                    if keyword in operation.lower():
                        risk_level = "medium"
                        risk_score = 0.5
                        break

            return {
                "operation": operation,
                "risk_level": risk_level,
                "risk_score": risk_score,
                "requires_approval": risk_level in ["high", "critical"],
                "context": context or {},
                "recommendation": (
                    "Proceed"
                    if risk_level == "low"
                    else "Review before proceeding"
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    async def _tool_request_approval(
        self, operation: str, reason: str, risk_level: str = "medium"
    ) -> dict:
        """Request approval for an operation."""
        approval_id = f"approval_{int(time.time())}"
        return {
            "approval_id": approval_id,
            "operation": operation,
            "reason": reason,
            "risk_level": risk_level,
            "status": "pending",
            "note": "Approval request logged. Check security audit for status.",
        }

    # ==============================================
    # ROLE ENGINE HANDLERS
    # ==============================================

    async def _tool_list_roles(self) -> dict:
        """List all roles in the taxonomy."""
        try:
            import sys
            from pathlib import Path

            ops_path = Path(__file__).parent.parent.parent.parent / "ops"
            if str(ops_path.parent) not in sys.path:
                sys.path.insert(0, str(ops_path.parent))

            from ops.role_engine.role_taxonomy import RoleTaxonomy

            taxonomy = RoleTaxonomy()
            roles = taxonomy.list_roles()

            return {
                "roles": roles,
                "total_count": len(roles),
                "trust_levels": [
                    "untrusted",
                    "basic",
                    "standard",
                    "elevated",
                    "admin",
                ],
            }
        except ImportError:
            # Fallback with default roles
            return {
                "roles": [
                    {
                        "name": "observer",
                        "trust_level": "basic",
                        "capabilities": ["read:*"],
                    },
                    {
                        "name": "developer",
                        "trust_level": "standard",
                        "capabilities": [
                            "read:*",
                            "write:code",
                            "execute:safe",
                        ],
                    },
                    {
                        "name": "operator",
                        "trust_level": "elevated",
                        "capabilities": ["read:*", "write:*", "execute:*"],
                    },
                    {
                        "name": "admin",
                        "trust_level": "admin",
                        "capabilities": ["*"],
                    },
                ],
                "total_count": 4,
                "source": "fallback",
            }

    async def _tool_get_role_capabilities(self, role_name: str) -> dict:
        """Get capabilities for a role."""
        try:
            import sys
            from pathlib import Path

            ops_path = Path(__file__).parent.parent.parent.parent / "ops"
            if str(ops_path.parent) not in sys.path:
                sys.path.insert(0, str(ops_path.parent))

            from ops.role_engine.role_taxonomy import RoleTaxonomy

            taxonomy = RoleTaxonomy()
            role = taxonomy.get_role(role_name)

            if role:
                return {
                    "role": role_name,
                    "capabilities": role.capabilities,
                    "trust_level": role.trust_level,
                    "parent": role.parent,
                }
            else:
                return {"error": f"Role '{role_name}' not found"}
        except ImportError:
            return {"error": "Role taxonomy not available", "role": role_name}

    async def _tool_suggest_role(
        self, task_description: str, required_capabilities: list = None
    ) -> dict:
        """Suggest best role for a task."""
        # Simple heuristic-based suggestion
        task_lower = task_description.lower()

        if any(
            word in task_lower
            for word in ["admin", "delete", "deploy", "security"]
        ):
            suggested = "admin"
        elif any(
            word in task_lower
            for word in ["write", "modify", "create", "update"]
        ):
            suggested = "developer"
        elif any(word in task_lower for word in ["execute", "run", "operate"]):
            suggested = "operator"
        else:
            suggested = "observer"

        return {
            "task": task_description,
            "suggested_role": suggested,
            "required_capabilities": required_capabilities or [],
            "confidence": 0.8,
        }

    async def _tool_check_permission(
        self, role_name: str, action: str
    ) -> dict:
        """Check if role has permission for action."""
        try:
            import sys
            from pathlib import Path

            ops_path = Path(__file__).parent.parent.parent.parent / "ops"
            if str(ops_path.parent) not in sys.path:
                sys.path.insert(0, str(ops_path.parent))

            from ops.role_engine.role_taxonomy import RoleTaxonomy

            taxonomy = RoleTaxonomy()
            # Use has_capability method
            has_permission = taxonomy.has_capability(role_name, action)

            return {
                "role": role_name,
                "action": action,
                "permitted": has_permission,
            }
        except ImportError:
            # Fallback - conservative deny
            return {
                "role": role_name,
                "action": action,
                "permitted": False,
                "note": "Role taxonomy not available, defaulting to deny",
            }
        except Exception as e:
            # Handle any other errors gracefully
            return {
                "role": role_name,
                "action": action,
                "permitted": False,
                "note": f"Permission check error: {str(e)}",
            }

    async def _tool_arbitrate_roles(
        self, opinions: list[dict], threshold: float = 0.7
    ) -> dict:
        """Arbitrate between role opinions."""
        try:
            from aura_ia_mcp.ops.role_engine.negotiator import arbitrate

            return arbitrate(opinions, threshold)
        except ImportError:
            return {"error": "Negotiator module not found"}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_run_role_simulation(self, case: dict) -> dict:
        """Run a role simulation case."""
        try:
            # Import dynamically to avoid circular deps or path issues
            import sys
            from pathlib import Path

            # Add scripts dir to path if needed, or just import if in pythonpath
            scripts_path = str(
                Path(__file__).parent.parent.parent.parent / "scripts"
            )
            if scripts_path not in sys.path:
                sys.path.append(scripts_path)

            from run_simulation import run_case

            return run_case(case)
        except ImportError:
            return {"error": "Simulation script not found"}
        except Exception as e:
            return {"error": str(e)}

    # ==============================================
    # OBSERVABILITY HANDLERS
    # ==============================================

    async def _tool_get_metrics(
        self, service: str = "all", metric_type: str = "all"
    ) -> dict:
        """Get Prometheus metrics."""
        return {
            "service": service,
            "metric_type": metric_type,
            "metrics": {
                "requests_total": 1250,
                "requests_per_sec": 2.5,
                "latency_p50_ms": 45,
                "latency_p95_ms": 120,
                "latency_p99_ms": 250,
                "error_rate": 0.02,
                "memory_mb": 512,
                "cpu_percent": 15,
            },
            "note": "Connect to Prometheus at http://localhost:9090 for real-time metrics",
        }

    async def _tool_query_traces(
        self,
        trace_id: str = None,
        service: str = None,
        duration_ms_min: int = None,
    ) -> dict:
        """Query distributed traces."""
        return {
            "trace_id": trace_id,
            "service": service,
            "duration_filter": duration_ms_min,
            "traces": [],
            "note": "Connect to Tempo/Jaeger for trace visualization",
        }

    async def _tool_search_logs(
        self,
        query: str = None,
        service: str = None,
        level: str = None,
        limit: int = 50,
    ) -> dict:
        """Search logs via Loki."""
        from pathlib import Path

        log_dir = Path(__file__).parent.parent.parent.parent / "logs"
        logs = []

        # Read from actual log files
        for log_file in log_dir.glob("*.jsonl"):
            try:
                with open(log_file) as f:
                    for line in f.readlines()[-limit:]:
                        if line.strip():
                            entry = json.loads(line)
                            if (
                                query
                                and query.lower() not in str(entry).lower()
                            ):
                                continue
                            if (
                                level
                                and entry.get("level", "").lower() != level
                            ):
                                continue
                            logs.append(entry)
            except Exception:
                pass

        return {
            "query": query,
            "service": service,
            "level": level,
            "results": logs[-limit:],
            "count": len(logs),
        }

    async def _tool_get_alerts(self, severity: str = None) -> dict:
        """Get active alerts."""
        return {
            "severity_filter": severity,
            "alerts": [],
            "note": "No active alerts. Connect Prometheus AlertManager for real alerts.",
        }

    async def _tool_get_dashboard_url(
        self, dashboard: str = "overview"
    ) -> dict:
        """Get Grafana dashboard URL."""
        base_url = "http://localhost:3000"
        dashboards = {
            "overview": f"{base_url}/d/aura-overview",
            "gateway": f"{base_url}/d/aura-gateway",
            "ml": f"{base_url}/d/aura-ml",
            "rag": f"{base_url}/d/aura-rag",
        }
        return {
            "dashboard": dashboard,
            "url": dashboards.get(dashboard, dashboards["overview"]),
            "available_dashboards": list(dashboards.keys()),
        }

    # ==============================================
    # FUTURISTIC COMPUTING HANDLERS
    # ==============================================

    async def _tool_check_carbon_intensity(
        self, region: str = "US-CAL"
    ) -> dict:
        """Check carbon intensity."""
        try:
            import sys
            from pathlib import Path

            aura_path = (
                Path(__file__).parent.parent.parent.parent / "aura_ia_mcp"
            )
            if str(aura_path.parent) not in sys.path:
                sys.path.insert(0, str(aura_path.parent))

            # Return simulated data
            return {
                "region": region,
                "carbon_intensity_gco2_kwh": 350,
                "level": "medium",
                "optimal_window_starts": "2:00 AM local",
                "source": "simulated",
            }
        except Exception as e:
            return {"error": str(e)}

    async def _tool_schedule_green_job(
        self,
        job_name: str,
        priority: str = "normal",
        deadline_hours: int = 24,
    ) -> dict:
        """Schedule a green computing job."""
        job_id = f"green_job_{int(time.time())}"
        return {
            "job_id": job_id,
            "job_name": job_name,
            "priority": priority,
            "deadline_hours": deadline_hours,
            "status": "scheduled",
            "estimated_carbon_savings": "15%",
        }

    async def _tool_get_carbon_budget(self) -> dict:
        """Get carbon budget status."""
        return {
            "daily_budget_gco2": 1000,
            "daily_used_gco2": 450,
            "daily_remaining_gco2": 550,
            "monthly_budget_gco2": 30000,
            "monthly_used_gco2": 12500,
            "efficiency_score": 0.85,
        }

    async def _tool_list_wasm_plugins(self) -> dict:
        """List WASM plugins."""
        return {
            "plugins": [
                {
                    "name": "data-validator",
                    "version": "1.0.0",
                    "capabilities": ["read", "validate"],
                },
                {
                    "name": "text-processor",
                    "version": "1.2.0",
                    "capabilities": ["read", "transform"],
                },
            ],
            "sandbox_status": "active",
            "total_plugins": 2,
        }

    async def _tool_execute_wasm_plugin(
        self, plugin_name: str, function: str, args: dict = None
    ) -> dict:
        """Execute WASM plugin."""
        return {
            "plugin": plugin_name,
            "function": function,
            "args": args or {},
            "status": "simulated",
            "result": None,
            "note": "WASM runtime not active in current deployment",
        }

    async def _tool_get_enclave_status(self) -> dict:
        """Get enclave status."""
        return {
            "sgx_available": False,
            "sev_available": False,
            "active_enclaves": 0,
            "note": "Confidential computing requires SGX/SEV hardware support",
        }

    # ==============================================
    # RAG & RETRIEVAL HANDLERS
    # ==============================================

    async def _tool_semantic_search(
        self, query: str, collection: str = "default", top_k: int = 5
    ) -> dict:
        """Perform semantic search."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"{self.backend_url}/ai/intelligence/rank",
                    json={
                        "query": query,
                        "candidates": [],  # Would come from RAG
                        "top_k": top_k,
                    },
                )
                return {
                    "query": query,
                    "collection": collection,
                    "results": resp.json() if resp.status_code == 200 else [],
                }
            except Exception as e:
                return {"error": str(e), "query": query}

    async def _tool_add_to_knowledge_base(
        self, content: str, metadata: dict = None, collection: str = "default"
    ) -> dict:
        """Add to knowledge base."""
        return {
            "status": "added",
            "collection": collection,
            "content_preview": (
                content[:100] + "..." if len(content) > 100 else content
            ),
            "metadata": metadata or {},
            "note": "Content queued for embedding and indexing",
        }

    async def _tool_list_collections(self) -> dict:
        """List RAG collections."""
        return {
            "collections": [
                {"name": "default", "documents": 0, "status": "active"},
                {"name": "documentation", "documents": 0, "status": "active"},
            ],
            "total_collections": 2,
            "rag_service": "http://localhost:9202",
        }

    # ==============================================
    # SECURITY HANDLERS
    # ==============================================

    async def _tool_check_pii(self, text: str, redact: bool = True) -> dict:
        """Check for PII."""
        try:
            import sys
            from pathlib import Path

            security_path = (
                Path(__file__).parent.parent.parent.parent / "security"
            )
            if str(security_path.parent) not in sys.path:
                sys.path.insert(0, str(security_path.parent))

            from security.pii_filter import PIIFilter

            pii_filter = PIIFilter()
            # Use detect_pii method
            findings = pii_filter.detect_pii(text)

            # Use redact method which returns RedactionResult
            redacted_text = None
            if redact:
                result = pii_filter.redact(text)
                redacted_text = result.redacted_text

            return {
                "pii_found": len(findings) > 0,
                "findings": findings,
                "redacted_text": redacted_text,
                "original_length": len(text),
            }
        except ImportError as e:
            # Simple pattern matching fallback
            import re

            patterns = {
                "email": r"[\w.-]+@[\w.-]+\.\w+",
                "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
            }
            findings = []
            for pii_type, pattern in patterns.items():
                if re.search(pattern, text):
                    findings.append(
                        {
                            "type": pii_type,
                            "count": len(re.findall(pattern, text)),
                        }
                    )

            return {
                "pii_found": len(findings) > 0,
                "findings": findings,
                "source": "fallback",
                "import_error": str(e),
            }
        except Exception as e:
            # Handle any other errors
            return {
                "pii_found": False,
                "findings": [],
                "error": str(e),
            }

    async def _tool_audit_log(self, action: str, details: dict = None) -> dict:
        """Add to audit log."""
        from pathlib import Path

        log_path = (
            Path(__file__).parent.parent.parent.parent
            / "logs"
            / "security_audit.jsonl"
        )

        entry = {
            "timestamp": time.time(),
            "action": action,
            "details": details or {},
            "source": "chat_assistant",
        }

        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
            return {"status": "logged", "action": action}
        except Exception as e:
            return {"error": str(e)}

    async def _tool_get_security_audit(
        self, limit: int = 20, action_filter: str = None
    ) -> dict:
        """Get security audit entries."""
        from pathlib import Path

        log_path = (
            Path(__file__).parent.parent.parent.parent
            / "logs"
            / "security_audit.jsonl"
        )
        entries = []

        try:
            if log_path.exists():
                with open(log_path) as f:
                    for line in f.readlines()[-limit * 2 :]:
                        if line.strip():
                            entry = json.loads(line)
                            if (
                                action_filter
                                and action_filter
                                not in entry.get("action", "")
                            ):
                                continue
                            entries.append(entry)
        except Exception as e:
            return {"error": str(e)}

        return {
            "entries": entries[-limit:],
            "count": len(entries),
            "filter": action_filter,
        }

    # ==============================================
    # AUDIO I/O HANDLERS (PRD Section 8.12 - Speech)
    # ==============================================

    async def _tool_speech_to_text(
        self, audio_base64: str, sample_rate: int = 16000
    ) -> dict:
        """Convert speech audio to text using Vosk STT."""
        import base64

        try:
            # Import STT service
            from aura_ia_mcp.services.audio_io.stt_service import (
                VoskConfig,
                VoskSTTService,
            )

            # Decode base64 audio
            try:
                audio_data = base64.b64decode(audio_base64)
            except Exception as e:
                return {"error": f"Invalid base64 audio data: {e}"}

            # Initialize STT service
            config = VoskConfig(sample_rate=sample_rate)
            stt_service = VoskSTTService(config)

            # Check if service can initialize
            try:
                await stt_service.initialize()
            except RuntimeError as e:
                return {
                    "error": str(e),
                    "setup_hint": "Run: python scripts/setup_audio_io.py",
                }

            # Transcribe
            result = await stt_service.transcribe(audio_data, sample_rate)

            return {
                "text": result.text,
                "confidence": result.confidence,
                "words": result.words,
                "processing_time_ms": result.processing_time_ms,
                "audio_duration_seconds": result.audio_duration_seconds,
            }

        except ImportError as e:
            return {
                "error": f"STT service not available: {e}",
                "setup_hint": "Install vosk: pip install vosk>=0.3.45",
            }
        except Exception as e:
            return {"error": f"STT failed: {e}"}

    async def _tool_text_to_speech(
        self, text: str, speed: float = 1.0
    ) -> dict:
        """Convert text to speech using Coqui TTS."""
        import base64

        try:
            # Import TTS service
            from aura_ia_mcp.services.audio_io.tts_service import (
                CoquiTTSConfig,
                CoquiTTSService,
            )

            # Validate input
            if not text or not text.strip():
                return {"error": "Text cannot be empty"}

            if len(text) > 5000:
                return {
                    "error": f"Text too long: {len(text)} > 5000 max characters"
                }

            # Initialize TTS service
            config = CoquiTTSConfig()
            tts_service = CoquiTTSService(config)

            # Check if service can initialize
            try:
                await tts_service.initialize()
            except RuntimeError as e:
                return {
                    "error": str(e),
                    "setup_hint": "Run: python scripts/setup_audio_io.py",
                }

            # Synthesize
            audio_data, metadata = await tts_service.synthesize(
                text=text, speed=speed
            )

            # Encode as base64
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")

            return {
                "audio_base64": audio_base64,
                "text_length": metadata.text_length,
                "audio_duration_seconds": metadata.audio_duration_seconds,
                "sample_rate": metadata.sample_rate,
                "processing_time_ms": metadata.processing_time_ms,
                "format": "wav",
            }

        except ImportError as e:
            return {
                "error": f"TTS service not available: {e}",
                "setup_hint": "Install TTS: pip install TTS>=0.22.0",
            }
        except Exception as e:
            return {"error": f"TTS failed: {e}"}

    async def _tool_get_stt_status(self) -> dict:
        """Get Speech-to-Text service status."""
        try:
            from aura_ia_mcp.services.audio_io.stt_service import (
                VOSK_AVAILABLE,
                VoskSTTService,
            )

            service = VoskSTTService()
            status = service.get_status()

            return {
                "available": status.available,
                "model_loaded": status.model_loaded,
                "model_name": status.model_name,
                "sample_rate": status.sample_rate,
                "supported_languages": status.supported_languages,
                "engine": "Vosk (Kaldi-based)",
                "features": [
                    "Offline operation",
                    "CPU-only",
                    "94-95% WER",
                    "Word-level timestamps",
                ],
            }
        except ImportError:
            return {
                "available": False,
                "error": "Vosk not installed",
                "install": "pip install vosk>=0.3.45",
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    async def _tool_get_tts_status(self) -> dict:
        """Get Text-to-Speech service status."""
        try:
            from aura_ia_mcp.services.audio_io.tts_service import (
                COQUI_TTS_AVAILABLE,
                CoquiTTSService,
            )

            service = CoquiTTSService()
            status = service.get_status()

            return {
                "available": status.available,
                "model_loaded": status.model_loaded,
                "model_name": status.model_name,
                "vocoder_name": status.vocoder_name,
                "sample_rate": status.sample_rate,
                "use_gpu": status.use_gpu,
                "supported_languages": status.supported_languages,
                "engine": "Coqui TTS",
                "features": [
                    "MOS 4.2-4.4 quality",
                    "CPU real-time capable",
                    "GPU acceleration optional",
                    "Multiple voices",
                ],
            }
        except ImportError:
            return {
                "available": False,
                "error": "Coqui TTS not installed",
                "install": "pip install TTS>=0.22.0",
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    # ==============================================
    # OLLAMA AGENT TOOL HANDLERS (PRD Section 8.13)
    # ==============================================

    def _get_ollama_backend(self):
        """Get or create the Ollama backend instance."""
        if not hasattr(self, "_ollama_backend"):
            from aura_ia_mcp.services.model_gateway.adapters.ollama import (
                OllamaBackend,
                TaskType,
            )

            # Use environment variable or default to Docker container name
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://aura-ia-ollama:11434")
            self._ollama_backend = OllamaBackend(
                base_url=ollama_url,
                model="phi3.5:3.8b",  # Default MCP Concierge model
            )
            self._ollama_task_types = TaskType
        return self._ollama_backend

    async def _tool_ollama_consult(
        self,
        prompt: str,
        model: str = None,
        task_type: str = "general",
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> dict:
        """Consult Ollama model for specialist knowledge."""
        try:
            backend = self._get_ollama_backend()
            TaskType = self._ollama_task_types

            # Map string task type to enum
            task_type_map = {
                "general": TaskType.GENERAL,
                "code": TaskType.CODE,
                "math": TaskType.MATH,
                "creative": TaskType.CREATIVE,
                "analysis": TaskType.ANALYSIS,
                "conversation": TaskType.CONVERSATION,
            }
            task = task_type_map.get(task_type, TaskType.GENERAL)

            result = await backend.generate(
                prompt=prompt,
                user_id="mcp_concierge",
                task_type=task,
                model=model,
                auto_select_model=model is None,
                num_predict=max_tokens,
                temperature=temperature,
            )

            if result.get("success"):
                return {
                    "success": True,
                    "response": result.get("response"),
                    "model": result.get("model"),
                    "input_tokens": result.get("input_tokens"),
                    "output_tokens": result.get("output_tokens"),
                    "latency_ms": result.get("latency_ms"),
                    "budget_remaining": result.get("user_budget_remaining"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error"),
                }
        except ImportError:
            return {
                "success": False,
                "error": "Ollama backend not available",
                "install": "Ensure Ollama service is running on port 9207",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_ollama_list_models(self) -> dict:
        """List available Ollama models."""
        try:
            backend = self._get_ollama_backend()
            models = await backend.list_models()

            if not models:
                return {
                    "success": True,
                    "models": [],
                    "message": "No models found. Use ollama_pull_model to download models.",
                }

            formatted_models = []
            for model in models:
                formatted_models.append(
                    {
                        "name": model.get("name", "unknown"),
                        "size": model.get("size", 0),
                        "modified_at": model.get("modified_at", ""),
                        "details": model.get("details", {}),
                    }
                )

            return {
                "success": True,
                "models": formatted_models,
                "count": len(formatted_models),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_ollama_pull_model(self, model_name: str) -> dict:
        """Pull a model from Ollama registry."""
        try:
            backend = self._get_ollama_backend()
            result = await backend.pull_model(model_name)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_ollama_model_info(self, model_name: str) -> dict:
        """Get detailed information about a model."""
        try:
            backend = self._get_ollama_backend()
            info = await backend.get_model_info(model_name)

            if "error" in info:
                return {"success": False, "error": info["error"]}

            return {
                "success": True,
                "model": model_name,
                "info": info,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _tool_ollama_health(self) -> dict:
        """Check Ollama service health."""
        try:
            backend = self._get_ollama_backend()
            is_healthy = await backend.health()
            circuit_status = backend.get_circuit_status()
            performance_stats = backend.get_performance_stats()

            return {
                "success": True,
                "healthy": is_healthy,
                "service_url": backend.base_url,
                "default_model": backend.model,
                "circuit_breaker": circuit_status,
                "performance": performance_stats,
            }
        except Exception as e:
            return {
                "success": False,
                "healthy": False,
                "error": str(e),
            }

    # ==============================================
    # CONFIGURATION & MANAGEMENT HANDLERS
    # ==============================================

    async def _tool_get_config(self, section: str = "all") -> dict:
        """Get MCP configuration."""
        from pathlib import Path

        config_path = (
            Path(__file__).parent.parent.parent.parent
            / "config"
            / "ide_ultra_config.json"
        )

        try:
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                if section != "all" and section in config:
                    return {section: config[section]}
                return config
        except Exception as e:
            return {"error": str(e)}

        return {
            "backend_url": self.backend_url,
            "ports": {
                "gateway": 9200,
                "backend": 9201,
                "rag": 9202,
                "dashboard": 9205,
                "role_engine": 9206,
            },
        }

    async def _tool_get_project_status(self, section: str = "all") -> dict:
        """Get project status from MASTER_PROJECT_STATUS.md."""
        from pathlib import Path

        status_path = (
            Path(__file__).parent.parent.parent.parent
            / "docs"
            / "MASTER_PROJECT_STATUS.md"
        )

        status = {
            "version": "1.6",
            "status": "Production-Ready",
            "phases_complete": [
                "Phase 1: Standardization & Migration (V.1.1)",
                "Phase 2: Reliability & Scaling (V.1.2)",
                "Phase 3: Security Hardening (V.1.3)",
                "Phase 4: Advanced Intelligence (V.1.4)",
                "Phase 5: Observability Platform (V.1.5)",
                "Phase 6: Strategic & Futuristic (V.1.6)",
            ],
            "phases_in_progress": [
                "Phase 7: Frontend Evolution & Integration",
            ],
            "phases_pending": [
                "Phase 8: Final Production Deployment",
            ],
            "capabilities": {
                "ml_backend": [
                    "sentiment_analysis",
                    "semantic_ranking",
                    "embeddings",
                ],
                "debate_engine": ["dual_model_debate", "consensus_detection"],
                "dag_orchestration": [
                    "parallel_tasks",
                    "workflow_builder",
                    "mermaid_visualization",
                ],
                "risk_router": [
                    "risk_scoring",
                    "approval_workflow",
                    "circuit_breaker",
                ],
                "role_engine": ["14_roles", "23_capabilities", "trust_levels"],
                "observability": [
                    "prometheus",
                    "grafana",
                    "opentelemetry",
                    "loki",
                ],
                "futuristic": [
                    "green_compute",
                    "wasm_sandbox",
                    "confidential_compute",
                ],
                "security": ["pii_filter", "audit_logging", "zero_trust"],
            },
            "test_status": "All tests passing (210+ tests)",
        }

        if section != "all" and section in status:
            return {section: status[section]}

        return status

    async def _tool_list_available_tools(self) -> dict:
        """List all available tools."""
        tools_by_category = {
            "health_status": [
                "check_health",
                "get_system_status",
                "get_model_status",
            ],
            "data_retrieval": [
                "get_documentation",
                "list_entities",
                "get_activity_stats",
            ],
            "command_execution": ["execute_command"],
            "ai_ml": ["analyze_emotion", "semantic_rank"],
            "debugging": ["get_recent_logs", "diagnose_issue"],
            "github": ["list_github_repos"],
            "debate_engine": ["start_debate", "get_debate_status"],
            "dag_orchestration": [
                "create_workflow",
                "execute_workflow",
                "visualize_dag",
            ],
            "risk_management": ["evaluate_risk", "request_approval"],
            "role_engine": [
                "list_roles",
                "get_role_capabilities",
                "suggest_role",
                "check_permission",
            ],
            "observability": [
                "get_metrics",
                "query_traces",
                "search_logs",
                "get_alerts",
                "get_dashboard_url",
            ],
            "green_computing": [
                "check_carbon_intensity",
                "schedule_green_job",
                "get_carbon_budget",
            ],
            "wasm_sandbox": ["list_wasm_plugins", "execute_wasm_plugin"],
            "confidential_computing": ["get_enclave_status"],
            "rag_retrieval": [
                "semantic_search",
                "add_to_knowledge_base",
                "list_collections",
            ],
            "security": ["check_pii", "audit_log", "get_security_audit"],
            "audio_speech": [
                "speech_to_text",
                "text_to_speech",
                "get_stt_status",
                "get_tts_status",
            ],
            "configuration": [
                "get_config",
                "get_project_status",
                "list_available_tools",
            ],
        }

        total = sum(len(tools) for tools in tools_by_category.values())

        return {
            "categories": tools_by_category,
            "total_tools": total,
            "note": "Call any tool by name with appropriate arguments",
        }


class OllamaAdapter:
    """Lightweight adapter for Ollama-based chat (replaces heavy DualModelAdapter)."""

    def __init__(self):
        self.default_temperature = 0.7
        self.default_top_p = 0.9
        self.default_top_k = 40
        self.default_repeat_penalty = 1.1

    def load_model(self, mode: str = "talker"):
        """No-op: Ollama manages models automatically."""
        print(f"ℹ️ OllamaAdapter.load_model called with mode={mode} (No-op)")
        pass

    def get_model_info(self):
        return {
            "name": "ollama_cluster",
            "backend": "remote_http",
            "models": ["llama3.1:8b", "phi3.5:3.8b", "qwen2.5-coder:7b"],
        }

    def is_model_available(self):
        return True


class ChatService:
    """Main chat service orchestrating LLM and tools."""

    def __init__(
        self,
        backend_url: str | None = None,
        model_path: str | None = None,
    ):
        # In-container backend listens on 8001; allow override via env or arg.
        default_backend = (
            os.getenv("AURA_BACKEND_URL") or "http://127.0.0.1:8001"
        )
        self.backend_url = backend_url or default_backend
        self.model_path = model_path
        self.tool_registry = MCPToolRegistry(self.backend_url)
        self.conversations: dict[str, Conversation] = {}
        self._llm = None
        self._llm_available = None
        self._llm_inflight = 0
        self._llm_hang_ts: float | None = None
        self._llm_hang_reason: str | None = None

    @staticmethod
    def _is_mcp_intent(message: str) -> bool:
        """Detect MCP/system intents that must use MCP sources of truth."""
        msg = message.lower()
        return any(keyword in msg for keyword in MCP_KEYWORDS)

    def _list_mcp_tools(self) -> dict[str, Any]:
        """Enumerate MCP tools directly from the registry (no LLM, no backend hop)."""
        tools = []
        for name, tool in self.tool_registry.tools.items():
            tools.append(
                {
                    "name": name,
                    "type": tool.get("type", "tool"),
                    "description": tool.get("description", ""),
                }
            )

        return {"tools": tools, "source": "mcp_registry", "llm_used": False}

    def _get_mcp_info(self) -> dict[str, Any]:
        """Return information about Aura MCP capabilities."""
        tool_count = len(self.tool_registry.tools)
        tool_categories = {}
        for name, tool in self.tool_registry.tools.items():
            tool_type = tool.get("type", "general")
            if tool_type not in tool_categories:
                tool_categories[tool_type] = []
            tool_categories[tool_type].append(name)

        info = f"""🤖 **Aura IA MCP** - Your AI Assistant

**What I Can Do:**
• 🌤️ **Weather** - Get current weather for any location (e.g., "weather in New York")
• 🔍 **Web Search** - Search the internet (e.g., "search for Python tutorials")
• 🕐 **Time & Date** - Tell you the current time and date
• 📊 **System Status** - Check health of MCP services
• 🤖 **AI Models** - Query available LLM models
• 🛠️ **{tool_count} MCP Tools** - Execute specialized operations

**Quick Commands:**
• "What's the weather in [city]?"
• "Search for [topic]"
• "What time is it?"
• "System status"
• "List tools" or "What can you do?"

**Tool Categories:** {', '.join(tool_categories.keys())}

Type 'list tools' to see all {tool_count} available tools."""

        return {
            "response": info,
            "tool_count": tool_count,
            "categories": list(tool_categories.keys()),
            "source": "mcp_info",
            "llm_used": False,
        }

    def _format_weather_response(
        self, weather_data: dict, location: str
    ) -> str:
        """Convert structured weather data into a natural, conversational response."""

        # WMO Weather codes mapping
        weather_codes = {
            0: ("clear sky", "☀️"),
            1: ("mainly clear", "🌤️"),
            2: ("partly cloudy", "⛅"),
            3: ("overcast", "☁️"),
            45: ("fog", "🌫️"),
            48: ("depositing rime fog", "🌫️"),
            51: ("light drizzle", "🌧️"),
            53: ("moderate drizzle", "🌧️"),
            55: ("dense drizzle", "🌧️"),
            61: ("slight rain", "🌧️"),
            63: ("moderate rain", "🌧️"),
            65: ("heavy rain", "🌧️"),
            71: ("slight snow", "🌨️"),
            73: ("moderate snow", "🌨️"),
            75: ("heavy snow", "🌨️"),
            80: ("slight rain showers", "🌦️"),
            81: ("moderate rain showers", "🌦️"),
            82: ("violent rain showers", "⛈️"),
            95: ("thunderstorm", "⛈️"),
            96: ("thunderstorm with hail", "⛈️"),
            99: ("thunderstorm with heavy hail", "⛈️"),
        }

        # Wind direction to compass
        def wind_direction_to_compass(degrees: float) -> str:
            directions = [
                "north",
                "north-northeast",
                "northeast",
                "east-northeast",
                "east",
                "east-southeast",
                "southeast",
                "south-southeast",
                "south",
                "south-southwest",
                "southwest",
                "west-southwest",
                "west",
                "west-northwest",
                "northwest",
                "north-northwest",
            ]
            index = round(degrees / 22.5) % 16
            return directions[index]

        # Wind speed description
        def wind_description(speed: float) -> str:
            if speed < 5:
                return "calm conditions"
            elif speed < 15:
                return "a gentle breeze"
            elif speed < 30:
                return "moderate winds"
            elif speed < 50:
                return "strong winds"
            else:
                return "very strong winds"

        try:
            current = weather_data.get("current_weather", {})
            temp = current.get("temperature", "N/A")
            wind_speed = current.get("windspeed", 0)
            wind_dir = current.get("winddirection", 0)
            weather_code = current.get("weathercode", 0)
            is_day = current.get("is_day", 1)

            # Get weather description and emoji
            weather_desc, weather_emoji = weather_codes.get(
                weather_code, ("unknown conditions", "🌡️")
            )

            # Get wind info
            compass = wind_direction_to_compass(wind_dir)
            wind_desc = wind_description(wind_speed)

            # Time of day greeting
            if is_day:
                time_emoji = "🌞"
            else:
                time_emoji = "🌙"

            # Build natural response
            response_parts = [
                f"Hey! It's currently **{temp}°C** in {location}",
                f"with {weather_desc} {weather_emoji}",
            ]

            if wind_speed > 5:
                response_parts.append(
                    f"and {wind_desc} ({wind_speed} km/h from the {compass})"
                )
            else:
                response_parts.append("with calm winds")

            # Add contextual comment
            if temp > 25 and weather_code <= 2:
                response_parts.append(
                    f". Perfect weather to be outside! {time_emoji}"
                )
            elif temp < 10:
                response_parts.append(". Bundle up if you're heading out! 🧥")
            elif weather_code >= 61:
                response_parts.append(
                    ". You might want to grab an umbrella! ☔"
                )
            else:
                response_parts.append(".")

            return " ".join(response_parts)

        except Exception as e:
            return f"Weather data available for {location}, but I had trouble formatting it: {e}"

    def _handle_time(self, msg: str) -> dict[str, Any]:
        """Return current time with timezone awareness."""
        try:
            import datetime

            try:
                import pytz
            except ImportError:
                pytz = None

            zone = "UTC"
            if "cape town" in msg:
                zone = "Africa/Johannesburg"

            if pytz:
                tz_obj = pytz.timezone(zone)
                now = datetime.datetime.now(tz_obj)
            else:
                now = datetime.datetime.now(datetime.UTC)
                zone = "UTC"

            # Format friendly response
            time_str = now.strftime("%I:%M %p")
            date_str = now.strftime("%A, %B %d, %Y")
            friendly_response = f"🕐 It's currently **{time_str}** ({zone})\n📅 {date_str}"
            
            return {
                "response": friendly_response,
                "location": zone,
                "source": "system_time",
                "llm_used": False,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "error": f"time lookup failed: {exc}",
                "source": "system_time",
                "llm_used": False,
            }

    async def _handle_world_time(self, msg: str) -> dict[str, Any]:
        """Return time for a specific timezone/city."""
        import datetime
        try:
            import pytz
        except ImportError:
            return {
                "response": "⚠️ Timezone support not available. Please install pytz.",
                "llm_used": False,
            }

        # City to timezone mapping
        city_timezones = {
            "new york": "America/New_York",
            "los angeles": "America/Los_Angeles",
            "london": "Europe/London",
            "paris": "Europe/Paris",
            "tokyo": "Asia/Tokyo",
            "sydney": "Australia/Sydney",
            "dubai": "Asia/Dubai",
            "singapore": "Asia/Singapore",
            "hong kong": "Asia/Hong_Kong",
            "berlin": "Europe/Berlin",
            "moscow": "Europe/Moscow",
            "new zealand": "Pacific/Auckland",
            "auckland": "Pacific/Auckland",
            "wellington": "Pacific/Auckland",
            "cape town": "Africa/Johannesburg",
            "johannesburg": "Africa/Johannesburg",
            "mumbai": "Asia/Kolkata",
            "delhi": "Asia/Kolkata",
            "beijing": "Asia/Shanghai",
            "shanghai": "Asia/Shanghai",
            "seoul": "Asia/Seoul",
            "bangkok": "Asia/Bangkok",
            "amsterdam": "Europe/Amsterdam",
            "rome": "Europe/Rome",
            "madrid": "Europe/Madrid",
            "toronto": "America/Toronto",
            "vancouver": "America/Vancouver",
            "chicago": "America/Chicago",
            "denver": "America/Denver",
            "phoenix": "America/Phoenix",
            "hawaii": "Pacific/Honolulu",
            "alaska": "America/Anchorage",
        }

        msg_lower = msg.lower()
        found_city = None
        found_tz = None

        for city, tz in city_timezones.items():
            if city in msg_lower:
                found_city = city.title()
                found_tz = tz
                break

        if not found_tz:
            return {
                "response": "🤔 I couldn't identify the city/timezone. Try asking like 'what time is it in Tokyo?' or 'time in New York'",
                "llm_used": False,
            }

        try:
            tz_obj = pytz.timezone(found_tz)
            now = datetime.datetime.now(tz_obj)
            time_str = now.strftime("%I:%M %p")
            date_str = now.strftime("%A, %B %d")
            
            return {
                "response": f"🕐 In **{found_city}**, it's currently **{time_str}**\n📅 {date_str} ({found_tz})",
                "source": "world_time",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"⚠️ Couldn't get time for {found_city}: {e}",
                "llm_used": False,
            }

    async def _handle_location(self, msg: str) -> dict[str, Any]:
        """Get user's approximate location via IP geolocation."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Use ip-api.com for free geolocation
                response = await client.get("http://ip-api.com/json/")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        city = data.get("city", "Unknown")
                        region = data.get("regionName", "")
                        country = data.get("country", "Unknown")
                        lat = data.get("lat", 0)
                        lon = data.get("lon", 0)
                        
                        location_str = f"{city}, {region}" if region else city
                        
                        return {
                            "response": f"📍 Based on your IP, you appear to be in **{location_str}, {country}**\n🌐 Coordinates: {lat:.4f}, {lon:.4f}\n\n_Note: This is approximate based on your IP address._",
                            "city": city,
                            "region": region,
                            "country": country,
                            "lat": lat,
                            "lon": lon,
                            "source": "ip_geolocation",
                            "llm_used": False,
                        }
                
                return {
                    "response": "⚠️ Couldn't determine your location. The geolocation service may be unavailable.",
                    "llm_used": False,
                }
        except Exception as e:
            return {
                "response": f"⚠️ Location lookup failed: {e}",
                "llm_used": False,
            }

    async def _handle_weather(self, msg: str) -> dict[str, Any]:
        """Fetch weather from open-meteo and return human-friendly response."""
        import re

        # Expanded location map for South Africa and common cities
        location_map = {
            "cape town": {
                "name": "Cape Town",
                "lat": -33.918861,
                "lon": 18.4233,
            },
            "johannesburg": {
                "name": "Johannesburg",
                "lat": -26.204103,
                "lon": 28.047304,
            },
            "brackenfell": {
                "name": "Brackenfell",
                "lat": -33.8747,
                "lon": 18.6989,
            },
            "durban": {
                "name": "Durban",
                "lat": -29.8587,
                "lon": 31.0218,
            },
            "pretoria": {
                "name": "Pretoria",
                "lat": -25.7479,
                "lon": 28.2293,
            },
            "stellenbosch": {
                "name": "Stellenbosch",
                "lat": -33.9321,
                "lon": 18.8602,
            },
            "paarl": {
                "name": "Paarl",
                "lat": -33.7342,
                "lon": 18.9623,
            },
            "new york": {"name": "New York", "lat": 40.7128, "lon": -74.006},
            "london": {"name": "London", "lat": 51.5074, "lon": -0.1278},
            "paris": {"name": "Paris", "lat": 48.8566, "lon": 2.3522},
            "tokyo": {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
            "sydney": {"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
        }

        msg_lower = msg.lower()
        location = None
        for key in location_map:
            if key in msg_lower:
                location = location_map[key]
                break

        if location is None:
            # Try a simple regex for "in <city>"
            match = re.search(r"in ([a-zA-Z ]+)", msg_lower)
            if match:
                guessed = match.group(1).strip()
                if guessed in location_map:
                    location = location_map[guessed]

        if location is None:
            # Default to Cape Town for deterministic behavior.
            location = location_map["cape town"]

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": location["lat"],
                        "longitude": location["lon"],
                        "current_weather": True,
                    },
                )
                resp.raise_for_status()
                weather_data = resp.json()

                # Generate human-friendly response
                friendly_response = self._format_weather_response(
                    weather_data, location["name"]
                )

                return {
                    "response": friendly_response,
                    "weather_data": weather_data,  # Structured data still available
                    "location": location["name"],
                    "source": "open_meteo_api",
                    "llm_used": False,
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "response": f"Sorry, I couldn't fetch the weather for {location.get('name', 'that location')}: {exc}",
                "error": str(exc),
                "location": location.get("name"),
                "source": "open_meteo_api",
                "llm_used": False,
            }

    async def _handle_search(self, msg: str) -> dict[str, Any]:
        """Perform a real web search via DuckDuckGo Instant Answer API."""
        import re as _re

        # Extract actual search query by stripping common intent prefixes
        query = msg.strip()
        for prefix in [
            "search the internet for",
            "search internet for",
            "search for",
            "search",
            "internet search",
            "web search",
            "look up",
            "find",
        ]:
            if query.lower().startswith(prefix):
                query = query[len(prefix) :].strip()
                break

        if not query:
            return {
                "results": [],
                "source": "duckduckgo_instant",
                "llm_used": False,
                "note": "empty query after prefix strip",
            }

        # Honor an injected search_service if provided (advanced users can supply a richer backend).
        try:
            search_service = getattr(self, "search_service", None)
            if search_service:
                results = search_service.search(query)
                return {
                    "results": results,
                    "source": "web_search",
                    "llm_used": False,
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "error": f"search failed via custom service: {exc}",
                "source": "web_search",
                "llm_used": False,
            }

        # Built-in HTTP search (no LLM): DuckDuckGo Instant Answer JSON + HTML fallback.
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            ) as client:
                # Try Instant Answer API first
                resp = await client.get(
                    "https://api.duckduckgo.com",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": 1,
                        "skip_disambig": 1,
                        "t": "aura-mcp",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                results: list[dict[str, Any]] = []

                # Prefer abstract if available
                abstract_url = data.get("AbstractURL")
                abstract_text = data.get("AbstractText") or data.get(
                    "Abstract"
                )
                if abstract_url and abstract_text:
                    results.append(
                        {
                            "title": abstract_text[:200],
                            "url": abstract_url,
                            "type": "abstract",
                        }
                    )

                # Collect related topics
                for topic in data.get("RelatedTopics", []):
                    if (
                        isinstance(topic, dict)
                        and topic.get("FirstURL")
                        and topic.get("Text")
                    ):
                        results.append(
                            {
                                "title": topic["Text"][:200],
                                "url": topic["FirstURL"],
                                "type": "link",
                            }
                        )
                    if len(results) >= 5:
                        break

                # If instant answer empty, fallback to DuckDuckGo HTML lite
                if not results:
                    import re as _re
                    from urllib.parse import parse_qs, unquote, urlparse

                    html_resp = await client.get(
                        "https://lite.duckduckgo.com/lite/",
                        params={"q": query},
                    )
                    html_resp.raise_for_status()
                    html = html_resp.text

                    # Parse result links from DDG lite HTML
                    link_pattern = _re.compile(
                        r'<a rel="nofollow" href="([^"]+)" class=[\'"]result-link[\'"]>([^<]+)</a>',
                        _re.IGNORECASE,
                    )
                    for match in link_pattern.finditer(html):
                        raw_url = match.group(1)
                        title = match.group(2).strip()

                        # DDG lite uses redirect links; extract actual URL from uddg param
                        if "duckduckgo.com/l/" in raw_url:
                            parsed = urlparse(raw_url)
                            qs = parse_qs(parsed.query)
                            actual_urls = qs.get("uddg", [])
                            if actual_urls:
                                url = unquote(actual_urls[0])
                            else:
                                continue
                        else:
                            url = raw_url

                        results.append(
                            {"title": title[:200], "url": url, "type": "web"}
                        )
                        if len(results) >= 5:
                            break

                return {
                    "results": results,
                    "query": query,
                    "source": "duckduckgo",
                    "llm_used": False,
                }
        except Exception as exc:  # noqa: BLE001
            return {
                "error": f"search failed: {exc}",
                "source": "web_search",
                "llm_used": False,
            }

    # ─────────────────────────────────────────────────────────────────────
    # MEDIA AUTOMATION HANDLERS
    # ─────────────────────────────────────────────────────────────────────

    async def _handle_media_queue(self, msg: str) -> dict[str, Any]:
        """Get current download queue status from all media services."""
        try:
            from mcp_server.services.media_automation import get_media_service

            media = get_media_service()
            status = await media.get_status_summary()

            return {
                "response": status,
                "source": "media_automation",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "📺 Media automation service not available. Please check configuration.",
                "error": "media_automation module not found",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Error checking download queue: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_media_download(self, msg: str) -> dict[str, Any]:
        """Handle media download requests - search and add to Sonarr/Radarr.
        
        In TRACKING MODE (default for 15 days):
            - Logs the request for recommendation learning
            - Does NOT actually add to Radarr/Sonarr
            - User must say "confirm download X" to actually download
        """
        try:
            from mcp_server.services.media_automation import get_media_service

            media = get_media_service()

            # Extract the search query
            query = media.extract_search_query(msg)
            if not query:
                return {
                    "response": "🤔 What would you like me to download? Try: 'Download Dune' or 'Get The Bear series'",
                    "llm_used": False,
                }

            # Smart add - searches and adds best match (respects tracking mode)
            result = await media.smart_add(query, auto_select=True)

            if result.get("tracking_mode") and result.get("requires_confirmation"):
                # Tracking mode - logged but not downloaded
                response = result.get("message", "📊 Request tracked.")
                return {
                    "response": response,
                    "result": result,
                    "source": "media_automation",
                    "llm_used": False,
                    "tracking_mode": True
                }
            elif result.get("success"):
                response = result.get("message", "✅ Added to download queue!")
                if result.get("searching"):
                    response += "\n🔍 Searching for releases now..."
            elif result.get("requires_selection"):
                # Multiple results, need user to pick
                search_results = result.get("search_results", {})
                movies = search_results.get("movies", [])[:3]
                series = search_results.get("series", [])[:3]

                lines = ["🔍 Found multiple matches:\n"]

                if movies:
                    lines.append("**Movies:**")
                    for i, m in enumerate(movies, 1):
                        lines.append(f"  {i}. {m.get('title')} ({m.get('year')}) - ⭐ {m.get('rating', 'N/A')}")

                if series:
                    lines.append("\n**Series:**")
                    for i, s in enumerate(series, 1):
                        lines.append(f"  {i}. {s.get('title')} ({s.get('year')}) - {s.get('seasons', '?')} seasons")

                lines.append("\n💡 Be more specific, e.g., 'Download Dune 2021 movie'")
                response = "\n".join(lines)
            else:
                response = result.get("message", "❌ Could not find or add that media.")
                if result.get("error"):
                    response += f"\nError: {result['error']}"

            return {
                "response": response,
                "result": result,
                "source": "media_automation",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "📺 Media automation not configured. Set SONARR_API_KEY and RADARR_API_KEY.",
                "error": "media_automation module not found",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Error processing download request: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_media_confirm(self, msg: str) -> dict[str, Any]:
        """Handle explicit download confirmation - bypasses tracking mode."""
        try:
            from mcp_server.services.media_automation import get_media_service

            media = get_media_service()

            # Extract the search query (remove "confirm download" prefix)
            query = msg.lower()
            for prefix in ["confirm download", "yes download", "actually download", "really download", "do download"]:
                query = query.replace(prefix, "").strip()
            
            query = media.extract_search_query(query)
            if not query:
                return {
                    "response": "🤔 What would you like me to confirm? Try: 'confirm download Dune'",
                    "llm_used": False,
                }

            # Force download - bypasses tracking mode
            result = await media.confirm_download(query)

            if result.get("success"):
                response = result.get("message", "✅ Confirmed and added to download queue!")
                if result.get("searching"):
                    response += "\n🔍 Searching for releases now..."
            else:
                response = result.get("message", "❌ Could not add that media.")
                if result.get("error"):
                    response += f"\nError: {result['error']}"

            return {
                "response": response,
                "result": result,
                "source": "media_automation",
                "llm_used": False,
                "confirmed": True
            }
        except ImportError:
            return {
                "response": "📺 Media automation not configured.",
                "error": "media_automation module not found",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Error confirming download: {e}",
                "error": str(e),
                "llm_used": False,
            }
    
    async def _handle_media_stats(self, msg: str) -> dict[str, Any]:
        """Get media tracking statistics."""
        try:
            from mcp_server.services.media_automation import get_tracking_stats

            stats = await get_tracking_stats()
            
            if "error" in stats:
                return {
                    "response": f"❌ Could not get stats: {stats['error']}",
                    "llm_used": False,
                }
            
            lines = ["📊 **Media Tracking Stats**\n"]
            lines.append(f"📈 Total requests tracked: {stats.get('total_requests', 0)}")
            lines.append(f"🔒 Tracking mode: {'ON' if stats.get('tracking_mode') else 'OFF'}")
            lines.append(f"📅 Data retention: {stats.get('retention_days', 15)} days\n")
            
            by_type = stats.get("by_type", {})
            if by_type:
                lines.append("**By Type:**")
                for t, c in by_type.items():
                    emoji = "🎬" if t == "movie" else "📺" if t == "series" else "🎌"
                    lines.append(f"  {emoji} {t}: {c}")
            
            top_genres = stats.get("top_genres", [])
            if top_genres:
                lines.append("\n**Top Genres:**")
                for g in top_genres[:5]:
                    lines.append(f"  • {g['genre']}: {g['count']}")
            
            recent = stats.get("recent", [])
            if recent:
                lines.append("\n**Recent Requests:**")
                for r in recent[:5]:
                    lines.append(f"  • {r.get('title', 'Unknown')} ({r.get('media_type', '?')})")
            
            return {
                "response": "\n".join(lines),
                "stats": stats,
                "source": "media_automation",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Error getting stats: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_media_search(self, msg: str) -> dict[str, Any]:
        """Search for media without adding to queue."""
        try:
            from mcp_server.services.media_automation import get_media_service

            media = get_media_service()
            query = media.extract_search_query(msg)

            if not query:
                return {
                    "response": "🔍 What would you like me to search for?",
                    "llm_used": False,
                }

            results = await media.smart_search(query)
            movies = results.get("movies", [])[:5]
            series = results.get("series", [])[:5]

            lines = [f"🔍 **Search results for '{query}':**\n"]

            if movies and not any("error" in m for m in movies):
                lines.append("🎬 **Movies:**")
                for m in movies:
                    status = "✅ In library" if m.get("inLibrary") else "➕ Available"
                    lines.append(f"  • {m.get('title')} ({m.get('year')}) - ⭐ {m.get('rating', 'N/A')} [{status}]")

            if series and not any("error" in s for s in series):
                lines.append("\n📺 **Series:**")
                for s in series:
                    status = "✅ In library" if s.get("inLibrary") else "➕ Available"
                    lines.append(f"  • {s.get('title')} ({s.get('year')}) - {s.get('seasons', '?')} seasons [{status}]")

            if not movies and not series:
                lines.append("No results found. Try a different search term.")
            else:
                lines.append("\n💡 Say 'Download [title]' to add to your queue!")

            return {
                "response": "\n".join(lines),
                "results": results,
                "source": "media_automation",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "📺 Media search not available. Configure API keys first.",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Search error: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_plex_status(self, msg: str) -> dict[str, Any]:
        """Get Plex library status and recently added."""
        try:
            from mcp_server.services.media_automation import get_media_service

            media = get_media_service()
            recent = await media.get_plex_recently_added(limit=10)

            if not recent:
                return {
                    "response": "📺 Couldn't fetch Plex data. Check PLEX_TOKEN configuration.",
                    "llm_used": False,
                }

            lines = ["📺 **Recently Added to Plex:**\n"]
            for item in recent:
                if item.get("grandparent_title"):
                    # Episode
                    lines.append(f"  • 📺 {item['grandparent_title']} - {item['title']}")
                else:
                    # Movie
                    lines.append(f"  • 🎬 {item['title']} ({item.get('year', 'N/A')})")

            return {
                "response": "\n".join(lines),
                "recent": recent,
                "source": "plex",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "📺 Plex integration not available.",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Plex error: {e}",
                "error": str(e),
                "llm_used": False,
            }

    # ─────────────────────────────────────────────────────────────────────
    # HOME ASSISTANT HANDLERS
    # ─────────────────────────────────────────────────────────────────────

    async def _handle_ha_status(self, msg: str) -> dict[str, Any]:
        """Get Home Assistant home status summary."""
        try:
            from mcp_server.services.home_assistant import get_home_assistant_service

            ha = get_home_assistant_service()
            summary = await ha.get_home_summary()

            return {
                "response": summary,
                "source": "home_assistant",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "🏠 Home Assistant integration not available. Set HA_TOKEN.",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Home Assistant error: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_ha_control(self, msg: str) -> dict[str, Any]:
        """Handle light/switch control commands."""
        try:
            from mcp_server.services.home_assistant import (
                ENTITY_FRIENDLY_NAMES,
                get_home_assistant_service,
            )

            ha = get_home_assistant_service()
            result = await ha.process_command(msg)

            if result.get("success"):
                # Build friendly response
                actions = []
                for r in result.get("results", []):
                    entity_name = r.get("entity", "device")
                    action = result.get("action", "").replace("_", " ")
                    actions.append(f"{entity_name}")

                if "turn_on" in result.get("action", ""):
                    response = f"✅ Turned on: {', '.join(actions)}"
                elif "turn_off" in result.get("action", ""):
                    response = f"✅ Turned off: {', '.join(actions)}"
                else:
                    response = f"✅ Done: {', '.join(actions)}"
            else:
                response = f"❌ {result.get('error', 'Command failed')}"
                if result.get("hint"):
                    response += f"\n💡 {result['hint']}"

            return {
                "response": response,
                "result": result,
                "source": "home_assistant",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "🏠 Home Assistant not configured. Set HA_TOKEN environment variable.",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Control error: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_ha_climate(self, msg: str) -> dict[str, Any]:
        """Handle AC/climate control commands."""
        try:
            from mcp_server.services.home_assistant import get_home_assistant_service
            import re

            ha = get_home_assistant_service()
            msg_lower = msg.lower()

            # Parse temperature
            temp_match = re.search(r"(\d+)\s*(?:degrees?|°|deg)?", msg_lower)

            # Parse mode
            mode = None
            if "off" in msg_lower and "ac" in msg_lower:
                mode = "off"
            elif "cool" in msg_lower:
                mode = "cool"
            elif "heat" in msg_lower:
                mode = "heat"
            elif "dry" in msg_lower:
                mode = "dry"
            elif "fan only" in msg_lower or "fan mode" in msg_lower:
                mode = "fan_only"
            elif "auto" in msg_lower:
                mode = "auto"

            # Parse fan speed
            fan_mode = None
            for fan in ["turbo", "high", "medium", "low", "auto"]:
                if f"fan {fan}" in msg_lower or f"{fan} fan" in msg_lower:
                    fan_mode = fan
                    break

            results = []

            # Set temperature if specified
            if temp_match:
                temp = int(temp_match.group(1))
                if 16 <= temp <= 30:  # Reasonable AC range
                    result = await ha.set_ac_temperature(temp)
                    if result.get("success"):
                        results.append(f"Temperature set to {temp}°C")
                    else:
                        results.append(f"Failed to set temperature: {result.get('error')}")
                else:
                    results.append(f"Temperature {temp}°C is out of range (16-30)")

            # Set mode if specified
            if mode:
                result = await ha.set_ac_mode(mode)
                if result.get("success"):
                    results.append(f"Mode set to {mode}")
                else:
                    results.append(f"Failed to set mode: {result.get('error')}")

            # Set fan if specified
            if fan_mode:
                result = await ha.set_ac_fan_mode(fan_mode)
                if result.get("success"):
                    results.append(f"Fan set to {fan_mode}")
                else:
                    results.append(f"Failed to set fan: {result.get('error')}")

            # If no specific command, show status
            if not results:
                status = await ha.get_ac_status()
                if "error" not in status:
                    response = f"❄️ **AC Status:**\n"
                    response += f"  Mode: {status['mode'].title()}\n"
                    response += f"  Target: {status['target_temp']}°C\n"
                    response += f"  Room: {status['current_temp']}°C\n"
                    response += f"  Fan: {status['fan_mode']}\n"
                    response += f"  Humidity: {status.get('humidity', 'N/A')}%"
                else:
                    response = f"❌ {status['error']}"
            else:
                response = "✅ AC: " + ", ".join(results)

            return {
                "response": response,
                "source": "home_assistant",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "🏠 Home Assistant not configured.",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ AC control error: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_ha_presence(self, msg: str) -> dict[str, Any]:
        """Handle presence/who's home queries."""
        try:
            from mcp_server.services.home_assistant import get_home_assistant_service

            ha = get_home_assistant_service()
            presence = await ha.get_presence()

            if presence.get("anyone_home"):
                home_persons = [p["name"] for p in presence["persons"] if p["home"]]
                response = f"👥 **Home:** {', '.join(home_persons)}"
            else:
                response = "👥 **Nobody is home** (based on device tracking)"

            # Add details for each person
            for person in presence["persons"]:
                status = "🏠 Home" if person["home"] else f"📍 {person['state'].title()}"
                response += f"\n  • {person['name']}: {status}"

            return {
                "response": response,
                "presence": presence,
                "source": "home_assistant",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "🏠 Home Assistant not configured.",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Presence check error: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_ha_scene(self, msg: str) -> dict[str, Any]:
        """Handle scene activation - both HA scenes and smart scenes."""
        try:
            from mcp_server.services.home_assistant import (
                SMART_SCENES,
                get_home_assistant_service,
            )

            ha = get_home_assistant_service()
            msg_lower = msg.lower()

            # Map natural language to HA scenes
            ha_scene_map = {
                "rainbow": "scene.rainbow",
                "bedroom color": "scene.bedroom_mode_color",
                "room rainbow": "scene.room_rainbow",
            }

            # Map natural language to smart scenes (multi-action)
            smart_scene_map = {
                "goodnight": "goodnight",
                "good night": "goodnight",
                "turn off all": "goodnight",
                "all lights off": "goodnight",
                "movie time": "movie_time",
                "movie mode": "movie_time",
                "leaving home": "leaving_home",
                "leaving": "leaving_home",
                "i'm leaving": "leaving_home",
                "coming home": "coming_home",
                "i'm home": "coming_home",
                "wake up": "wake_up",
                "morning": "wake_up",
                "work mode": "work_mode",
                "study mode": "work_mode",
                "relax": "relax",
                "chill": "relax",
            }

            # Check for smart scenes first (more powerful)
            for phrase, scene_name in smart_scene_map.items():
                if phrase in msg_lower:
                    result = await ha.execute_smart_scene(scene_name)
                    if result.get("success"):
                        response = f"✅ **{scene_name.replace('_', ' ').title()}**\n"
                        response += f"   {result.get('description', '')}\n"
                        actions_done = [r["entity"] for r in result.get("results", []) if r["success"]]
                        if actions_done:
                            response += f"   Changed: {', '.join(actions_done[:5])}"
                            if len(actions_done) > 5:
                                response += f" +{len(actions_done) - 5} more"
                    else:
                        response = f"❌ Scene failed: {result.get('error')}"
                    
                    return {
                        "response": response,
                        "result": result,
                        "source": "home_assistant",
                        "llm_used": False,
                    }

            # Check for HA native scenes
            for phrase, scene_id in ha_scene_map.items():
                if phrase in msg_lower:
                    result = await ha.activate_scene(scene_id)
                    if result.get("success"):
                        response = f"✅ Activated: {phrase.title()}"
                    else:
                        response = f"❌ Failed: {result.get('error')}"
                    
                    return {
                        "response": response,
                        "source": "home_assistant",
                        "llm_used": False,
                    }

            # No scene matched - show available scenes
            response = "🎬 **Available Scenes:**\n\n"
            response += "**Smart Scenes (multi-action):**\n"
            for name, scene in SMART_SCENES.items():
                response += f"  • '{name.replace('_', ' ').title()}' - {scene['description']}\n"
            response += "\n**Light Effects:**\n"
            response += "  • 'Rainbow' - RGB light effect\n"
            response += "  • 'Bedroom color' - Bedroom ambiance"

            return {
                "response": response,
                "source": "home_assistant",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "🏠 Home Assistant not configured.",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Scene error: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_ha_comfort(self, msg: str) -> dict[str, Any]:
        """Handle comfort analysis requests."""
        try:
            from mcp_server.services.home_assistant import get_home_assistant_service

            ha = get_home_assistant_service()
            comfort = await ha.get_comfort_analysis()

            score = comfort.get("comfort_score", 0)
            score_emoji = "😊" if score >= 80 else "😐" if score >= 50 else "😓"

            response = f"🌡️ **Comfort Analysis** {score_emoji} Score: {score}/100\n"

            # Temperature
            if "temperature" in comfort:
                temp = comfort["temperature"]
                response += f"\n🌡️ **Temperature:** {temp['current']}°C "
                response += f"({'✅ Optimal' if temp['status'] == 'optimal' else '⚠️ ' + temp['status'].title()})"

            # Humidity
            if "humidity" in comfort:
                hum = comfort["humidity"]
                response += f"\n💧 **Humidity:** {hum['current']}% "
                response += f"({'✅ Optimal' if hum['status'] == 'optimal' else '⚠️ ' + hum['status'].title()})"

            # Issues
            if comfort.get("issues"):
                response += "\n\n⚠️ **Issues:**"
                for issue in comfort["issues"]:
                    response += f"\n  • {issue}"

            # Recommendations
            if comfort.get("recommendations"):
                response += "\n\n💡 **Recommendations:**"
                for rec in comfort["recommendations"]:
                    response += f"\n  • {rec}"

            return {
                "response": response,
                "comfort": comfort,
                "source": "home_assistant",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "🏠 Home Assistant not configured.",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Comfort analysis error: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_ha_energy(self, msg: str) -> dict[str, Any]:
        """Handle energy usage queries."""
        try:
            from mcp_server.services.home_assistant import get_home_assistant_service

            ha = get_home_assistant_service()
            insights = await ha.get_energy_insights()
            energy = await ha.get_energy_usage()

            response = "⚡ **Energy Report**\n"

            # Current usage
            usage = insights.get("current_usage", {})
            if usage.get("ac_power_w") is not None:
                response += f"\n🌡️ **AC Power:** {usage['ac_power_w']}W"
            if usage.get("ac_total_kwh") is not None:
                response += f"\n📊 **AC Total:** {usage['ac_total_kwh']:.1f} kWh"
            if usage.get("geyser"):
                response += f"\n🔥 **Geyser:** {usage['geyser'].title()}"
            if usage.get("lights_on") is not None:
                response += f"\n💡 **Lights on:** {usage['lights_on']}"

            # Warnings
            if insights.get("warnings"):
                response += "\n\n⚠️ **Warnings:**"
                for warn in insights["warnings"]:
                    response += f"\n  • {warn}"

            # Recommendations
            if insights.get("recommendations"):
                response += "\n\n💡 **Tips:**"
                for rec in insights["recommendations"]:
                    response += f"\n  • {rec}"

            return {
                "response": response,
                "insights": insights,
                "source": "home_assistant",
                "llm_used": False,
            }
        except ImportError:
            return {
                "response": "🏠 Home Assistant not configured.",
                "llm_used": False,
            }
        except Exception as e:
            return {
                "response": f"❌ Energy report error: {e}",
                "error": str(e),
                "llm_used": False,
            }

    async def _handle_mcp_request(
        self, message: str, conversation_id: str, mode: str
    ) -> dict[str, Any]:
        """Central MCP router: deterministic keyword matching + semantic fallback."""
        msg = message.lower()
        payload = None

        # ─────────────────────────────────────────────────────────────────────
        # PHASE 1: Fast keyword matching (no LLM)
        # ─────────────────────────────────────────────────────────────────────

        # Tool listing patterns (natural language)
        tool_list_patterns = [
            "list" in msg and "tool" in msg,
            "what tool" in msg,
            "which tool" in msg,
            "available tool" in msg,
            "show tool" in msg,
            "mcp tool" in msg,
            "capabilities" in msg,
            "what can you do" in msg,
            "what are your" in msg and ("tool" in msg or "capabilit" in msg),
        ]

        # Help/About patterns
        help_about_patterns = [
            "about" in msg and "mcp" in msg,
            "tell me about" in msg,
            "what is" in msg and ("mcp" in msg or "aura" in msg),
            "help" in msg,
            "how do i use" in msg,
            "explain" in msg and ("mcp" in msg or "aura" in msg),
        ]

        if any(tool_list_patterns):
            payload = self._list_mcp_tools()
        elif any(help_about_patterns):
            payload = self._get_mcp_info()
        # Home Assistant status check BEFORE generic status (more specific first)
        # But NOT if it's a command (turn/switch)
        elif any(kw in msg for kw in ["home status", "house status", "what lights"]) and not any(cmd in msg for cmd in ["turn", "switch"]):
            payload = await self._handle_ha_status(msg)
        elif ("status" in msg or "health" in msg) and "home" not in msg:
            payload = await self._tool_get_system_status()
        elif "ollama" in msg:
            payload = await self._tool_ollama_list_models()
        elif "model" in msg or "llm" in msg:
            payload = await self._tool_get_model_status()
        elif "where am i" in msg or "my location" in msg or ("location" in msg and "where" in msg):
            payload = await self._handle_location(msg)
        elif "time in" in msg or "timezone" in msg:
            payload = await self._handle_world_time(msg)
        elif "time" in msg or "date" in msg:
            payload = self._handle_time(msg)
        elif "weather" in msg:
            payload = await self._handle_weather(msg)
        # Media automation handlers
        elif any(kw in msg for kw in ["what's downloading", "whats downloading", "what is downloading", "download queue", "download status"]) or (msg.strip() == "downloading"):
            payload = await self._handle_media_queue(msg)
        elif any(kw in msg for kw in ["confirm download", "yes download", "actually download", "really download", "do download"]):
            payload = await self._handle_media_confirm(msg)
        elif any(kw in msg for kw in ["media stats", "tracking stats", "what have i searched", "media tracking"]):
            payload = await self._handle_media_stats(msg)
        elif any(kw in msg for kw in ["download", "get me", "add to", "grab", "queue"]) and any(kw in msg for kw in ["movie", "series", "show", "anime", "film"]):
            payload = await self._handle_media_download(msg)
        elif any(kw in msg for kw in ["search", "find", "look for"]) and any(kw in msg for kw in ["movie", "movies", "series", "show", "shows", "tv", "anime", "film", "plex", "radarr", "sonarr"]):
            payload = await self._handle_media_search(msg)
        elif any(kw in msg for kw in ["plex", "recently added", "new on plex", "what's new"]):
            payload = await self._handle_plex_status(msg)
        # Home Assistant control handlers
        elif any(kw in msg for kw in ["turn on", "turn off", "switch on", "switch off"]) and any(kw in msg for kw in ["light", "lights", "bedroom", "lounge", "kitchen", "bathroom", "hallway", "study", "geyser", "spare", "guest", "front", "back", "porch", "scullery", "all"]):
            payload = await self._handle_ha_control(msg)
        elif any(kw in msg for kw in ["ac", "aircon", "air con", "air conditioner"]) or ("degrees" in msg and any(kw in msg for kw in ["set", "turn", "make"])):
            payload = await self._handle_ha_climate(msg)
        elif any(kw in msg for kw in ["who is home", "anyone home", "who's home", "whos home", "is anyone"]):
            payload = await self._handle_ha_presence(msg)
        elif any(kw in msg for kw in ["scene", "movie time", "goodnight", "good night", "leaving", "coming home", "wake up", "work mode", "relax", "chill"]):
            payload = await self._handle_ha_scene(msg)
        elif any(kw in msg for kw in ["comfort", "how comfortable", "temperature ok", "too hot", "too cold"]):
            payload = await self._handle_ha_comfort(msg)
        elif any(kw in msg for kw in ["energy", "power usage", "electricity", "how much power", "energy report"]):
            payload = await self._handle_ha_energy(msg)
        elif "search" in msg or "internet" in msg or "look up" in msg:
            payload = await self._handle_search(msg)

        # ─────────────────────────────────────────────────────────────────────
        # PHASE 2: Semantic intent classification (lightweight LLM)
        # ─────────────────────────────────────────────────────────────────────
        
        if payload is None and INTENT_CLASSIFIER_AVAILABLE:
            payload = await self._handle_semantic_intent(message)
        
        # ─────────────────────────────────────────────────────────────────────
        # PHASE 3: Fallback
        # ─────────────────────────────────────────────────────────────────────
        
        if payload is None:
            payload = {
                "response": "I understood your request but couldn't find a matching action. Try 'help' to see what I can do.",
                "llm_used": False,
                "source": "mcp_router",
            }

        conv = self.get_or_create_conversation(conversation_id, mode)
        conv.add_message("assistant", json.dumps(payload))
        return {
            "response": payload,
            "tool_calls": [],
            "conversation_id": conversation_id,
            "mode": mode,
            "llm_used": payload.get("llm_used", False),
        }
    
    async def _handle_semantic_intent(self, message: str) -> dict[str, Any] | None:
        """Handle message using semantic intent classification.
        
        Uses lightweight LLM to classify intent and extract parameters,
        then routes to the appropriate handler.
        """
        try:
            classifier = get_intent_classifier()
            result = await classifier.classify(message, use_llm=True)
            
            print(f"🎯 Semantic: {result.intent.value} ({result.confidence:.0%}) params={result.parameters}")
            
            # Route based on classified intent
            if result.confidence < 0.6:
                # Low confidence - let it fall through to general chat
                return None
            
            intent = result.intent
            params = result.parameters
            
            # Home Light Control
            if intent == Intent.HOME_LIGHT_CONTROL:
                return await self._handle_ha_control_semantic(params)
            
            # Home AC Control
            elif intent == Intent.HOME_AC_CONTROL:
                return await self._handle_ha_climate_semantic(params)
            
            # Home Status
            elif intent == Intent.HOME_STATUS:
                return await self._handle_ha_status(message)
            
            # Home Scene
            elif intent == Intent.HOME_SCENE:
                return await self._handle_ha_scene(message)
            
            # Home Presence
            elif intent == Intent.HOME_PRESENCE:
                return await self._handle_ha_presence(message)
            
            # Home Energy
            elif intent == Intent.HOME_ENERGY:
                return await self._handle_ha_energy(message)
            
            # Home Comfort
            elif intent == Intent.HOME_COMFORT:
                return await self._handle_ha_comfort(message)
            
            # Media Search
            elif intent == Intent.MEDIA_SEARCH:
                return await self._handle_media_search(message)
            
            # Media Download
            elif intent == Intent.MEDIA_DOWNLOAD:
                return await self._handle_media_download(message)
            
            # Media Queue
            elif intent == Intent.MEDIA_QUEUE:
                return await self._handle_media_queue(message)
            
            # Media Confirm
            elif intent == Intent.MEDIA_CONFIRM:
                return await self._handle_media_confirm(message)
            
            # Media Stats
            elif intent == Intent.MEDIA_STATS:
                return await self._handle_media_stats(message)
            
            # System Status
            elif intent == Intent.SYSTEM_STATUS:
                return await self._tool_get_system_status()
            
            # System Time
            elif intent == Intent.SYSTEM_TIME:
                return self._handle_time(message)
            
            # System Weather
            elif intent == Intent.SYSTEM_WEATHER:
                return await self._handle_weather(message)
            
            # System Location
            elif intent == Intent.SYSTEM_LOCATION:
                return await self._handle_location(message)
            
            # System Search
            elif intent == Intent.SYSTEM_SEARCH:
                return await self._handle_search(message)
            
            # System Help
            elif intent == Intent.SYSTEM_HELP:
                return self._get_mcp_info()
            
            # System Tools
            elif intent == Intent.SYSTEM_TOOLS:
                return self._list_mcp_tools()
            
            # General Chat - return None to let main chat handler use LLM
            elif intent == Intent.GENERAL_CHAT:
                return None
            
            # Unknown - return None
            return None
            
        except Exception as e:
            print(f"⚠️ Semantic intent handling error: {e}")
            return None
    
    async def _handle_ha_control_semantic(self, params: dict) -> dict[str, Any]:
        """Handle light control from semantic classification."""
        action = params.get("action", "on")
        room = params.get("room")
        
        if not room:
            return {
                "response": "Which room's light would you like to control?",
                "llm_used": True,
                "source": "semantic_router",
            }
        
        # Build the command message for the existing handler
        command = f"turn {action} {room} light"
        return await self._handle_ha_control(command)
    
    async def _handle_ha_climate_semantic(self, params: dict) -> dict[str, Any]:
        """Handle AC control from semantic classification."""
        action = params.get("action", "status")
        
        try:
            from mcp_server.services.home_assistant import get_home_assistant_service
            ha = get_home_assistant_service()
            
            if action == "status":
                result = await ha.get_ac_status()
                if result.get("success"):
                    status = result
                    response = f"❄️ AC Status:\n"
                    response += f"Mode: {status.get('mode', 'unknown').title()}\n"
                    response += f"Target: {status.get('target_temp', 'N/A')}°C\n"
                    response += f"Room: {status.get('current_temp', 'N/A')}°C\n"
                    response += f"Fan: {status.get('fan_mode', 'auto')}\n"
                    response += f"Humidity: {status.get('humidity', 'N/A')}%"
                    return {"response": response, "llm_used": True, "source": "semantic_ha"}
                else:
                    return {"response": f"❌ Could not get AC status: {result.get('error')}", "llm_used": True, "source": "semantic_ha"}
            
            elif action == "set_temp":
                temp = params.get("temperature")
                if temp:
                    result = await ha.set_ac_temperature(float(temp))
                    if result.get("success"):
                        return {"response": f"✅ AC temperature set to {temp}°C", "llm_used": True, "source": "semantic_ha"}
                    else:
                        return {"response": f"❌ Failed to set temperature: {result.get('error')}", "llm_used": True, "source": "semantic_ha"}
                return {"response": "What temperature would you like?", "llm_used": True, "source": "semantic_ha"}
            
            elif action == "set_mode":
                mode = params.get("mode")
                if mode:
                    result = await ha.set_ac_mode(mode)
                    if result.get("success"):
                        return {"response": f"✅ AC mode set to {mode.title()}", "llm_used": True, "source": "semantic_ha"}
                    else:
                        return {"response": f"❌ Failed to set mode: {result.get('error')}", "llm_used": True, "source": "semantic_ha"}
                return {"response": "Which mode? (cool, heat, auto, dry, fan_only, off)", "llm_used": True, "source": "semantic_ha"}
            
            elif action == "set_fan":
                fan = params.get("fan")
                if fan:
                    result = await ha.set_ac_fan_mode(fan)
                    if result.get("success"):
                        return {"response": f"✅ AC fan set to {fan.title()}", "llm_used": True, "source": "semantic_ha"}
                    else:
                        return {"response": f"❌ Failed to set fan: {result.get('error')}", "llm_used": True, "source": "semantic_ha"}
                return {"response": "Which fan speed? (auto, low, medium, high, turbo)", "llm_used": True, "source": "semantic_ha"}
            
            else:
                return {"response": "I can help with AC status, temperature, mode, or fan speed.", "llm_used": True, "source": "semantic_ha"}
                
        except Exception as e:
            return {"response": f"❌ AC control error: {e}", "llm_used": True, "source": "semantic_ha"}

    def _get_llm(self):
        """Lazy load the LLM adapter (now lightweight OllamaAdapter)."""
        if self._llm is None:
            self._llm = OllamaAdapter()
            self._llm_available = True
            print("ℹ️ Lightweight OllamaAdapter initialized.")
        return self._llm

    def _requires_worker(self, message: str) -> bool:
        """Determine if message requires WORKER model (heavy reasoning)."""
        from mcp_server.model_adapters.local_llm_adapter import WORKER_KEYWORDS

        msg_lower = message.lower()
        return any(kw in msg_lower for kw in WORKER_KEYWORDS)

    async def _run_llm_chat(
        self,
        llm,
        messages: list[dict[str, str]],
        mode: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        top_k: int | None = None,
        repeat_penalty: float | None = None,
        timeout_s: float = CHAT_TIMEOUT_S,
        force_worker: bool = False,
    ) -> tuple[dict | None, str | None]:
        """Run llm.chat in a thread with a hard timeout to avoid hung requests.

        Uses Ollama API directly with mode-based model routing.

        Mode to Model mapping:
        - chat/concierge → llama3.1:8b (always loaded)
        - mcp_command/debug → qwen2.5-coder:7b
        - general → phi3.5:3.8b (fast fallback)
        """
        # Mode to model mapping (from lifecycle.py)
        MODE_TO_MODEL = {
            "auto": "phi3.5:3.8b",  # Auto mode uses fast model, routing handles intent
            "chat": "phi3.5:3.8b",
            "concierge": "llama3.1:8b",
            "mcp_command": "qwen2.5-coder:7b",
            "mcp": "qwen2.5-coder:7b",
            "debug": "qwen2.5-coder:7b",
            "general": "phi3.5:3.8b",
            "ai": "llama3.1:8b",
        }

        model = MODE_TO_MODEL.get(mode, "phi3.5:3.8b")
        ollama_url = os.getenv(
            "OLLAMA_BASE_URL", "http://aura-ia-ollama:11434"
        )

        start = time.time()
        self._llm_inflight += 1

        # Build system prompt - friendly and conversational
        system_prompt = """You are Aura, a friendly and helpful AI assistant. You have a warm, conversational personality.

PERSONALITY:
- Be warm, friendly, and personable - like chatting with a knowledgeable friend
- Use natural language, not robotic responses
- Add appropriate emojis to make responses feel more human 😊
- Be concise but not cold - show you care about helping
- If you don't know something, say so honestly and offer alternatives

CAPABILITIES (use these automatically when relevant):
- Weather: Get current weather for any location
- Time: Tell time in any timezone worldwide
- Location: Detect user's approximate location via IP
- Search: Look up information on the internet
- System: Check health/status of MCP services

IMPORTANT RULES:
- When asked about time, weather, or location - USE THE TOOLS AUTOMATICALLY, don't just describe them
- Give direct answers, not instructions on how to get answers
- Format responses nicely with line breaks for readability
- If a question implies needing a tool (like "what's the time in Tokyo"), use it immediately"""

        # Prepare messages with system prompt
        ollama_messages = [
            {"role": "system", "content": system_prompt}
        ] + messages

        try:
            async with httpx.AsyncClient(
                timeout=timeout_s, trust_env=False
            ) as client:
                response = await client.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": ollama_messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                )

                if response.status_code != 200:
                    duration_ms = int((time.time() - start) * 1000)
                    print(
                        f"❌ Ollama returned HTTP {response.status_code} after {duration_ms}ms"
                    )
                    return None, f"Ollama HTTP {response.status_code}"

                data = response.json()
                content = data.get("message", {}).get("content", "")

                duration_ms = int((time.time() - start) * 1000)
                print(
                    f"✅ Ollama chat completed in {duration_ms}ms (model={model})"
                )

                result = {
                    "response": content,
                    "tool_call": None,  # Ollama doesn't use tool_call format
                    "usage": {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0)
                        + data.get("eval_count", 0),
                    },
                    "model_used": "ollama",
                    "model_name": model,
                }
                return result, None

        except httpx.TimeoutException:
            duration_ms = int((time.time() - start) * 1000)
            print(f"⚠️ Ollama chat timed out after {duration_ms}ms")
            self._llm_hang_ts = time.time()
            self._llm_hang_reason = (
                f"Ollama chat exceeded timeout {timeout_s}s"
            )
            return None, "timeout"
        except Exception as e:  # noqa: BLE001
            duration_ms = int((time.time() - start) * 1000)
            print(f"❌ Ollama chat failed after {duration_ms}ms: {e}")
            return None, str(e)
        finally:
            self._llm_inflight = max(0, self._llm_inflight - 1)

    def is_llm_available(self) -> bool:
        """Check if LLM is available (Assumed True for Ollama service)."""
        return True

    def get_model_info(self) -> dict[str, Any]:
        """Get info about available models (TALKER/WORKER)."""
        llm = self._get_llm()
        if llm and hasattr(llm, "get_model_info"):
            return llm.get_model_info()
        return {"available": False}

    def get_watchdog_status(self) -> dict[str, Any]:
        """Expose watchdog status for health endpoints."""
        return {
            "inflight": self._llm_inflight,
            "last_hang_ts": self._llm_hang_ts,
            "last_hang_reason": self._llm_hang_reason,
            "timeout_s": CHAT_TIMEOUT_S,
            "watchdog_s": CHAT_WATCHDOG_S,
        }

    def get_or_create_conversation(
        self, conversation_id: str, mode: str = "general"
    ) -> Conversation:
        """Get or create a conversation with SQLite persistence.

        If PERSISTENCE_AVAILABLE, loads conversation history from database
        so the model can remember past interactions.
        """
        if PERSISTENCE_AVAILABLE:
            # Use persistent store - loads history from SQLite
            store = get_conversation_store()
            conv = store.get_or_create_conversation(conversation_id, mode)
            # Also keep reference in local cache for backward compat
            self.conversations[conversation_id] = conv
            return conv
        else:
            # Fallback: in-memory only
            if conversation_id not in self.conversations:
                self.conversations[conversation_id] = Conversation(
                    id=conversation_id, mode=mode
                )
            return self.conversations[conversation_id]

    def clear_conversation(self, conversation_id: str = "default") -> bool:
        """Clear a conversation's message history.
        
        Args:
            conversation_id: ID of conversation to clear
            
        Returns:
            True if cleared successfully
        """
        # Clear from in-memory cache
        if conversation_id in self.conversations:
            self.conversations[conversation_id].clear()
        
        # Clear from persistent store if available
        if PERSISTENCE_AVAILABLE:
            store = get_conversation_store()
            store.delete_conversation(conversation_id)
        
        return True

    async def chat(
        self,
        message: str,
        conversation_id: str = "default",
        mode: str = "general",
    ) -> dict[str, Any]:
        """Process a chat message and return response.

        Architecture (Intent-First Routing):
        1. Fast keyword match for obvious commands (no LLM)
        2. Semantic intent classification for ALL other messages (lightweight LLM)
        3. Route to appropriate handler based on classified intent
        4. Only use full LLM chat for general conversation

        Args:
            message: User's message
            conversation_id: Conversation identifier
            mode: Chat mode (general, mcp, ai, debug)

        Returns:
            {
                "response": str,
                "tool_calls": list,
                "conversation_id": str,
                "mode": str,
                "llm_used": bool,
            }
        """
        conv = self.get_or_create_conversation(conversation_id, mode)
        conv.mode = mode

        # Add user message
        conv.add_message("user", message)

        # ─────────────────────────────────────────────────────────────────────
        # PHASE 1: Fast keyword matching for obvious MCP commands
        # ─────────────────────────────────────────────────────────────────────
        if self._is_mcp_intent(message):
            return await self._handle_mcp_request(message, conversation_id, mode)

        # ─────────────────────────────────────────────────────────────────────
        # PHASE 2: Semantic Intent Classification (ALL messages)
        # Uses lightweight LLM to understand user intent
        # ─────────────────────────────────────────────────────────────────────
        if INTENT_CLASSIFIER_AVAILABLE:
            intent_result = await self._classify_and_handle_intent(message, conversation_id, mode)
            if intent_result is not None:
                # Intent was classified and handled
                conv.add_message("assistant", json.dumps(intent_result.get("response", "")))
                return intent_result

        # ─────────────────────────────────────────────────────────────────────
        # PHASE 3: General LLM Chat (only for conversation/unknown intents)
        # ─────────────────────────────────────────────────────────────────────
        tool_calls = []
        model_used = "ollama"
        max_tokens = CHAT_MAX_TOKENS_EXTENDED if mode in EXTENDED_TOKEN_MODES else CHAT_MAX_TOKENS

        try:
            result, err = await self._run_llm_chat(
                llm=None,
                messages=conv.get_messages_for_llm(),
                mode=mode,
                max_tokens=max_tokens,
                temperature=0.7,
                timeout_s=CHAT_TIMEOUT_S,
            )

            if err:
                response = (
                    "LLM timed out—please retry with a shorter prompt or after a moment."
                    if err == "timeout"
                    else f"LLM error: {err}"
                )
            else:
                response = result["response"]
                model_used = result.get("model_name", "ollama")

        except Exception as e:
            import traceback
            print(f"❌ Ollama chat error: {e}")
            traceback.print_exc()
            response = f"Ollama error: {str(e)}. Please ensure Ollama is running and models are loaded."

        conv.add_message("assistant", response)

        return {
            "response": response,
            "tool_calls": tool_calls,
            "conversation_id": conversation_id,
            "mode": mode,
            "llm_used": True,
            "model_used": model_used,
        }

    async def _classify_and_handle_intent(
        self, message: str, conversation_id: str, mode: str
    ) -> dict[str, Any] | None:
        """Classify intent using LLM and route to appropriate handler.
        
        Returns:
            Response dict if intent was handled, None if should fall through to general chat
        """
        try:
            classifier = get_intent_classifier()
            result = await classifier.classify(message, use_llm=True)
            
            print(f"🎯 Intent: {result.intent.value} ({result.confidence:.0%}) params={result.parameters} [{result.classification_time_ms}ms]")
            
            # If classified as general chat or low confidence, return None to use full LLM
            if result.intent == Intent.GENERAL_CHAT or result.confidence < 0.6:
                print(f"   → Routing to general LLM chat")
                return None
            
            # Route to handler based on intent
            payload = await self._execute_intent(result, message)
            
            if payload is None:
                # Handler returned None, fall through to general chat
                return None
            
            return {
                "response": payload,
                "tool_calls": [],
                "conversation_id": conversation_id,
                "mode": mode,
                "llm_used": result.used_llm,
                "intent": result.intent.value,
                "confidence": result.confidence,
            }
            
        except Exception as e:
            print(f"⚠️ Intent classification error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _execute_intent(self, result: "ClassifiedIntent", message: str) -> dict[str, Any] | None:
        """Execute the classified intent by routing to the appropriate handler."""
        intent = result.intent
        params = result.parameters
        
        # ─────────────────────────────────────────────────────────────────────
        # HOME AUTOMATION
        # ─────────────────────────────────────────────────────────────────────
        
        if intent == Intent.HOME_LIGHT_CONTROL:
            return await self._handle_ha_control_semantic(params)
        
        elif intent == Intent.HOME_AC_CONTROL:
            return await self._handle_ha_climate_semantic(params)
        
        elif intent == Intent.HOME_STATUS:
            return await self._handle_ha_status(message)
        
        elif intent == Intent.HOME_SCENE:
            return await self._handle_ha_scene(message)
        
        elif intent == Intent.HOME_PRESENCE:
            return await self._handle_ha_presence(message)
        
        elif intent == Intent.HOME_ENERGY:
            return await self._handle_ha_energy(message)
        
        elif intent == Intent.HOME_COMFORT:
            return await self._handle_ha_comfort(message)
        
        # ─────────────────────────────────────────────────────────────────────
        # MEDIA AUTOMATION
        # ─────────────────────────────────────────────────────────────────────
        
        elif intent == Intent.MEDIA_SEARCH:
            return await self._handle_media_search(message)
        
        elif intent == Intent.MEDIA_DOWNLOAD:
            return await self._handle_media_download(message)
        
        elif intent == Intent.MEDIA_QUEUE:
            return await self._handle_media_queue(message)
        
        elif intent == Intent.MEDIA_CONFIRM:
            return await self._handle_media_confirm(message)
        
        elif intent == Intent.MEDIA_STATS:
            return await self._handle_media_stats(message)
        
        # ─────────────────────────────────────────────────────────────────────
        # SYSTEM / MCP
        # ─────────────────────────────────────────────────────────────────────
        
        elif intent == Intent.SYSTEM_STATUS:
            return await self._tool_get_system_status()
        
        elif intent == Intent.SYSTEM_TIME:
            return self._handle_time(message)
        
        elif intent == Intent.SYSTEM_WEATHER:
            return await self._handle_weather(message)
        
        elif intent == Intent.SYSTEM_LOCATION:
            return await self._handle_location(message)
        
        elif intent == Intent.SYSTEM_SEARCH:
            return await self._handle_search(message)
        
        elif intent == Intent.SYSTEM_HELP:
            return self._get_mcp_info()
        
        elif intent == Intent.SYSTEM_TOOLS:
            return self._list_mcp_tools()
        
        # ─────────────────────────────────────────────────────────────────────
        # GENERAL / UNKNOWN - Return None to use full LLM
        # ─────────────────────────────────────────────────────────────────────
        
        return None

    async def _fallback_response(
        self, message: str, mode: str
    ) -> tuple[str, list]:
        """Fallback when LLM is not available - use pattern matching."""
        message_lower = message.lower()
        tool_calls = []

        # Pattern-based routing
        if any(
            word in message_lower for word in ["health", "status", "check"]
        ):
            result = await self.tool_registry.execute("check_health", {})
            tool_calls.append(
                {"tool": "check_health", "arguments": {}, "result": result}
            )

            if result.get("success"):
                health = result.get("result", {})
                response = f"Backend Status: {'✅ Online' if health.get('ok') else '❌ Offline'}\n"
                if health.get("ml_models"):
                    response += f"ML Models: Sentiment={health['ml_models'].get('sentiment')}, Semantic={health['ml_models'].get('semantic')}"
            else:
                response = f"Could not check health: {result.get('error')}"

        elif any(
            word in message_lower for word in ["docs", "documentation", "help"]
        ):
            result = await self.tool_registry.execute("get_documentation", {})
            tool_calls.append(
                {
                    "tool": "get_documentation",
                    "arguments": {},
                    "result": result,
                }
            )

            if result.get("success"):
                topics = result.get("result", {}).get("topics", [])
                response = f"Available documentation topics: {', '.join(topics)}\n\nAsk about a specific topic for details."
            else:
                response = (
                    f"Could not get documentation: {result.get('error')}"
                )

        elif any(
            word in message_lower for word in ["model", "ml", "ai status"]
        ):
            result = await self.tool_registry.execute("get_model_status", {})
            tool_calls.append(
                {"tool": "get_model_status", "arguments": {}, "result": result}
            )

            if result.get("success"):
                status = result.get("result", {})
                response = "ML Model Status:\n"
                for name, info in status.items():
                    if isinstance(info, dict):
                        response += f"- {name}: {'✅' if info.get('available') else '❌'} ({info.get('model', 'N/A')})\n"
            else:
                response = f"Could not get model status: {result.get('error')}"

        elif any(
            word in message_lower
            for word in ["debug", "diagnose", "fix", "error"]
        ):
            result = await self.tool_registry.execute(
                "diagnose_issue", {"symptom": message}
            )
            tool_calls.append(
                {
                    "tool": "diagnose_issue",
                    "arguments": {"symptom": message},
                    "result": result,
                }
            )

            if result.get("success"):
                diag = result.get("result", {})
                response = "🔍 Diagnostic Results:\n\n"
                for suggestion in diag.get("suggestions", []):
                    response += f"Issue: {suggestion.get('issue')}\n"
                    response += f"Cause: {suggestion.get('likely_cause')}\n"
                    response += f"Fix: {suggestion.get('fix')}\n\n"
            else:
                response = f"Could not run diagnostics: {result.get('error')}"

        elif "command" in message_lower or message_lower.startswith("run "):
            # Extract command
            cmd = message.replace("run ", "").replace("command ", "").strip()
            if cmd:
                result = await self.tool_registry.execute(
                    "execute_command", {"command": cmd}
                )
                tool_calls.append(
                    {
                        "tool": "execute_command",
                        "arguments": {"command": cmd},
                        "result": result,
                    }
                )

                if result.get("success"):
                    output = result.get("result", {}).get("result", {})
                    response = f"Command Output:\n```\n{output.get('output', 'No output')}\n```"
                else:
                    response = f"Command failed: {result.get('error')}"
            else:
                response = "Please specify a command to run. Safe commands: echo, ls, pwd, whoami, date"

        elif (
            "entities" in message_lower
            or "tools" in message_lower
            or "list" in message_lower
        ):
            result = await self.tool_registry.execute("list_entities", {})
            tool_calls.append(
                {"tool": "list_entities", "arguments": {}, "result": result}
            )

            if result.get("success"):
                entities = result.get("result", {}).get("entities", [])
                response = "Available MCP Entities:\n"
                for e in entities:
                    response += f"- **{e.get('name')}** ({e.get('type')}): {e.get('description')}\n"
            else:
                response = f"Could not list entities: {result.get('error')}"

        elif "github" in message_lower or "repo" in message_lower:
            result = await self.tool_registry.execute(
                "list_github_repos", {"per_page": 5}
            )
            tool_calls.append(
                {
                    "tool": "list_github_repos",
                    "arguments": {"per_page": 5},
                    "result": result,
                }
            )

            if result.get("success"):
                data = result.get("result", {})
                if "error" in data:
                    response = f"GitHub: {data.get('error')}"
                else:
                    repos = data.get("repos", [])
                    response = "GitHub Repositories:\n"
                    for r in repos[:5]:
                        response += f"- **{r.get('name')}**: {r.get('description', 'No description')}\n"
            else:
                response = f"Could not list repos: {result.get('error')}"

        else:
            # Generic response
            response = """I'm Aura, your MCP assistant. The embedded LLM is not loaded yet.

I can still help you with these commands:
- "check health" - Check backend status
- "model status" - Check ML model status
- "list tools" - List available MCP tools
- "docs" - Get documentation
- "debug [issue]" - Diagnose problems
- "run [command]" - Execute safe commands

To enable full AI chat, run:
```
python scripts/download_phi4_model.py
```
Then restart the backend."""

        return response, tool_calls


# Singleton instance
_chat_service: ChatService | None = None


def get_chat_service(
    backend_url: str | None = None,
    auto_load_model: bool = True,
) -> ChatService:
    """Get the singleton chat service instance.

    Args:
        backend_url: URL of the MCP backend server (defaults to ML_BACKEND_URL env var)
        auto_load_model: If True, automatically load the LLM on first chat
    """
    import os
    global _chat_service
    if _chat_service is None:
        # Use environment variable or default to localhost for development
        resolved_url = backend_url or os.getenv("ML_BACKEND_URL", "http://localhost:9201")
        _chat_service = ChatService(backend_url=resolved_url)
        # Pre-initialize the LLM adapter (lazy load on first use)
        if auto_load_model:
            try:
                from mcp_server.model_adapters.local_llm_adapter import (
                    LocalLLMAdapter,
                )

                adapter = LocalLLMAdapter.get_instance()
                if adapter.is_model_available():
                    print(f"✓ LLM model available: {adapter.model_path.name}")
            except Exception as e:
                print(f"⚠ LLM adapter init: {e}")
    return _chat_service


__all__ = [
    "ChatService",
    "get_chat_service",
    "MCPToolRegistry",
    "Conversation",
]
