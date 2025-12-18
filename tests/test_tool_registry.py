from src.mcp_server.tool_registry import load_tools


def test_tool_registry_loads_three_tools():
    tools = load_tools()
    names = sorted(t.name for t in tools)
    assert names == ["embedding_generate", "rag_query", "role_policy"]
    # Validate schema integrity
    for t in tools:
        assert set(t.schema.keys()) >= {"name", "version", "inputs", "outputs"}
