"""Layer 2: Symbolic Router - Deterministic Intent Classification & Routing.

The Symbolic Router is the "real mind" of the HNSC system. It:
- Validates all JSON outputs from the LLM
- Maps user intent to specific tools/workflows
- Rejects impossible or unsafe instructions
- Returns safe alternatives when needed
- Enforces PRD compliance on all outputs
- Modifies LLM suggestions to be compliant

The LLM just provides hints; this router makes decisions.

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IntentCategory(Enum):
    """High-level intent categories."""

    QUERY = "query"  # Information retrieval
    COMMAND = "command"  # Execute an action
    CREATE = "create"  # Create/generate something
    MODIFY = "modify"  # Change existing state
    DELETE = "delete"  # Remove something (high risk)
    ANALYZE = "analyze"  # Analysis/inspection
    DEBUG = "debug"  # Troubleshooting
    WORKFLOW = "workflow"  # Multi-step pipeline
    CLARIFY = "clarify"  # Need more information
    UNKNOWN = "unknown"  # Cannot determine


@dataclass
class IntentClassification:
    """Result of intent classification."""

    category: IntentCategory
    confidence: float
    tool_suggestion: str | None = None
    workflow_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    safety_level: str = "safe"  # safe, caution, dangerous
    reasoning: str = ""


class SymbolicRouter:
    """Deterministic router that validates and routes LLM outputs.

    This layer ensures:
    1. All JSON is valid
    2. Tool calls are correctly formatted
    3. Intent is mapped to the right tool/workflow
    4. Safety constraints are enforced
    5. PRD compliance is maintained
    """

    def __init__(self) -> None:
        # Intent patterns - deterministic matching
        self._intent_patterns: dict[IntentCategory, list[re.Pattern]] = {
            IntentCategory.QUERY: [
                re.compile(
                    r"\b(what|how|why|when|where|who|show|display|get|list|tell)\b",
                    re.I,
                ),
                re.compile(
                    r"\b(status|info|information|details|explain)\b", re.I
                ),
            ],
            IntentCategory.COMMAND: [
                re.compile(
                    r"\b(run|execute|start|stop|restart|invoke|call)\b", re.I
                ),
                re.compile(r"\b(check|verify|test|validate)\b", re.I),
            ],
            IntentCategory.CREATE: [
                re.compile(
                    r"\b(create|generate|build|make|write|compose)\b", re.I
                ),
                re.compile(r"\b(new|add|insert)\b", re.I),
            ],
            IntentCategory.MODIFY: [
                re.compile(
                    r"\b(update|change|modify|edit|fix|patch|set)\b", re.I
                ),
                re.compile(r"\b(configure|adjust|tweak)\b", re.I),
            ],
            IntentCategory.DELETE: [
                re.compile(
                    r"\b(delete|remove|drop|clear|purge|destroy)\b", re.I
                ),
            ],
            IntentCategory.ANALYZE: [
                re.compile(
                    r"\b(analyze|examine|inspect|review|audit)\b", re.I
                ),
                re.compile(r"\b(compare|measure|evaluate|assess)\b", re.I),
            ],
            IntentCategory.DEBUG: [
                re.compile(
                    r"\b(debug|diagnose|troubleshoot|investigate)\b", re.I
                ),
                re.compile(r"\b(error|issue|problem|bug|fail)\b", re.I),
            ],
            IntentCategory.WORKFLOW: [
                re.compile(r"\b(workflow|pipeline|sequence|process)\b", re.I),
                re.compile(r"\b(then|after|next|finally)\b", re.I),
            ],
            IntentCategory.CLARIFY: [
                re.compile(r"\?$"),  # Ends with question mark
                re.compile(r"\b(which|should|could|would)\b", re.I),
            ],
        }

        # Tool mappings - deterministic routing
        self._tool_mappings: dict[str, dict[str, Any]] = {
            # Health & Status
            "health": {
                "tool": "check_health",
                "category": IntentCategory.QUERY,
            },
            "status": {
                "tool": "get_system_status",
                "category": IntentCategory.QUERY,
            },
            "model": {
                "tool": "get_model_status",
                "category": IntentCategory.QUERY,
            },
            # Data Retrieval
            "docs": {
                "tool": "get_documentation",
                "category": IntentCategory.QUERY,
            },
            "documentation": {
                "tool": "get_documentation",
                "category": IntentCategory.QUERY,
            },
            "entities": {
                "tool": "list_entities",
                "category": IntentCategory.QUERY,
            },
            "tools": {
                "tool": "list_available_tools",
                "category": IntentCategory.QUERY,
            },
            "activity": {
                "tool": "get_activity_stats",
                "category": IntentCategory.QUERY,
            },
            # Role Engine
            "roles": {"tool": "list_roles", "category": IntentCategory.QUERY},
            "role": {
                "tool": "get_role_capabilities",
                "category": IntentCategory.QUERY,
            },
            "permission": {
                "tool": "check_permission",
                "category": IntentCategory.QUERY,
            },
            # Debate Engine
            "debate": {
                "tool": "start_debate",
                "category": IntentCategory.CREATE,
            },
            # DAG/Workflow
            "workflow": {
                "tool": "create_workflow",
                "category": IntentCategory.CREATE,
            },
            "dag": {"tool": "visualize_dag", "category": IntentCategory.QUERY},
            # Risk
            "risk": {
                "tool": "evaluate_risk",
                "category": IntentCategory.ANALYZE,
            },
            "approval": {
                "tool": "request_approval",
                "category": IntentCategory.COMMAND,
            },
            # Observability
            "metrics": {
                "tool": "get_metrics",
                "category": IntentCategory.QUERY,
            },
            "logs": {
                "tool": "get_recent_logs",
                "category": IntentCategory.QUERY,
            },
            "traces": {
                "tool": "query_traces",
                "category": IntentCategory.QUERY,
            },
            "alerts": {"tool": "get_alerts", "category": IntentCategory.QUERY},
            # Security
            "pii": {"tool": "check_pii", "category": IntentCategory.ANALYZE},
            "audit": {
                "tool": "get_security_audit",
                "category": IntentCategory.QUERY,
            },
            # RAG
            "search": {
                "tool": "semantic_search",
                "category": IntentCategory.QUERY,
            },
            "knowledge": {
                "tool": "add_to_knowledge_base",
                "category": IntentCategory.CREATE,
            },
            # Config
            "config": {"tool": "get_config", "category": IntentCategory.QUERY},
            "project": {
                "tool": "get_project_status",
                "category": IntentCategory.QUERY,
            },
            # Green Computing
            "carbon": {
                "tool": "get_carbon_budget",
                "category": IntentCategory.QUERY,
            },
            "green": {
                "tool": "schedule_green_job",
                "category": IntentCategory.CREATE,
            },
            # Debug
            "diagnose": {
                "tool": "diagnose_issue",
                "category": IntentCategory.DEBUG,
            },
            "debug": {
                "tool": "diagnose_issue",
                "category": IntentCategory.DEBUG,
            },
        }

        # Safety levels for tools
        self._tool_safety: dict[str, str] = {
            "execute_command": "caution",
            "request_approval": "caution",
            "add_to_knowledge_base": "safe",
            "start_debate": "safe",
            "create_workflow": "safe",
            "execute_workflow": "caution",
            "audit_log": "safe",
            # Default: safe
        }

        # JSON schemas for validation
        self._tool_schemas: dict[str, dict] = {}

    def classify_intent(self, user_input: str) -> IntentClassification:
        """Classify user intent deterministically.

        This is the first step - understanding what the user wants.
        """
        input_lower = user_input.lower()

        # Score each category
        category_scores: dict[IntentCategory, float] = {}

        for category, patterns in self._intent_patterns.items():
            score = 0.0
            for pattern in patterns:
                matches = pattern.findall(user_input)
                score += len(matches) * 0.25
            category_scores[category] = min(score, 1.0)

        # Find best category
        best_category = IntentCategory.UNKNOWN
        best_score = 0.0

        for category, score in category_scores.items():
            if score > best_score:
                best_score = score
                best_category = category

        # Find tool suggestion
        tool_suggestion = None
        for keyword, mapping in self._tool_mappings.items():
            if keyword in input_lower:
                tool_suggestion = mapping["tool"]
                # Override category if tool mapping has specific category
                if mapping.get("category") and best_score < 0.5:
                    best_category = mapping["category"]
                break

        # Determine safety level
        safety = "safe"
        if best_category == IntentCategory.DELETE:
            safety = "dangerous"
        elif best_category == IntentCategory.MODIFY:
            safety = "caution"
        elif tool_suggestion and tool_suggestion in self._tool_safety:
            safety = self._tool_safety[tool_suggestion]

        return IntentClassification(
            category=best_category,
            confidence=best_score if best_score > 0 else 0.3,
            tool_suggestion=tool_suggestion,
            requires_confirmation=safety in ("caution", "dangerous"),
            safety_level=safety,
            reasoning=f"Matched category {best_category.value} with score {best_score:.2f}",
        )

    def validate_json(self, text: str) -> tuple[bool, dict | None, str]:
        """Extract and validate JSON from LLM output.

        Returns:
            (is_valid, parsed_json, error_message)
        """
        # Try to find JSON in various formats
        json_patterns = [
            r"```json\s*\n?(.*?)\n?```",
            r"```tool_call\s*\n?(.*?)\n?```",
            r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}",
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    parsed = json.loads(match.strip())
                    return True, parsed, ""
                except json.JSONDecodeError:
                    continue

        # Try parsing the entire text as JSON
        try:
            parsed = json.loads(text.strip())
            return True, parsed, ""
        except json.JSONDecodeError as e:
            return False, None, f"JSON parse error: {e}"

    def validate_tool_call(
        self,
        tool_call: dict[str, Any],
        available_tools: set[str],
    ) -> tuple[bool, str, dict | None]:
        """Validate a tool call from LLM output.

        Returns:
            (is_valid, error_or_tool_name, corrected_call)
        """
        # Check structure
        if not isinstance(tool_call, dict):
            return False, "Tool call must be a dict", None

        name = tool_call.get("name")
        if not name:
            return False, "Missing 'name' field", None

        if name not in available_tools:
            # Try to find closest match
            for tool in available_tools:
                if (
                    name.lower() in tool.lower()
                    or tool.lower() in name.lower()
                ):
                    return (
                        True,
                        tool,
                        {
                            "name": tool,
                            "arguments": tool_call.get("arguments", {}),
                        },
                    )
            return False, f"Unknown tool: {name}", None

        # Validate arguments
        arguments = tool_call.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}

        return True, name, {"name": name, "arguments": arguments}

    def route_to_tool(
        self,
        intent: IntentClassification,
        user_input: str,
        available_tools: set[str],
    ) -> tuple[str | None, dict]:
        """Route intent to the appropriate tool.

        Returns:
            (tool_name, arguments)
        """
        input_lower = user_input.lower()

        # If we have a tool suggestion, validate it
        if (
            intent.tool_suggestion
            and intent.tool_suggestion in available_tools
        ):
            args = self._extract_arguments(user_input, intent.tool_suggestion)
            return intent.tool_suggestion, args

        # Fallback: try keyword matching
        for keyword, mapping in self._tool_mappings.items():
            if keyword in input_lower:
                tool = mapping["tool"]
                if tool in available_tools:
                    args = self._extract_arguments(user_input, tool)
                    return tool, args

        return None, {}

    def _extract_arguments(self, user_input: str, tool_name: str) -> dict:
        """Extract arguments from user input for a specific tool.

        This is deterministic extraction based on tool requirements.
        """
        args: dict[str, Any] = {}

        # Tool-specific argument extraction
        if tool_name == "get_documentation":
            topics = [
                "command",
                "emotion",
                "rank",
                "github",
                "workflow",
                "security",
            ]
            for topic in topics:
                if topic in user_input.lower():
                    args["topic"] = topic
                    break

        elif tool_name == "execute_command":
            # Extract command after keywords
            patterns = [
                r"run\s+(.+)",
                r"execute\s+(.+)",
                r"command[:\s]+(.+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.I)
                if match:
                    args["command"] = match.group(1).strip()
                    break

        elif tool_name == "check_pii":
            # The user input itself is often the text to check
            if "check" in user_input.lower() or "scan" in user_input.lower():
                # Extract text after these keywords
                patterns = [
                    r"(?:check|scan|analyze)\s+(?:pii\s+)?(?:in\s+)?['\"](.+?)['\"]",
                    r"text[:\s]+(.+)",
                ]
                for pattern in patterns:
                    match = re.search(pattern, user_input, re.I)
                    if match:
                        args["text"] = match.group(1)
                        break

        elif tool_name == "semantic_search":
            # Extract search query
            patterns = [
                r"search\s+(?:for\s+)?(.+)",
                r"find\s+(.+)",
                r"query[:\s]+(.+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.I)
                if match:
                    args["query"] = match.group(1).strip()
                    break

        elif tool_name == "diagnose_issue":
            # The user input describes the symptom
            args["symptom"] = user_input

        elif tool_name == "get_recent_logs":
            # Extract service and line count
            if "security" in user_input.lower():
                args["service"] = "security_audit"
            elif "provenance" in user_input.lower():
                args["service"] = "provenance"

            # Extract number of lines
            match = re.search(r"(\d+)\s*(?:lines?|entries?)", user_input, re.I)
            if match:
                args["lines"] = int(match.group(1))

        elif tool_name == "evaluate_risk":
            args["operation"] = user_input

        elif tool_name == "start_debate":
            # Extract topic
            patterns = [
                r"debate\s+(?:about\s+)?(.+)",
                r"topic[:\s]+(.+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.I)
                if match:
                    args["topic"] = match.group(1).strip()
                    break

        return args

    def correct_llm_output(
        self,
        llm_output: str,
        intent: IntentClassification,
        available_tools: set[str],
    ) -> dict[str, Any]:
        """Correct and validate LLM output.

        This is the key function that ensures LLM outputs are always valid.

        Returns:
            {
                "valid": bool,
                "tool_call": dict | None,
                "response": str,
                "corrections_made": list[str],
            }
        """
        corrections: list[str] = []

        # Try to extract tool call
        is_valid, parsed, error = self.validate_json(llm_output)

        if is_valid and parsed:
            # Validate tool call structure
            valid_tool, result, corrected = self.validate_tool_call(
                parsed, available_tools
            )

            if valid_tool:
                if corrected and corrected != parsed:
                    corrections.append(
                        f"Corrected tool call: {parsed} -> {corrected}"
                    )

                return {
                    "valid": True,
                    "tool_call": corrected or parsed,
                    "response": llm_output,
                    "corrections_made": corrections,
                }
            else:
                corrections.append(f"Invalid tool call: {result}")
        elif error:
            corrections.append(f"JSON error: {error}")

        # No valid tool call found - use intent routing
        if intent.tool_suggestion:
            tool_name, args = self.route_to_tool(
                intent, llm_output, available_tools
            )

            if tool_name:
                corrections.append(f"Routed to tool via intent: {tool_name}")
                return {
                    "valid": True,
                    "tool_call": {"name": tool_name, "arguments": args},
                    "response": llm_output,
                    "corrections_made": corrections,
                }

        # Return as plain response (no tool call needed)
        return {
            "valid": True,
            "tool_call": None,
            "response": llm_output,
            "corrections_made": corrections,
        }

    def generate_clarification_request(
        self,
        intent: IntentClassification,
        user_input: str,
    ) -> str:
        """Generate a clarification request when intent is unclear.

        This is deterministic - no LLM needed.
        """
        if intent.category == IntentCategory.UNKNOWN:
            return (
                "I'm not sure what you'd like me to do. Could you please:\n"
                "- Check health/status: Ask about system health or status\n"
                "- Query data: Ask for logs, metrics, or documentation\n"
                "- Execute command: Ask to run a specific operation\n"
                "- Analyze: Ask to review or audit something\n"
                "- Debug: Describe an issue you're facing"
            )

        if intent.confidence < 0.5:
            return (
                f"I think you want to {intent.category.value} something, "
                f"but I'm not certain. Could you be more specific?\n"
                f"For example, try: '{self._get_example_for_category(intent.category)}'"
            )

        if intent.requires_confirmation:
            tool = intent.tool_suggestion or "this operation"
            return (
                f"You're about to perform a {intent.safety_level} operation: {tool}\n"
                f"Please confirm by saying 'yes' or 'confirm', or provide more details."
            )

        return ""

    def _get_example_for_category(self, category: IntentCategory) -> str:
        """Get example input for a category."""
        examples = {
            IntentCategory.QUERY: "Show me the system status",
            IntentCategory.COMMAND: "Run the health check",
            IntentCategory.CREATE: "Create a new workflow",
            IntentCategory.MODIFY: "Update the configuration",
            IntentCategory.DELETE: "Clear the log files",
            IntentCategory.ANALYZE: "Analyze the security audit",
            IntentCategory.DEBUG: "Debug connection issues",
            IntentCategory.WORKFLOW: "Run the full deployment pipeline",
            IntentCategory.CLARIFY: "What tools are available?",
        }
        return examples.get(category, "Show me the status")


@dataclass
class RoutingResult:
    """Result from the route() method - unified interface for HNSC Controller."""

    intent_category: str
    confidence: float
    recommended_tool: str | None = None
    extracted_parameters: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    safety_level: str = "safe"
    workflow_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "intent_category": self.intent_category,
            "confidence": self.confidence,
            "recommended_tool": self.recommended_tool,
            "extracted_parameters": self.extracted_parameters,
            "requires_confirmation": self.requires_confirmation,
            "safety_level": self.safety_level,
            "workflow_id": self.workflow_id,
        }


# Add route() method to SymbolicRouter
def _route_impl(self: SymbolicRouter, user_input: str) -> RoutingResult:
    """High-level routing method for HNSC Controller.

    This combines intent classification and tool routing into a single call.

    Args:
        user_input: The user's natural language input.

    Returns:
        RoutingResult with intent, tool, and parameters.
    """
    # Step 1: Classify intent
    intent = self.classify_intent(user_input)

    # Step 2: Get tool and arguments
    tool_name, arguments = self.route_to_tool(
        intent,
        user_input,
        set(
            self._tool_mappings.get(k, {}).get("tool", "")
            for k in self._tool_mappings.keys()
        ),
    )

    # If no tool found via route_to_tool, use intent suggestion
    if not tool_name and intent.tool_suggestion:
        tool_name = intent.tool_suggestion
        arguments = self._extract_arguments(user_input, tool_name)

    return RoutingResult(
        intent_category=(
            intent.category.value
            if isinstance(intent.category, IntentCategory)
            else str(intent.category)
        ),
        confidence=intent.confidence,
        recommended_tool=tool_name,
        extracted_parameters=arguments,
        requires_confirmation=intent.requires_confirmation,
        safety_level=intent.safety_level,
        workflow_id=intent.workflow_id,
    )


# Monkey-patch the route method onto SymbolicRouter
SymbolicRouter.route = _route_impl


# Singleton instance
_router: SymbolicRouter | None = None


def get_symbolic_router() -> SymbolicRouter:
    """Get singleton router instance."""
    global _router
    if _router is None:
        _router = SymbolicRouter()
    return _router
