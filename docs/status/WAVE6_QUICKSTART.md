# Wave 6 Quick Start Guide

## Getting Started with Real Embeddings & Advanced Retrieval

**Prerequisites**: Wave 5 complete (30/30 tests passing)
**Estimated Time**: Phase 1 setup takes ~30 minutes
**Quick Path**: Follow Phase 1 to get real embeddings working immediately

---

## 🚀 Phase 1 Quick Start (Week 1-2)

### Step 1: Install Dependencies

```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\Activate.ps1  # Windows

# Install new packages
pip install sentence-transformers torch nltk tqdm

# Verify installation
python -c "from sentence_transformers import SentenceTransformer; print('✓ OK')"
```

### Step 2: Create Embedding Service

Create `aura_ia_mcp/services/model_gateway/embedding_service.py`:

```python
"""Real embedding service using sentence-transformers."""
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import Optional
from prometheus_client import Histogram, Counter

# Metrics
embedding_latency = Histogram(
    "embedding_latency_seconds",
    "Time to encode embeddings",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)
embedding_count = Counter(
    "embedding_documents_total",
    "Total documents encoded"
)

class EmbeddingService:
    """Sentence-transformer embedding service."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
        normalize: bool = True
    ):
        """
        Initialize embedding model.

        Args:
            model_name: HuggingFace model name
            device: 'cpu' or 'cuda'
            normalize: L2 normalize vectors
        """
        self.model_name = model_name
        self.device = device
        self.normalize = normalize
        self.model: Optional[SentenceTransformer] = None

    def _ensure_loaded(self):
        """Lazy load model on first use."""
        if self.model is None:
            self.model = SentenceTransformer(self.model_name, device=self.device)

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Encode texts to embeddings.

        Args:
            texts: List of text strings

        Returns:
            numpy array of shape (len(texts), embedding_dim)
        """
        self._ensure_loaded()

        with embedding_latency.time():
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False
            )

        if self.normalize:
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        embedding_count.inc(len(texts))
        return embeddings
```

### Step 3: Update Retriever

Modify `aura_ia_mcp/services/model_gateway/retrieval_pipeline.py`:

```python
# Add imports at top
import os
from typing import Optional, Callable, Union
from .embedding_service import EmbeddingService

# Update Retriever.__init__
def __init__(
    self,
    client: QdrantClient,
    embed_fn: Union[Callable[[str], list[float]], EmbeddingService],
    cfg: RetrievalConfig,
    metrics_registry=None
):
    self.client = client

    # Support both legacy callable and new EmbeddingService
    if isinstance(embed_fn, EmbeddingService):
        self.embed_service = embed_fn
        self.embed_fn = None
    else:
        self.embed_fn = embed_fn  # Legacy
        self.embed_service = None

    self.cfg = cfg
    # ... rest of init

# Update retrieve() method
def retrieve(
    self,
    query: str,
    metadata_filter: Optional[dict] = None
) -> list[dict]:
    """Retrieve relevant documents."""
    start = time.time()

    try:
        # Get query embedding
        if self.embed_service:
            # New: real embeddings
            query_vec = self.embed_service.encode([query])[0].tolist()
        elif self.embed_fn:
            # Legacy: pseudo-embeddings
            query_vec = self.embed_fn(query)
        else:
            raise ValueError("No embedding function provided")

        # ... rest of retrieval logic
```

### Step 4: Update Upsert Script

Modify `scripts/qdrant_upsert.py`:

```python
from aura_ia_mcp.services.model_gateway.embedding_service import EmbeddingService
from tqdm import tqdm

def main():
    parser = argparse.ArgumentParser(description="Upsert documents to Qdrant")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="Embedding model")
    parser.add_argument("--device", default="cpu", help="Device: cpu or cuda")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size")
    args = parser.parse_args()

    # Initialize embedding service
    embed_service = EmbeddingService(model_name=args.model, device=args.device)

    # Load documents
    docs = load_jsonl(args.input)

    # Batch upsert with progress bar
    for i in tqdm(range(0, len(docs), args.batch_size), desc="Upserting"):
        batch = docs[i:i + args.batch_size]
        texts = [doc["content"] for doc in batch]

        # Real embeddings
        embeddings = embed_service.encode(texts)

        # Upload to Qdrant
        points = [
            PointStruct(
                id=str(uuid4()),
                vector=emb.tolist(),
                payload=doc
            )
            for doc, emb in zip(batch, embeddings)
        ]
        client.upsert(collection_name=args.collection, points=points)
```

### Step 5: Test Real Embeddings

Create `tests/test_wave6_embedding_service.py`:

```python
"""Test real embedding service."""
import pytest
import numpy as np
from aura_ia_mcp.services.model_gateway.embedding_service import EmbeddingService

def test_embedding_service_encode():
    """Test basic encoding."""
    service = EmbeddingService(model_name="all-MiniLM-L6-v2")

    texts = ["hello world", "machine learning"]
    embeddings = service.encode(texts)

    assert embeddings.shape == (2, 384)  # MiniLM has 384 dimensions
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0)  # Normalized

def test_embedding_similarity():
    """Test semantic similarity."""
    service = EmbeddingService(model_name="all-MiniLM-L6-v2")

    # Similar sentences
    emb1 = service.encode(["The cat sits on the mat"])[0]
    emb2 = service.encode(["A cat is sitting on a mat"])[0]

    # Dissimilar sentence
    emb3 = service.encode(["Quantum physics is complex"])[0]

    sim_similar = np.dot(emb1, emb2)
    sim_different = np.dot(emb1, emb3)

    assert sim_similar > 0.7  # High similarity
    assert sim_different < 0.5  # Low similarity
    assert sim_similar > sim_different  # Sanity check

def test_embedding_batch():
    """Test batch encoding efficiency."""
    service = EmbeddingService(model_name="all-MiniLM-L6-v2")

    texts = [f"Document {i}" for i in range(100)]
    embeddings = service.encode(texts)

    assert embeddings.shape == (100, 384)
    assert np.allclose(np.linalg.norm(embeddings, axis=1), 1.0)
```

