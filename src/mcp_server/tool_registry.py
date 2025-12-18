import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from aura_ia_mcp.core.audit import audit_tool_registry_loaded

REQUIRED_SCHEMA_KEYS = {"name", "version", "inputs", "outputs"}
TOOLS_ROOT = Path(__file__).parent / "tools"


class ToolSchemaError(Exception):
    """Schema validation / loading error."""


class Tool:
    def __init__(
        self,
        name: str,
        version: str,
        impl: Any,
        schema: dict[str, Any],
    ) -> None:
        self.name = name
        self.version = version
        self.impl = impl
        self.schema = schema

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute tool implementation (stub)."""
        result: Any = self.impl(payload)
        if not isinstance(result, dict):
            raise ToolSchemaError(
                f"Tool '{self.name}' returned non-dict payload"
            )
        return result  # type: ignore[return-value]


def _load_schema(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = REQUIRED_SCHEMA_KEYS - set(data.keys())
    if missing:
        raise ToolSchemaError(f"Missing keys in schema {path}: {missing}")
    return data


def _load_tool_dir(tool_dir: Path) -> Tool:
    schema_path = tool_dir / "schema.json"
    impl_path = tool_dir / "tool.py"
    if not schema_path.exists() or not impl_path.exists():
        raise ToolSchemaError(f"Invalid tool directory structure: {tool_dir}")
    schema = _load_schema(schema_path)
    spec = importlib.util.spec_from_file_location(
        f"tool_{tool_dir.name}", impl_path
    )
    if spec is None or spec.loader is None:
        raise ToolSchemaError(f"Unable to load tool module: {tool_dir}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    if not hasattr(module, "run"):
        raise ToolSchemaError(
            f"Tool implementation missing run() function: {tool_dir}"
        )
    return Tool(
        schema["name"],
        schema["version"],
        module.run,
        schema,
    )


def load_tools() -> list[Tool]:
    tools: list[Tool] = []
    if not TOOLS_ROOT.exists():
        return tools
    for entry in sorted(TOOLS_ROOT.iterdir()):
        if entry.is_dir():
            tools.append(_load_tool_dir(entry))
    audit_tool_registry_loaded(t.name for t in tools)
    return tools


__all__ = ["Tool", "load_tools", "ToolSchemaError"]
