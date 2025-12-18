from __future__ import annotations

from typing import Any


def command_args_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["method", "command"],
        "properties": {
            "method": {
                "type": "string",
                "enum": ["run", "dry_run", "explain"],
            },
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "timeout": {"type": "number"},
            "payload": {"type": "object"},
        },
    }


def catalog_args_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["method"],
        "properties": {
            "method": {"type": "string", "enum": ["list_entities", "get_doc"]},
            "query": {"type": "string"},
        },
    }


async def run_command_adapter(
    server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    method = args.get("method")
    command = args.get("command")
    payload = args.get("payload")
    if not method or not command:
        raise ValueError("'method' and 'command' are required")

    if method == "run":
        # Pass-through to backend run
        return await server.backend.run_command(command, payload)
    if method == "dry_run":
        return {"dry_run": True, "command": command, "payload": payload or {}}
    if method == "explain":
        return {
            "explanation": f"This would run: {command}",
            "payload": payload or {},
        }
    raise ValueError(f"Unsupported method for command: {method}")


async def catalog_adapter(
    server: AgentsMCPServer, args: dict[str, Any]
) -> dict[str, Any]:
    method = args.get("method")
    if method == "list_entities":
        entities = await server.backend.list_entities()
        return {"entities": entities}
    if method == "get_doc":
        query = args.get("query")
        if not query:
            raise ValueError("'query' is required for get_doc")
        doc = await server.backend.fetch_documentation(query)
        return {"documentation": doc}
    raise ValueError(f"Unsupported method for catalog: {method}")