Run tests:

```bash
python -m pytest tests/test_wave6_embedding_service.py -v
```

Expected output:

```
test_wave6_embedding_service.py::test_embedding_service_encode PASSED
test_wave6_embedding_service.py::test_embedding_similarity PASSED
test_wave6_embedding_service.py::test_embedding_batch PASSED
```

### Step 6: Re-index Qdrant with Real Embeddings

```bash
# Backup existing collection (optional)
python scripts/backup_qdrant_collection.py --collection aura_docs --output data/backups/

# Re-index with real embeddings
python scripts/qdrant_upsert.py \
    --input data/documents.jsonl \
    --collection aura_docs \
    --model all-MiniLM-L6-v2 \
    --device cpu \
    --batch-size 100
```

### Step 7: Update Configuration

Add to `.env` or environment:

```bash
# Wave 6 - Real Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu
EMBEDDING_NORMALIZE=1
EMBEDDING_BATCH_SIZE=32

# Keep Wave 5 flags
RETRIEVAL_ENABLED=1
RETRIEVAL_COLLECTION=aura_docs
RETRIEVAL_TOP_K=10
QDRANT_URL=http://localhost:6333
```

### Step 8: Validate End-to-End

Test retrieval with real embeddings:

```python
# test_wave6_retrieval_integration.py
from aura_ia_mcp.services.model_gateway.embedding_service import EmbeddingService
from aura_ia_mcp.services.model_gateway.retrieval_pipeline import Retriever, RetrievalConfig
from qdrant_client import QdrantClient

def test_real_embeddings_retrieval():
    """Test retrieval with real embeddings."""
    client = QdrantClient(url="http://localhost:6333")
    embed_service = EmbeddingService(model_name="all-MiniLM-L6-v2")
    cfg = RetrievalConfig(
        collection="aura_docs",
        top_k=5,
        budget_tokens=500
    )

    retriever = Retriever(client, embed_service, cfg)

    # Query with synonyms
    results = retriever.retrieve("machine learning algorithms")

    assert len(results) > 0
    assert all("content" in r for r in results)

    # Check semantic relevance (ML-related content should rank high)
    top_content = results[0]["content"].lower()
    assert any(kw in top_content for kw in ["machine", "learning", "model", "algorithm"])
```

Run:

```bash
python -m pytest tests/test_wave6_retrieval_integration.py -v
```

---

## ✅ Phase 1 Completion Checklist

- [ ] Dependencies installed (`sentence-transformers`, `torch`, `nltk`)
- [ ] `embedding_service.py` created with tests (3/3 passing)
- [ ] `retrieval_pipeline.py` updated to use `EmbeddingService`
- [ ] `qdrant_upsert.py` updated with batch processing
- [ ] Qdrant re-indexed with real embeddings
- [ ] Configuration updated (`.env` or environment variables)
- [ ] Integration test validates real embeddings retrieval
- [ ] All Wave 5 tests still pass (30/30)

**Success Metric**: Retrieval quality noticeably improved (synonyms retrieve relevant docs)

---

## 🎯 What's Next?

Once Phase 1 is complete, proceed to:

- **Phase 2**: Connection pooling & retry logic (Week 3)
- **Phase 3**: Re-ranking with cross-encoder (Week 4-5)
- **Phase 4**: A/B testing framework (Week 6)
- **Phase 5**: Documentation & deployment (Week 7)

See `WAVE6_PLAN.md` for detailed specifications.

---

## 🔧 Troubleshooting

### Model download fails

```bash
# Pre-download model manually
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Out of memory during encoding

```python
# Reduce batch size in embedding_service.py
EMBEDDING_BATCH_SIZE=16  # Default: 32
```

### Slow encoding on CPU

```bash
# Use smaller model
EMBEDDING_MODEL=all-MiniLM-L6-v2  # 384-dim, fast

# Or enable GPU (if available)
EMBEDDING_DEVICE=cuda
```

### Qdrant connection errors

```bash
# Check Qdrant is running
docker ps | grep qdrant

# Restart if needed
docker compose restart qdrant
```

---

## 📚 References

- **Wave 6 Full Plan**: `WAVE6_PLAN.md`
- **Wave 5 Completion**: `WAVE5_COMPLETION.md`
- **PRD Section 8**: Agent implementation rules
- **Sentence-Transformers Docs**: <https://www.sbert.net/>
- **Qdrant API**: <https://qdrant.tech/documentation/>

---

**Quick Win**: Phase 1 delivers immediate retrieval quality improvements with minimal changes. Real embeddings understand synonyms and semantic similarity much better than pseudo-embeddings!

**Next Steps**: After Phase 1 validation, review `WAVE6_PLAN.md` Section 3 for Phase 2-5 implementation.
