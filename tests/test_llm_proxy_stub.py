import asyncio

from aura_ia_mcp.services.llm_proxy_service import llm_health


def test_llm_health_returns_status():
    """Test LLM proxy health endpoint returns valid status."""
    result = asyncio.run(llm_health())
    assert result["status"] == "healthy"
    assert "backends" in result
    assert "ollama" in result["backends"]
