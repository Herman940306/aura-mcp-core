"""Real embedding service using sentence-transformers.

Wave 6 Phase 1: Replace pseudo-embeddings with production sentence-transformers.
"""

import os
import time

import numpy as np
from prometheus_client import CollectorRegistry, Counter, Histogram
from sentence_transformers import SentenceTransformer

# Default metrics (can be overridden with custom registry)
_default_embedding_latency = Histogram(
    "embedding_latency_seconds",
    "Time to encode embeddings",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
)
_default_embedding_count = Counter(
    "embedding_documents_total", "Total documents encoded"
)


class EmbeddingService:
    """Sentence-transformer embedding service.

    Features:
    - Lazy model loading (downloads on first use)
    - Batch encoding support
    - L2 normalization for cosine similarity
    - Device management (CPU/CUDA)
    - Prometheus metrics
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        normalize: bool = True,
        metrics_registry: CollectorRegistry | None = None,
    ):
        """Initialize embedding service.

        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2, 384-dim)
            device: 'cpu' or 'cuda'
            normalize: L2 normalize vectors for cosine similarity
            metrics_registry: Optional Prometheus registry (for test isolation)
        """
        self.model_name = model_name
        self.device = device
        self.normalize = normalize
        self.model: SentenceTransformer | None = None

        # Metrics (use custom registry if provided, otherwise default)
        if metrics_registry is not None:
            self.embedding_latency = Histogram(
                "embedding_latency_seconds",
                "Time to encode embeddings",
                buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
                registry=metrics_registry,
            )
            self.embedding_count = Counter(
                "embedding_documents_total",
                "Total documents encoded",
                registry=metrics_registry,
            )
        else:
            self.embedding_latency = _default_embedding_latency
            self.embedding_count = _default_embedding_count

    def _ensure_loaded(self):
        """Lazy load model on first use.

        Downloads model from HuggingFace Hub if not cached (~90MB for MiniLM).
        """
        if self.model is None:
            self.model = SentenceTransformer(
                self.model_name, device=self.device
            )

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> np.ndarray:
        """Encode texts to embeddings.

        Args:
            texts: List of text strings
            batch_size: Batch size for encoding (default: 32)
            show_progress: Show tqdm progress bar

        Returns:
            numpy array of shape (len(texts), embedding_dim)
            - all-MiniLM-L6-v2: 384 dimensions
            - all-mpnet-base-v2: 768 dimensions
        """
        if not texts:
            return np.array([])

        self._ensure_loaded()

        start = time.time()
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=show_progress,
            normalize_embeddings=False,  # We handle normalization below
        )

        # L2 normalization for cosine similarity
        if self.normalize:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            # Avoid division by zero
            norms = np.where(norms == 0, 1, norms)
            embeddings = embeddings / norms

        # Metrics
        elapsed = time.time() - start
        self.embedding_latency.observe(elapsed)
        self.embedding_count.inc(len(texts))

        return embeddings

    def encode_single(self, text: str) -> list[float]:
        """Encode single text to embedding (convenience method).

        Args:
            text: Single text string

        Returns:
            List of floats (embedding vector)
        """
        embedding = self.encode([text])[0]
        return embedding.tolist()

    def get_dimension(self) -> int:
        """Get embedding dimension.

        Returns:
            Embedding dimension (e.g., 384 for MiniLM, 768 for MPNet)
        """
        self._ensure_loaded()
        return self.model.get_sentence_embedding_dimension()


def create_embedding_service_from_env() -> EmbeddingService:
    """Create EmbeddingService from environment variables.

    Environment variables:
        EMBEDDING_MODEL: Model name (default: all-MiniLM-L6-v2)
        EMBEDDING_DEVICE: Device (default: cpu)
        EMBEDDING_NORMALIZE: Normalize vectors (default: 1)

    Returns:
        Configured EmbeddingService instance
    """
    model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    device = os.getenv("EMBEDDING_DEVICE", "cpu")
    normalize = os.getenv("EMBEDDING_NORMALIZE", "1") == "1"

    return EmbeddingService(
        model_name=model_name, device=device, normalize=normalize
    )
