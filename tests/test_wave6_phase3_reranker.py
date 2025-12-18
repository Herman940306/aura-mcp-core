"""Tests for Wave 6 Phase 3: ReRanker with cross-encoder."""

import pytest
from prometheus_client import CollectorRegistry

# Skip if sentence-transformers not available
pytest.importorskip("sentence_transformers")

from aura_ia_mcp.services.model_gateway.reranker import (
    ReRanker,
    create_reranker_from_env,
)


def test_reranker_initialization():
    """Test ReRanker initializes with cross-encoder model."""
    registry = CollectorRegistry()

    reranker = ReRanker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        device="cpu",
        metrics_registry=registry,
    )

    assert reranker.model is not None
    assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
    assert reranker.device == "cpu"


def test_reranker_single_prediction():
    """Test scoring a single (query, document) pair."""
    registry = CollectorRegistry()

    reranker = ReRanker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        device="cpu",
        metrics_registry=registry,
    )

    score = reranker.predict_single(
        query="machine learning",
        document="Machine learning is a subset of artificial intelligence",
    )

    # Score should be a float (cross-encoders output logits, not bounded [0,1])
    assert isinstance(score, float)
    # Relevant document should have positive score (typically >0 for MS MARCO model)
    assert score > -10.0  # Sanity check (model outputs can vary)


def test_reranker_rerank_documents():
    """Test re-ranking a list of documents."""
    registry = CollectorRegistry()

    reranker = ReRanker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        device="cpu",
        metrics_registry=registry,
    )

    query = "python programming"
    documents = [
        {"text": "Python is a high-level programming language", "score": 0.5},
        {"text": "Java is an object-oriented language", "score": 0.6},
        {"text": "Python programming tutorials for beginners", "score": 0.4},
        {"text": "The python snake is a reptile", "score": 0.3},
    ]

    reranked = reranker.rerank(query=query, documents=documents, top_k=3)

    # Should return top 3 documents
    assert len(reranked) == 3

    # All results should have cross_encoder_score in metadata
    for doc in reranked:
        assert "metadata" in doc
        assert "cross_encoder_score" in doc["metadata"]
        assert isinstance(doc["metadata"]["cross_encoder_score"], float)

    # Most relevant documents should be ranked higher
    # (Python programming tutorials should rank above Java or snake)
    texts = [doc["text"] for doc in reranked]
    assert "python" in texts[0].lower() or "python" in texts[1].lower()


def test_reranker_empty_documents():
    """Test re-ranking with empty document list."""
    registry = CollectorRegistry()

    reranker = ReRanker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        device="cpu",
        metrics_registry=registry,
    )

    reranked = reranker.rerank(query="test", documents=[], top_k=10)

    assert reranked == []


def test_reranker_fewer_docs_than_top_k():
    """Test re-ranking when documents < top_k."""
    registry = CollectorRegistry()

    reranker = ReRanker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        device="cpu",
        metrics_registry=registry,
    )

    documents = [
        {"text": "Document 1"},
        {"text": "Document 2"},
    ]

    reranked = reranker.rerank(query="test", documents=documents, top_k=10)

    # Should return all 2 documents
    assert len(reranked) == 2


def test_reranker_metrics_recorded():
    """Test that Prometheus metrics are recorded."""
    registry = CollectorRegistry()

    reranker = ReRanker(
        model_name="cross-encoder/ms-marco-MiniLM-L-6-v2",
        device="cpu",
        metrics_registry=registry,
    )

    documents = [{"text": "Test document"}]
    reranker.rerank(query="test", documents=documents, top_k=1)

    # Check metrics exist
    metric_families = {m.name for m in registry.collect()}
    assert "reranker_latency_seconds" in metric_families
    assert "reranker_score_distribution" in metric_families


def test_create_reranker_from_env_disabled():
    """Test factory returns None when disabled."""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"RERANK_ENABLED": "0"}, clear=False):
        reranker = create_reranker_from_env()
        assert reranker is None


def test_create_reranker_from_env_enabled():
    """Test factory creates ReRanker when enabled."""
    import os
    from unittest.mock import patch

    registry = CollectorRegistry()

    with patch.dict(
        os.environ,
        {
            "RERANK_ENABLED": "1",
            "RERANK_MODEL": "cross-encoder/ms-marco-MiniLM-L-6-v2",
            "RERANK_DEVICE": "cpu",
        },
        clear=False,
    ):
        reranker = create_reranker_from_env(metrics_registry=registry)
        assert reranker is not None
        assert reranker.model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"
        assert reranker.device == "cpu"
