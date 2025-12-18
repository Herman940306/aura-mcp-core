from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any

from prometheus_client import Counter, Histogram
from prometheus_client.registry import CollectorRegistry

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import FieldCondition, Filter, MatchValue
except Exception:  # pragma: no cover - optional in dev
    QdrantClient = None  # type: ignore
    Filter = FieldCondition = MatchValue = object  # type: ignore

# Wave 6: Import EmbeddingService, QdrantConnectionPool, ReRanker, QueryExpander
try:
    from .embedding_service import EmbeddingService
except ImportError:
    EmbeddingService = None  # type: ignore

try:
    from .qdrant_pool import QdrantConnectionPool
except ImportError:
    QdrantConnectionPool = None  # type: ignore

try:
    from .reranker import ReRanker
except ImportError:
    ReRanker = None  # type: ignore

try:
    from .query_expander import QueryExpander
except ImportError:
    QueryExpander = None  # type: ignore


@dataclass
class RetrievalConfig:
    collection: str
    top_k: int = 5
    score_threshold: float = 0.2
    retrieval_budget_tokens: int = (
        1024  # cap retrieval window to a fraction of total
    )
    metadata_filter: dict[str, Any] | None = None
    # Wave 6 Phase 3: Re-ranking and query expansion
    rerank_enabled: bool = False
    rerank_top_k: int = 50  # Retrieve more candidates for re-ranking
    expand_enabled: bool = False


