"""RAG service stub test."""

import asyncio

from aura_ia_mcp.services.rag_service import rag_health


def test_rag_health_returns_status():
    """Test RAG service health check returns valid structure."""
    result = asyncio.run(rag_health())
    assert "status" in result
    # Status can be healthy or unhealthy depending on Qdrant availability
    assert result["status"] in ("healthy", "unhealthy")
