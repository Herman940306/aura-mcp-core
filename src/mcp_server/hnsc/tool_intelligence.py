"""Layer 5: Tool Intelligence - Specialized Tool Handlers.

Tools handle specialized tasks that reduce LLM workload by 80%:
    - Linting
    - Code refactoring
    - Summarizing
    - Code generation
    - Formatting
    - Analysis

Each tool has built-in intelligence that doesn't require LLM reasoning.

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToolCategory(Enum):
    """Categories of intelligent tools."""

    ANALYSIS = "analysis"  # Analyze data/code/logs
    TRANSFORMATION = "transformation"  # Transform/format data
    VALIDATION = "validation"  # Validate inputs/outputs
    GENERATION = "generation"  # Generate content
    EXTRACTION = "extraction"  # Extract information
    SUMMARIZATION = "summarization"  # Summarize content
    FORMATTING = "formatting"  # Format outputs


@dataclass
class ToolOutput:
    """Structured output from a tool."""

    success: bool
    data: Any
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "summary": self.summary,
            "metadata": self.metadata,
            "suggestions": self.suggestions,
        }


class ToolIntelligenceLayer:
    """Layer of intelligent tools that reduce LLM workload.

    Each tool has built-in logic for common tasks.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}
        self._tool_metadata: dict[str, dict] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register built-in intelligent tools."""

        # Analysis tools
        self._register_tool(
            "analyze_json",
            self._analyze_json,
            ToolCategory.ANALYSIS,
            "Analyze JSON structure and content",
        )

        self._register_tool(
            "analyze_logs",
            self._analyze_logs,
            ToolCategory.ANALYSIS,
            "Analyze log entries for patterns and errors",
        )

        self._register_tool(
            "analyze_error",
            self._analyze_error,
            ToolCategory.ANALYSIS,
            "Analyze error messages and suggest fixes",
        )

        # Transformation tools
        self._register_tool(
            "format_output",
            self._format_output,
            ToolCategory.FORMATTING,
            "Format tool output for display",
        )

        self._register_tool(
            "transform_data",
            self._transform_data,
            ToolCategory.TRANSFORMATION,
            "Transform data between formats",
        )

        # Validation tools
        self._register_tool(
            "validate_tool_call",
            self._validate_tool_call,
            ToolCategory.VALIDATION,
            "Validate a tool call before execution",
        )

        self._register_tool(
            "validate_json_schema",
            self._validate_json_schema,
            ToolCategory.VALIDATION,
            "Validate JSON against a schema",
        )

        # Extraction tools
        self._register_tool(
            "extract_entities",
            self._extract_entities,
            ToolCategory.EXTRACTION,
            "Extract entities from text",
        )

        self._register_tool(
            "extract_metrics",
            self._extract_metrics,
            ToolCategory.EXTRACTION,
            "Extract metrics from data",
        )

        # Summarization tools
        self._register_tool(
            "summarize_results",
            self._summarize_results,
            ToolCategory.SUMMARIZATION,
            "Summarize tool execution results",
        )

        self._register_tool(
            "summarize_logs",
            self._summarize_logs,
            ToolCategory.SUMMARIZATION,
            "Summarize log entries",
        )

    def _register_tool(
        self,
        name: str,
        handler: Callable,
        category: ToolCategory,
        description: str,
    ) -> None:
        """Register an intelligent tool."""
        self._tools[name] = handler
        self._tool_metadata[name] = {
            "category": category.value,
            "description": description,
        }

    def execute(self, tool_name: str, **kwargs) -> ToolOutput:
        """Execute an intelligent tool."""
        if tool_name not in self._tools:
            return ToolOutput(
                success=False,
                data=None,
                summary=f"Unknown tool: {tool_name}",
            )

        try:
            return self._tools[tool_name](**kwargs)
        except Exception as e:
            return ToolOutput(
                success=False,
                data=None,
                summary=f"Tool execution failed: {e}",
            )

    def list_tools(self) -> list[dict]:
        """List available intelligent tools."""
        return [
            {"name": name, **meta}
            for name, meta in self._tool_metadata.items()
        ]

    # ===================
    # Analysis Tools
    # ===================

    def _analyze_json(self, data: Any) -> ToolOutput:
        """Analyze JSON structure and content."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                return ToolOutput(
                    success=False,
                    data=None,
                    summary=f"Invalid JSON: {e}",
                    suggestions=[
                        "Check for syntax errors",
                        "Validate JSON format",
                    ],
                )

        analysis = {
            "type": type(data).__name__,
            "size": len(str(data)),
        }

        if isinstance(data, dict):
            analysis["keys"] = list(data.keys())
            analysis["key_count"] = len(data)
            analysis["nested_depth"] = self._get_dict_depth(data)
        elif isinstance(data, list):
            analysis["item_count"] = len(data)
            if data:
                analysis["first_item_type"] = type(data[0]).__name__

        return ToolOutput(
            success=True,
            data=analysis,
            summary=f"JSON {analysis['type']} with {analysis.get('key_count', analysis.get('item_count', 0))} items",
            metadata={"parsed_at": time.time()},
        )

    def _analyze_logs(self, logs: list[dict]) -> ToolOutput:
        """Analyze log entries for patterns."""
        if not logs:
            return ToolOutput(
                success=True,
                data={"total": 0},
                summary="No logs to analyze",
            )

        analysis = {
            "total": len(logs),
            "levels": {},
            "services": {},
            "error_count": 0,
            "warning_count": 0,
            "patterns": [],
        }

        error_messages = []

        for log in logs:
            # Count by level
            level = str(log.get("level", log.get("type", "unknown"))).lower()
            analysis["levels"][level] = analysis["levels"].get(level, 0) + 1

            if level in ("error", "critical", "fatal"):
                analysis["error_count"] += 1
                msg = log.get("message", log.get("error", str(log)))
                error_messages.append(msg)
            elif level == "warning":
                analysis["warning_count"] += 1

            # Count by service
            service = log.get("service", log.get("source", "unknown"))
            analysis["services"][service] = (
                analysis["services"].get(service, 0) + 1
            )

        # Find common patterns in errors
        if error_messages:
            patterns = self._find_patterns(error_messages)
            analysis["patterns"] = patterns

        suggestions = []
        if analysis["error_count"] > 0:
            suggestions.append(
                f"Found {analysis['error_count']} errors - review immediately"
            )
        if analysis["warning_count"] > 5:
            suggestions.append(
                f"High warning count ({analysis['warning_count']}) - investigate"
            )

        return ToolOutput(
            success=True,
            data=analysis,
            summary=f"Analyzed {analysis['total']} logs: {analysis['error_count']} errors, {analysis['warning_count']} warnings",
            suggestions=suggestions,
        )

    def _analyze_error(self, error: str) -> ToolOutput:
        """Analyze error message and suggest fixes."""
        error_lower = error.lower()

        # Common error patterns and fixes
        patterns = {
            "connection refused": {
                "category": "connection",
                "likely_cause": "Service not running or wrong port",
                "fixes": [
                    "Check if the service is running",
                    "Verify the port number is correct",
                    "Check firewall settings",
                ],
            },
            "timeout": {
                "category": "timeout",
                "likely_cause": "Service overloaded or network issue",
                "fixes": [
                    "Increase timeout value",
                    "Check service health",
                    "Review network connectivity",
                ],
            },
            "permission denied": {
                "category": "permission",
                "likely_cause": "Insufficient permissions",
                "fixes": [
                    "Check user permissions",
                    "Verify role assignments",
                    "Review access policies",
                ],
            },
            "not found": {
                "category": "not_found",
                "likely_cause": "Resource doesn't exist",
                "fixes": [
                    "Verify the resource name/path",
                    "Check if resource was deleted",
                    "Review spelling and case sensitivity",
                ],
            },
            "invalid json": {
                "category": "json",
                "likely_cause": "Malformed JSON data",
                "fixes": [
                    "Validate JSON syntax",
                    "Check for missing quotes or brackets",
                    "Use a JSON validator tool",
                ],
            },
            "memory": {
                "category": "resource",
                "likely_cause": "Insufficient memory",
                "fixes": [
                    "Increase memory allocation",
                    "Reduce batch size",
                    "Restart service to clear memory",
                ],
            },
            "import": {
                "category": "dependency",
                "likely_cause": "Missing Python module",
                "fixes": [
                    "Install required package: pip install <package>",
                    "Check virtual environment activation",
                    "Verify PYTHONPATH is set correctly",
                ],
            },
        }

        matched_pattern = None
        for pattern_key, pattern_info in patterns.items():
            if pattern_key in error_lower:
                matched_pattern = pattern_info
                break

        if matched_pattern:
            return ToolOutput(
                success=True,
                data={
                    "error": error,
                    "category": matched_pattern["category"],
                    "cause": matched_pattern["likely_cause"],
                },
                summary=f"Error type: {matched_pattern['category']} - {matched_pattern['likely_cause']}",
                suggestions=matched_pattern["fixes"],
            )

        # Generic error analysis
        return ToolOutput(
            success=True,
            data={"error": error, "category": "unknown"},
            summary="Unknown error type - manual investigation needed",
            suggestions=[
                "Review full error traceback",
                "Check recent changes",
                "Search documentation for similar errors",
            ],
        )

    # ===================
    # Transformation Tools
    # ===================

    def _format_output(
        self,
        data: Any,
        format: str = "markdown",
    ) -> ToolOutput:
        """Format tool output for display."""
        if format == "markdown":
            formatted = self._to_markdown(data)
        elif format == "json":
            formatted = json.dumps(data, indent=2)
        elif format == "plain":
            formatted = str(data)
        else:
            formatted = str(data)

        return ToolOutput(
            success=True,
            data=formatted,
            summary=f"Formatted output as {format}",
            metadata={"format": format, "length": len(formatted)},
        )

    def _transform_data(
        self,
        data: Any,
        source_format: str,
        target_format: str,
    ) -> ToolOutput:
        """Transform data between formats."""
        # Simple format transformations
        transformations = {
            ("dict", "list"): lambda d: list(d.items()),
            ("list", "dict"): lambda l: {i: v for i, v in enumerate(l)},
            ("str", "list"): lambda s: s.split("\n"),
            ("list", "str"): lambda l: "\n".join(str(x) for x in l),
        }

        key = (source_format, target_format)
        if key in transformations:
            try:
                result = transformations[key](data)
                return ToolOutput(
                    success=True,
                    data=result,
                    summary=f"Transformed from {source_format} to {target_format}",
                )
            except Exception as e:
                return ToolOutput(
                    success=False,
                    data=None,
                    summary=f"Transformation failed: {e}",
                )

        return ToolOutput(
            success=False,
            data=None,
            summary=f"No transformation available: {source_format} -> {target_format}",
        )

    # ===================
    # Validation Tools
    # ===================

    def _validate_tool_call(
        self,
        tool_call: dict,
        available_tools: set[str],
    ) -> ToolOutput:
        """Validate a tool call before execution."""
        errors = []
        warnings = []

        # Check structure
        if not isinstance(tool_call, dict):
            errors.append("Tool call must be a dictionary")
        else:
            if "name" not in tool_call:
                errors.append("Missing 'name' field")
            elif tool_call["name"] not in available_tools:
                errors.append(f"Unknown tool: {tool_call['name']}")
                # Suggest similar tools
                suggestions = [
                    t
                    for t in available_tools
                    if tool_call["name"].lower() in t.lower()
                    or t.lower() in tool_call["name"].lower()
                ]
                if suggestions:
                    warnings.append(f"Did you mean: {', '.join(suggestions)}?")

            if "arguments" in tool_call and not isinstance(
                tool_call["arguments"], dict
            ):
                errors.append("'arguments' must be a dictionary")

        return ToolOutput(
            success=len(errors) == 0,
            data={
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
            },
            summary=(
                "Valid tool call"
                if not errors
                else f"Invalid: {', '.join(errors)}"
            ),
            suggestions=warnings,
        )

    def _validate_json_schema(
        self,
        data: Any,
        schema: dict,
    ) -> ToolOutput:
        """Simple JSON schema validation."""
        errors = []

        # Very basic schema validation
        if "type" in schema:
            expected_type = schema["type"]
            actual_type = type(data).__name__

            type_map = {
                "object": "dict",
                "array": "list",
                "string": "str",
                "number": ("int", "float"),
                "integer": "int",
                "boolean": "bool",
                "null": "NoneType",
            }

            expected = type_map.get(expected_type, expected_type)
            if isinstance(expected, tuple):
                if actual_type not in expected:
                    errors.append(
                        f"Expected type {expected_type}, got {actual_type}"
                    )
            elif actual_type != expected:
                errors.append(
                    f"Expected type {expected_type}, got {actual_type}"
                )

        if "required" in schema and isinstance(data, dict):
            for field in schema["required"]:
                if field not in data:
                    errors.append(f"Missing required field: {field}")

        return ToolOutput(
            success=len(errors) == 0,
            data={"valid": len(errors) == 0, "errors": errors},
            summary=(
                "Schema valid"
                if not errors
                else f"Schema errors: {len(errors)}"
            ),
        )

    # ===================
    # Extraction Tools
    # ===================

    def _extract_entities(self, text: str) -> ToolOutput:
        """Extract entities from text."""
        entities = {
            "urls": re.findall(r"https?://[^\s]+", text),
            "emails": re.findall(r"[\w.-]+@[\w.-]+\.\w+", text),
            "paths": re.findall(r"[/\\][\w./\\-]+\.\w+", text),
            "numbers": re.findall(r"\b\d+(?:\.\d+)?\b", text),
            "ports": re.findall(r":(\d{4,5})\b", text),
        }

        # Filter empty lists
        entities = {k: v for k, v in entities.items() if v}

        return ToolOutput(
            success=True,
            data=entities,
            summary=f"Extracted {sum(len(v) for v in entities.values())} entities",
            metadata={"entity_types": list(entities.keys())},
        )

    def _extract_metrics(self, data: dict) -> ToolOutput:
        """Extract metrics from data."""
        metrics = {}

        def extract_recursive(d, prefix=""):
            if isinstance(d, dict):
                for k, v in d.items():
                    key = f"{prefix}.{k}" if prefix else k
                    if isinstance(v, (int, float)):
                        metrics[key] = v
                    elif isinstance(v, dict):
                        extract_recursive(v, key)

        extract_recursive(data)

        return ToolOutput(
            success=True,
            data=metrics,
            summary=f"Extracted {len(metrics)} metrics",
            metadata={"metric_keys": list(metrics.keys())},
        )

    # ===================
    # Summarization Tools
    # ===================

    def _summarize_results(self, results: list[dict]) -> ToolOutput:
        """Summarize multiple tool results."""
        if not results:
            return ToolOutput(
                success=True,
                data={"total": 0},
                summary="No results to summarize",
            )

        summary_data = {
            "total_results": len(results),
            "successful": sum(1 for r in results if r.get("success", True)),
            "failed": sum(1 for r in results if not r.get("success", True)),
            "tools_used": list(set(r.get("tool", "unknown") for r in results)),
        }

        # Aggregate any numeric values
        numeric_aggregates = {}
        for result in results:
            data = result.get("result", result.get("data", {}))
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, (int, float)):
                        if k not in numeric_aggregates:
                            numeric_aggregates[k] = []
                        numeric_aggregates[k].append(v)

        for k, values in numeric_aggregates.items():
            summary_data[f"avg_{k}"] = sum(values) / len(values)
            summary_data[f"max_{k}"] = max(values)
            summary_data[f"min_{k}"] = min(values)

        return ToolOutput(
            success=True,
            data=summary_data,
            summary=f"Summarized {summary_data['total_results']} results: {summary_data['successful']} successful, {summary_data['failed']} failed",
        )

    def _summarize_logs(self, logs: list[dict]) -> ToolOutput:
        """Summarize log entries."""
        # Reuse log analysis
        analysis = self._analyze_logs(logs)

        if not analysis.success:
            return analysis

        data = analysis.data

        # Generate human-readable summary
        lines = [
            f"📊 Log Summary ({data['total']} entries)",
            "",
            "**By Level:**",
        ]

        for level, count in sorted(data["levels"].items()):
            emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(
                level, "⚪"
            )
            lines.append(f"  {emoji} {level}: {count}")

        if data["error_count"] > 0:
            lines.extend(
                [
                    "",
                    f"⚠️ **{data['error_count']} errors found**",
                ]
            )

            if data["patterns"]:
                lines.append("Common patterns:")
                for pattern in data["patterns"][:3]:
                    lines.append(f"  - {pattern}")

        return ToolOutput(
            success=True,
            data=data,
            summary="\n".join(lines),
            suggestions=analysis.suggestions,
        )

    # ===================
    # Helper Methods
    # ===================

    def _get_dict_depth(self, d: dict, current_depth: int = 1) -> int:
        """Get the maximum depth of a dictionary."""
        if not isinstance(d, dict) or not d:
            return current_depth

        max_depth = current_depth
        for value in d.values():
            if isinstance(value, dict):
                depth = self._get_dict_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)

        return max_depth

    def _find_patterns(
        self, messages: list[str], min_count: int = 2
    ) -> list[str]:
        """Find common patterns in error messages."""
        # Simple word frequency analysis
        word_counts: dict[str, int] = {}

        for msg in messages:
            words = re.findall(r"\b\w{4,}\b", msg.lower())
            for word in set(words):  # Count each word once per message
                word_counts[word] = word_counts.get(word, 0) + 1

        # Return words that appear in multiple messages
        patterns = [
            word for word, count in word_counts.items() if count >= min_count
        ]

        return sorted(patterns, key=lambda w: word_counts[w], reverse=True)[:5]

    def _to_markdown(self, data: Any, indent: int = 0) -> str:
        """Convert data to markdown format."""
        prefix = "  " * indent

        if isinstance(data, dict):
            lines = []
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{prefix}**{k}:**")
                    lines.append(self._to_markdown(v, indent + 1))
                else:
                    lines.append(f"{prefix}- **{k}**: {v}")
            return "\n".join(lines)

        elif isinstance(data, list):
            lines = []
            for item in data:
                if isinstance(item, dict):
                    lines.append(self._to_markdown(item, indent))
                else:
                    lines.append(f"{prefix}- {item}")
            return "\n".join(lines)

        else:
            return f"{prefix}{data}"


# Singleton instance
_tool_layer: ToolIntelligenceLayer | None = None


def get_tool_intelligence() -> ToolIntelligenceLayer:
    """Get singleton tool intelligence layer."""
    global _tool_layer
    if _tool_layer is None:
        _tool_layer = ToolIntelligenceLayer()
    return _tool_layer
