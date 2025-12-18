"""Unit tests for RAG retrieval pipeline."""

from __future__ import annotations

import pytest

from src.mcp_server.rag_retriever import MockVectorDB, RAGRetriever


@pytest.mark.asyncio
async def test_rag_retriever_basic():
    """Verify basic retrieval workflow."""
    vector_db = MockVectorDB()

    async def mock_embedding(text: str) -> list[float]:
        return [0.1] * 768

    retriever = RAGRetriever(
        vector_db=vector_db, embedding_fn=mock_embedding, top_k=3
    )
    result = await retriever.retrieve("test query", max_tokens=1000)

    assert len(result["chunks"]) == 3
    assert result["total_tokens"] > 0
    assert result["budget"] == int(1000 * 0.25)


@pytest.mark.asyncio
async def test_rag_retriever_budget_enforcement():
    """Verify retrieval respects token budget."""
    vector_db = MockVectorDB()

    async def mock_embedding(text: str) -> list[float]:
        return [0.1] * 768

    retriever = RAGRetriever(
        vector_db=vector_db,
        embedding_fn=mock_embedding,
        top_k=10,
        retrieval_budget_fraction=0.1,
    )
    result = await retriever.retrieve("test query", max_tokens=500)

    # Budget = 50 tokens; should truncate or limit chunks
    assert result["total_tokens"] <= result["budget"]


@pytest.mark.asyncio
async def test_rag_context_formatting():
    """Verify context formatting includes scores."""
    vector_db = MockVectorDB()

    async def mock_embedding(text: str) -> list[float]:
        return [0.1] * 768

    retriever = RAGRetriever(
        vector_db=vector_db, embedding_fn=mock_embedding, top_k=2
    )
    result = await retriever.retrieve("test query", max_tokens=1000)
    context = retriever.format_context(result)

    assert "## Retrieved Context" in context
    assert "[1]" in context
    assert "score:" in context