class Retriever:
    def __init__(
        self,
        client: QdrantClient | QdrantConnectionPool | None,
        embed_fn: Callable[[str], list[float]] | EmbeddingService,
        cfg: RetrievalConfig,
        reranker: ReRanker | None = None,
        query_expander: QueryExpander | None = None,
        metrics_registry: CollectorRegistry | None = None,
    ):
        """Initialize Retriever with support for both legacy and Wave 6 embeddings.

        Args:
            client: QdrantClient OR QdrantConnectionPool (Wave 6 Phase 2)
            embed_fn: Legacy callable OR EmbeddingService instance (Wave 6)
            cfg: Retrieval configuration
            reranker: Optional ReRanker for cross-encoder re-scoring (Wave 6 Phase 3)
            query_expander: Optional QueryExpander for query variants (Wave 6 Phase 3)
            metrics_registry: Optional Prometheus registry for test isolation
        """
        # Wave 6 Phase 2: Support both single client and connection pool
        if QdrantConnectionPool and isinstance(client, QdrantConnectionPool):
            self.pool: QdrantConnectionPool | None = client
            self.client: QdrantClient | None = None
        else:
            self.client = client  # type: ignore
            self.pool = None

        # Wave 6: Support both legacy callable and new EmbeddingService
        if EmbeddingService and isinstance(embed_fn, EmbeddingService):
            self.embed_service: EmbeddingService | None = embed_fn
            self.embed_fn: Callable[[str], list[float]] | None = None
        else:
            self.embed_fn = embed_fn  # type: ignore
            self.embed_service = None

        # Wave 6 Phase 3: Re-ranker and query expander
        self.reranker = reranker
        self.query_expander = query_expander

        self.cfg = cfg
        self._m_latency = Histogram(
            "retrieval_latency_seconds",
            "Latency of retrieval queries",
            buckets=(0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0),
            registry=metrics_registry,
        )
        self._m_hits = Counter(
            "retrieval_hits_total",
            "Number of retrieved docs (post-filter)",
            ["collection"],
            registry=metrics_registry,
        )
        self._audit_enabled = os.environ.get("RETRIEVAL_AUDIT_LOG", "0") in (
            "1",
            "true",
            "True",
        )
        self._audit_path = os.environ.get(
            "RETRIEVAL_AUDIT_PATH",
            os.path.join("logs", "security_audit.jsonl"),
        )

    def _audit_failure(self, err: Exception, query: str):
        if not self._audit_enabled:
            return
        try:
            rec = {
                "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "event": "retrieval_failure",
                "collection": self.cfg.collection,
                "error": type(err).__name__,
                "message": str(err),
                "query_preview": query[:160],
            }
            os.makedirs(os.path.dirname(self._audit_path), exist_ok=True)
            with open(self._audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            # Do not propagate audit logging errors
            pass

    def _build_filter(self) -> Filter | None:
        if not self.cfg.metadata_filter or Filter is object:
            return None
        conditions = []
        for key, val in self.cfg.metadata_filter.items():
            conditions.append(
                FieldCondition(key=key, match=MatchValue(value=val))
            )
        return Filter(must=conditions)

    def retrieve(self, query: str) -> list[dict[str, Any]]:
        """Top-K hybrid retrieval: cosine similarity + simple BM25-like boost.
        Returns list of {text, score, metadata}.

        Wave 6: Supports both legacy embed_fn and EmbeddingService.
        Wave 6 Phase 2: Supports both single client and connection pool with retry.
        Wave 6 Phase 3: Supports query expansion and re-ranking.
        """
        # Wave 6 Phase 3: Query expansion (if enabled)
        if self.cfg.expand_enabled and self.query_expander:
            query_variants = self.query_expander.expand(query)
            # Retrieve for each variant and merge results
            all_docs: list[dict[str, Any]] = []
            seen_texts: set[str] = set()

            for variant in query_variants:
                docs = self._retrieve_single_query(variant)
                # Deduplicate by text content
                for doc in docs:
                    text = doc.get("text", "")
                    if text not in seen_texts:
                        seen_texts.add(text)
                        all_docs.append(doc)

            # Sort by score (descending)
            all_docs.sort(key=lambda x: x.get("score", 0.0), reverse=True)

            # Apply re-ranking if enabled
            if self.cfg.rerank_enabled and self.reranker:
                all_docs = self.reranker.rerank(
                    query=query,  # Use original query for re-ranking
                    documents=all_docs[: self.cfg.rerank_top_k],
                    top_k=self.cfg.top_k,
                )
            else:
                all_docs = all_docs[: self.cfg.top_k]

            # Truncate to budget
            return _truncate_to_budget(
                all_docs, self.cfg.retrieval_budget_tokens
            )

        # No expansion: standard retrieval
        docs = self._retrieve_single_query(query)

        # Wave 6 Phase 3: Re-ranking (if enabled)
        if self.cfg.rerank_enabled and self.reranker:
            # Retrieve more candidates for re-ranking
            docs = self.reranker.rerank(
                query=query,
                documents=docs[: self.cfg.rerank_top_k],
                top_k=self.cfg.top_k,
            )

        return docs

    def _retrieve_single_query(self, query: str) -> list[dict[str, Any]]:
        """Execute retrieval for a single query (internal).

        Handles connection pool vs single client dispatch.
        """
        # Wave 6 Phase 2: Use connection pool with retry if available
        if self.pool:
            return self._retrieve_with_pool(query)

        # Legacy: Use single client
        if self.client is None:
            # Graceful fallback when Qdrant is unavailable or not configured
            return []

        t0 = perf_counter()
        try:
            # Wave 6: Get query embedding (supports both legacy and new)
            if self.embed_service:
                qvec = self.embed_service.encode_single(query)
            elif self.embed_fn:
                qvec = self.embed_fn(query)
            else:
                raise ValueError("No embedding function provided")

            flt = self._build_filter()
            # vector search using query_points API (qdrant-client >=1.6.0)
            res = self.client.query_points(
                collection_name=self.cfg.collection,
                query=qvec,
                limit=self.cfg.top_k,
                query_filter=flt,
            ).points
        except Exception as err:
            # Any retrieval error should not break chat; fall back to no context
            self._audit_failure(err=err, query=query)
            self._m_latency.observe(perf_counter() - t0)
            return []
        docs: list[dict[str, Any]] = []
        for p in res:
            # Support both "text" and "content" keys for backward compatibility
            text = p.payload.get("text") or p.payload.get("content", "")
            score = float(p.score or 0.0)
            bm25 = _bm25_like(query, text)
            composite = 0.7 * score + 0.3 * bm25
            if composite >= self.cfg.score_threshold:
                # Include content field if present for test compatibility
                doc_result = {
                    "text": text,
                    "score": composite,
                    "metadata": p.payload,
                }
                if "content" in p.payload:
                    doc_result["content"] = p.payload["content"]
                docs.append(doc_result)
        # truncate to retrieval_budget_tokens
        docs = _truncate_to_budget(docs, self.cfg.retrieval_budget_tokens)
        self._m_hits.labels(collection=self.cfg.collection).inc(len(docs))
        self._m_latency.observe(perf_counter() - t0)
        return docs

    def _retrieve_with_pool(self, query: str) -> list[dict[str, Any]]:
        """Execute retrieval with connection pool and retry logic.

        Wave 6 Phase 2: Production-grade retrieval with automatic retry and circuit breaker.
        """
        if not self.pool:
            return []

        t0 = perf_counter()

        # Get query embedding (outside pool operation)
        try:
            if self.embed_service:
                qvec = self.embed_service.encode_single(query)
            elif self.embed_fn:
                qvec = self.embed_fn(query)
            else:
                raise ValueError("No embedding function provided")
        except Exception as err:
            self._audit_failure(err=err, query=query)
            self._m_latency.observe(perf_counter() - t0)
            return []

        # Execute search with pool + retry
        def _search_operation(client: QdrantClient):
            flt = self._build_filter()
            return client.query_points(
                collection_name=self.cfg.collection,
                query=qvec,
                limit=self.cfg.top_k,
                query_filter=flt,
            ).points

        try:
            res = self.pool.execute_with_retry(
                operation=_search_operation, operation_name="qdrant_search"
            )
        except Exception as err:
            self._audit_failure(err=err, query=query)
            self._m_latency.observe(perf_counter() - t0)
            return []

        # Process results (same as legacy)
        docs: list[dict[str, Any]] = []
        for p in res:
            # Support both "text" and "content" keys for backward compatibility
            text = p.payload.get("text") or p.payload.get("content", "")
            score = float(p.score or 0.0)
            bm25 = _bm25_like(query, text)
            composite = 0.7 * score + 0.3 * bm25
            if composite >= self.cfg.score_threshold:
                # Include content field if present for test compatibility
                doc_result = {
                    "text": text,
                    "score": composite,
                    "metadata": p.payload,
                }
                if "content" in p.payload:
                    doc_result["content"] = p.payload["content"]
                docs.append(doc_result)

        # Truncate to retrieval_budget_tokens
        docs = _truncate_to_budget(docs, self.cfg.retrieval_budget_tokens)
        self._m_hits.labels(collection=self.cfg.collection).inc(len(docs))
        self._m_latency.observe(perf_counter() - t0)
        return docs


def _bm25_like(q: str, d: str) -> float:
    q_terms = q.lower().split()
    d_terms = d.lower().split()
    if not d_terms:
        return 0.0
    score = 0.0
    for t in q_terms:
        tf = d_terms.count(t)
        score += tf / (1 + math.log(1 + len(d_terms)))
    return min(score, 1.0)


def _truncate_to_budget(
    docs: list[dict[str, Any]], budget_tokens: int
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    used = 0
    for d in sorted(docs, key=lambda x: x["score"], reverse=True):
        est = (len(d["text"]) + 3) // 4
        if used + est > budget_tokens:
            break
        out.append(d)
        used += est
    return out
