"""Tests for Wave 6 Phase 1: EmbeddingService with real sentence-transformers."""

import numpy as np
from prometheus_client import CollectorRegistry

from aura_ia_mcp.services.model_gateway.embedding_service import (
    EmbeddingService,
    create_embedding_service_from_env,
)


def test_embedding_service_initialization():
    """Test EmbeddingService initializes correctly."""
    registry = CollectorRegistry()
    service = EmbeddingService(
        model_name="all-MiniLM-L6-v2",
        device="cpu",
        normalize=True,
        metrics_registry=registry,
    )

    assert service.model_name == "all-MiniLM-L6-v2"
    assert service.device == "cpu"
    assert service.normalize is True
    assert service.model is None  # Lazy loading


def test_embedding_service_encode():
    """Test basic encoding functionality."""
    registry = CollectorRegistry()
    service = EmbeddingService(
        model_name="all-MiniLM-L6-v2", metrics_registry=registry
    )

    texts = ["hello world", "machine learning"]
    embeddings = service.encode(texts)

    # Check shape
    assert embeddings.shape == (2, 384)  # MiniLM has 384 dimensions

    # Check normalization (L2 norm should be 1.0)
    norms = np.linalg.norm(embeddings, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)

    # Check values are reasonable floats
    assert embeddings.dtype == np.float32 or embeddings.dtype == np.float64
    assert not np.any(np.isnan(embeddings))
    assert not np.any(np.isinf(embeddings))


def test_embedding_similarity_semantics():
    """Test that embeddings capture semantic similarity."""
    registry = CollectorRegistry()
    service = EmbeddingService(
        model_name="all-MiniLM-L6-v2", metrics_registry=registry
    )

    # Similar sentences
    emb1 = service.encode(["The cat sits on the mat"])[0]
    emb2 = service.encode(["A cat is sitting on a mat"])[0]

    # Dissimilar sentence
    emb3 = service.encode(["Quantum physics is complex"])[0]

    # Cosine similarity (since vectors are normalized, just dot product)
    sim_similar = np.dot(emb1, emb2)
    sim_different = np.dot(emb1, emb3)

    # Similar sentences should have high similarity
    assert (
        sim_similar > 0.7
    ), f"Similar sentences similarity too low: {sim_similar}"

    # Dissimilar sentences should have lower similarity
    assert (
        sim_different < 0.5
    ), f"Dissimilar sentences similarity too high: {sim_different}"

    # Sanity: similar > dissimilar
    assert sim_similar > sim_different


def test_embedding_batch_processing():
    """Test batch encoding efficiency and correctness."""
    registry = CollectorRegistry()
    service = EmbeddingService(
        model_name="all-MiniLM-L6-v2", metrics_registry=registry
    )

    # Generate batch of texts with more variation
    texts = [f"Document {i}: This is about topic {i % 10}" for i in range(100)]
    embeddings = service.encode(texts, batch_size=32)

    # Check shape
    assert embeddings.shape == (100, 384)

    # Check all normalized
    norms = np.linalg.norm(embeddings, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)

    # Check embeddings vary (not all identical)
    # Standard deviation across batch should be non-trivial
    std_per_dim = np.std(embeddings, axis=0)
    assert np.mean(std_per_dim) > 0.01  # Some variation across dimensions


def test_embedding_single_convenience():
    """Test encode_single convenience method."""
    registry = CollectorRegistry()
    service = EmbeddingService(
        model_name="all-MiniLM-L6-v2", metrics_registry=registry
    )

    embedding = service.encode_single("test document")

    # Should be list of floats
    assert isinstance(embedding, list)
    assert len(embedding) == 384
    assert all(isinstance(x, float) for x in embedding)

    # Check normalized
    norm = np.linalg.norm(embedding)
    assert np.isclose(norm, 1.0, atol=1e-5)


def test_embedding_dimension_query():
    """Test get_dimension method."""
    registry = CollectorRegistry()
    service = EmbeddingService(
        model_name="all-MiniLM-L6-v2", metrics_registry=registry
    )

    dim = service.get_dimension()
    assert dim == 384  # MiniLM dimension


def test_embedding_empty_input():
    """Test handling of empty input."""
    registry = CollectorRegistry()
    service = EmbeddingService(
        model_name="all-MiniLM-L6-v2", metrics_registry=registry
    )

    embeddings = service.encode([])
    assert embeddings.shape == (0,)


def test_embedding_metrics_recorded():
    """Test that Prometheus metrics are recorded."""
    registry = CollectorRegistry()
    service = EmbeddingService(
        model_name="all-MiniLM-L6-v2", metrics_registry=registry
    )

    # Encode some texts
    service.encode(["test1", "test2", "test3"])

    # Check metrics exist in registry
    # Note: Counter metric name doesn't include _total suffix in collection
    metric_families = {m.name for m in registry.collect()}
    assert "embedding_latency_seconds" in metric_families
    assert "embedding_documents" in metric_families  # Counter without _total


def test_create_embedding_service_from_env(monkeypatch):
    """Test factory function with environment variables."""
    monkeypatch.setenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    monkeypatch.setenv("EMBEDDING_DEVICE", "cpu")
    monkeypatch.setenv("EMBEDDING_NORMALIZE", "1")

    service = create_embedding_service_from_env()

    assert service.model_name == "all-MiniLM-L6-v2"
    assert service.device == "cpu"
    assert service.normalize is True
    assert service.normalize is True
