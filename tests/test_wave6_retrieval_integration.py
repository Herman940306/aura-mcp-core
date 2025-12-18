"""Wave 6 Phase 1 integration tests: Real embeddings with Retriever."""

import numpy as np
import pytest
from prometheus_client import CollectorRegistry

from aura_ia_mcp.services.model_gateway.embedding_service import (
    EmbeddingService,
)
from aura_ia_mcp.services.model_gateway.retrieval_pipeline import (
    RetrievalConfig,
    Retriever,
)

# Skip if qdrant-client not available
pytest.importorskip("qdrant_client")

from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


@pytest.fixture
def qdrant_client():
    """Mock Qdrant client for testing."""
    # Use in-memory for tests
    client = QdrantClient(":memory:")
    return client


@pytest.fixture
def test_collection(qdrant_client):
    """Create test collection with sample documents."""
    collection_name = f"test_wave6_{uuid4().hex[:8]}"

    # Create collection (384-dim for MiniLM)
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    )

    # Initialize embedding service
    embed_service = EmbeddingService(model_name="all-MiniLM-L6-v2")

    # Sample documents
    docs = [
        "Machine learning is a subset of artificial intelligence.",
        "Python is a popular programming language for data science.",
        "Deep learning uses neural networks with multiple layers.",
        "Natural language processing enables computers to understand text.",
        "The quick brown fox jumps over the lazy dog.",
    ]

    # Encode and upsert
    embeddings = embed_service.encode(docs)
    points = [
        PointStruct(
            id=i, vector=emb.tolist(), payload={"content": doc, "index": i}
        )
        for i, (doc, emb) in enumerate(zip(docs, embeddings, strict=False))
    ]

    qdrant_client.upsert(collection_name=collection_name, points=points)

    yield collection_name, embed_service

    # Cleanup
    qdrant_client.delete_collection(collection_name)


def test_retriever_with_real_embeddings(qdrant_client, test_collection):
    """Test Retriever uses EmbeddingService correctly."""
    collection_name, embed_service = test_collection
    registry = CollectorRegistry()

    cfg = RetrievalConfig(
        collection=collection_name, top_k=3, retrieval_budget_tokens=500
    )

    retriever = Retriever(
        client=qdrant_client,
        embed_fn=embed_service,
        cfg=cfg,
        metrics_registry=registry,
    )

    # Query: should retrieve ML-related documents
    results = retriever.retrieve("artificial intelligence and neural networks")

    assert len(results) > 0
    assert len(results) <= 3  # Respects top_k

    # Check structure
    for result in results:
        assert "content" in result
        assert "score" in result
        assert isinstance(result["score"], float)

    # Semantic check: ML-related content should rank high
    top_content = results[0]["content"]
    assert any(
        keyword in top_content.lower()
        for keyword in [
            "machine learning",
            "deep learning",
            "neural",
            "intelligence",
        ]
    )


def test_retriever_semantic_similarity(qdrant_client, test_collection):
    """Test that semantic similarity works (synonyms retrieve relevant docs)."""
    collection_name, embed_service = test_collection
    registry = CollectorRegistry()

    cfg = RetrievalConfig(
        collection=collection_name, top_k=5, retrieval_budget_tokens=500
    )

    retriever = Retriever(
        client=qdrant_client,
        embed_fn=embed_service,
        cfg=cfg,
        metrics_registry=registry,
    )

    # Query with synonym: "AI" instead of "artificial intelligence"
    results = retriever.retrieve("AI and ML techniques")

    assert len(results) > 0

    # Should still retrieve relevant ML/AI docs
    contents = [r["content"].lower() for r in results]
    relevant_count = sum(
        1
        for c in contents
        if any(
            kw in c
            for kw in [
                "machine learning",
                "intelligence",
                "neural",
                "deep learning",
            ]
        )
    )

    # At least half should be relevant
    assert relevant_count >= len(results) // 2


def test_retriever_backward_compatibility_legacy_embed_fn(
    qdrant_client, test_collection
):
    """Test Retriever still works with legacy callable embed_fn."""
    collection_name, embed_service = test_collection
    registry = CollectorRegistry()

    cfg = RetrievalConfig(
        collection=collection_name, top_k=3, retrieval_budget_tokens=500
    )

    # Legacy mode: pass encode_single as callable
    retriever = Retriever(
        client=qdrant_client,
        embed_fn=embed_service.encode_single,  # Legacy callable
        cfg=cfg,
        metrics_registry=registry,
    )

    results = retriever.retrieve("machine learning")

    assert len(results) > 0
    assert all("content" in r for r in results)


def test_retriever_token_budget_enforcement(qdrant_client, test_collection):
    """Test that token budget truncation still works with real embeddings."""
    collection_name, embed_service = test_collection
    registry = CollectorRegistry()

    cfg = RetrievalConfig(
        collection=collection_name,
        top_k=5,
        retrieval_budget_tokens=50,  # Very small budget
    )

    retriever = Retriever(
        client=qdrant_client,
        embed_fn=embed_service,
        cfg=cfg,
        metrics_registry=registry,
    )

    results = retriever.retrieve("programming language")

    # Should truncate to fit budget
    total_chars = sum(len(r["content"]) for r in results)
    # Rough token estimate: ~4 chars per token
    estimated_tokens = total_chars / 4

    # Should be close to budget (allow some overhead)
    assert estimated_tokens <= cfg.retrieval_budget_tokens * 1.5


def test_embedding_quality_improvement():
    """Demonstrate that real embeddings improve over pseudo-embeddings."""
    # This is a qualitative test showing semantic understanding
    embed_service = EmbeddingService(model_name="all-MiniLM-L6-v2")

    # Similar concepts
    emb1 = embed_service.encode(["car"])[0]
    emb2 = embed_service.encode(["automobile"])[0]

    # Dissimilar concept
    emb3 = embed_service.encode(["banana"])[0]

    # Cosine similarity (vectors are normalized)
    sim_similar = np.dot(emb1, emb2)
    sim_different = np.dot(emb1, emb3)

    # Real embeddings should capture semantic similarity
    assert sim_similar > 0.6, "Synonyms should have high similarity"
    assert sim_similar > sim_different, "Similar concepts should rank higher"

    # Demonstrate improvement: pseudo-embeddings would be random/arbitrary
    import hashlib

    def pseudo_embed(text: str) -> np.ndarray:
        """Legacy pseudo-embedding (deterministic but not semantic)."""
        h = hashlib.sha256(text.encode()).digest()
        data = (h * 2)[:384]
        vec = np.array([b / 255.0 for b in data], dtype=np.float32)
        return vec / np.linalg.norm(vec)

    pseudo1 = pseudo_embed("car")
    pseudo2 = pseudo_embed("automobile")
    pseudo3 = pseudo_embed("banana")

    pseudo_sim_similar = np.dot(pseudo1, pseudo2)
    pseudo_sim_different = np.dot(pseudo1, pseudo3)

    # Pseudo-embeddings are essentially random (no semantic structure)
    # Real embeddings should have much better discrimination
    assert (
        sim_similar - sim_different > pseudo_sim_similar - pseudo_sim_different
    )

    # Pseudo-embeddings are essentially random (no semantic structure)
    # Real embeddings should have much better discrimination
    assert (
        sim_similar - sim_different > pseudo_sim_similar - pseudo_sim_different
    )
