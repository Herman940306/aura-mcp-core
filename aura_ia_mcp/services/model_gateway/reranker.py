"""Re-ranking service using cross-encoder models for improved retrieval relevance.

Wave 6 Phase 3: Re-score top-K candidates with cross-encoder for better ranking.
"""

import logging
import os
from time import perf_counter
from typing import Any

from prometheus_client import CollectorRegistry, Histogram

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    CrossEncoder = None  # type: ignore

logger = logging.getLogger(__name__)

# Default metrics
_default_latency = Histogram(
    "reranker_latency_seconds",
    "Latency of re-ranking operations",
    buckets=(0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0),
)
_default_score_dist = Histogram(
    "reranker_score_distribution",
    "Distribution of cross-encoder scores",
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)


class ReRanker:
    """Re-rank retrieval results using cross-encoder models.

    Cross-encoders score (query, document) pairs jointly, providing more
    accurate relevance scores than separate embeddings + cosine similarity.

    Usage:
        reranker = ReRanker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
        reranked = reranker.rerank(query="machine learning", documents=top_50, top_k=10)
    """

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
        metrics_registry: CollectorRegistry | None = None,
    ):
        """Initialize re-ranker with cross-encoder model.

        Args:
            model_name: HuggingFace cross-encoder model name
            device: Device to run model on ('cpu' or 'cuda')
            metrics_registry: Optional Prometheus registry for test isolation
        """
        if CrossEncoder is None:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        logger.info(f"Loading cross-encoder model: {model_name}")
        self.model = CrossEncoder(model_name, device=device)
        self.model_name = model_name
        self.device = device

        # Metrics
        if metrics_registry is not None:
            self._latency_hist = Histogram(
                "reranker_latency_seconds",
                "Latency of re-ranking operations",
                buckets=(0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0),
                registry=metrics_registry,
            )
            self._score_hist = Histogram(
                "reranker_score_distribution",
                "Distribution of cross-encoder scores",
                buckets=(
                    0.0,
                    0.1,
                    0.2,
                    0.3,
                    0.4,
                    0.5,
                    0.6,
                    0.7,
                    0.8,
                    0.9,
                    1.0,
                ),
                registry=metrics_registry,
            )
        else:
            self._latency_hist = _default_latency
            self._score_hist = _default_score_dist

    def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 10,
        score_key: str = "text",
    ) -> list[dict[str, Any]]:
        """Re-rank documents using cross-encoder scores.

        Args:
            query: Query string
            documents: List of document dicts with 'text' field
            top_k: Number of top documents to return after re-ranking
            score_key: Key in document dict containing text to score

        Returns:
            List of top-K documents sorted by cross-encoder score (descending)
        """
        if not documents:
            return []

        t0 = perf_counter()

        # Prepare (query, document) pairs
        pairs = [(query, doc.get(score_key, "")) for doc in documents]

        # Score with cross-encoder
        try:
            scores = self.model.predict(pairs)
        except Exception as e:
            logger.error(f"Cross-encoder prediction failed: {e}")
            self._latency_hist.observe(perf_counter() - t0)
            return documents[:top_k]  # Fallback: return original order

        # Record score distribution
        for score in scores:
            self._score_hist.observe(float(score))

        # Sort by cross-encoder score (descending)
        scored_docs = list(zip(documents, scores, strict=False))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # Add cross-encoder score to metadata
        result_docs = []
        for doc, score in scored_docs[:top_k]:
            doc_copy = doc.copy()
            if "metadata" not in doc_copy:
                doc_copy["metadata"] = {}
            doc_copy["metadata"]["cross_encoder_score"] = float(score)
            result_docs.append(doc_copy)

        self._latency_hist.observe(perf_counter() - t0)

        logger.debug(
            f"Re-ranked {len(documents)} docs → top {len(result_docs)} "
            f"(latency: {perf_counter() - t0:.3f}s)"
        )

        return result_docs

    def predict_single(self, query: str, document: str) -> float:
        """Score a single (query, document) pair.

        Args:
            query: Query string
            document: Document text

        Returns:
            Cross-encoder relevance score (higher = more relevant)
        """
        score = self.model.predict([(query, document)])
        return float(score[0])


def create_reranker_from_env(
    metrics_registry: CollectorRegistry | None = None,
) -> ReRanker | None:
    """Factory function to create ReRanker from environment variables.

    Environment variables:
        RERANK_ENABLED: Enable re-ranking (0|1, default: 0)
        RERANK_MODEL: Cross-encoder model name (default: ms-marco-MiniLM-L-6-v2)
        RERANK_DEVICE: Device to use (cpu|cuda, default: cpu)

    Returns:
        ReRanker instance if enabled, None otherwise
    """
    enabled = os.getenv("RERANK_ENABLED", "0") in ("1", "true", "True")
    if not enabled:
        return None

    model_name = os.getenv(
        "RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
    )
    device = os.getenv("RERANK_DEVICE", "cpu")

    logger.info(f"Creating ReRanker: model={model_name}, device={device}")

    return ReRanker(
        model_name=model_name, device=device, metrics_registry=metrics_registry
    )
