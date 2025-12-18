# Wave 1 Integration Guide: RAG + Embeddings + LLM Proxy

## Overview

Wave 1 implements the foundational AI capabilities:

1. **Embeddings Service** - Convert text to semantic vectors
2. **RAG Service** - Store and retrieve documents by semantic similarity
3. **LLM Proxy** - Generate text using multiple backends (Ollama, OpenAI, vLLM)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Client Application                    │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Aura IA MCP (Port 9200)                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ Embeddings  │  │     RAG     │  │ LLM Proxy   │   │
│  │  Service    │  │   Service   │  │   Service   │   │
│  │ /embed/*    │  │   /rag/*    │  │   /llm/*    │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
│         │                │                 │           │
└─────────┼────────────────┼─────────────────┼───────────┘
          │                │                 │
          ▼                ▼                 ▼
  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
  │ Sentence    │  │   Qdrant    │  │   Ollama    │
  │Transformers │  │  VectorDB   │  │  /OpenAI    │
  │ (in-proc)   │  │ (Port 9202) │  │  /vLLM      │
  └─────────────┘  └─────────────┘  └─────────────┘
```

## Service Details

### 1. Embeddings Service (`/embed`)

**Purpose:** Convert text into semantic vector representations.

**Model:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions, fast, efficient)

**Endpoints:**

#### `POST /embed/vectors`

Generate embeddings for text(s).

**Request:**

```json
{
  "texts": ["Hello world", "Machine learning is amazing"],
  "normalize": true
}
```

**Response:**

```json
{
  "embeddings": [
    [0.123, -0.456, 0.789, ...],
    [0.234, -0.567, 0.890, ...]
  ],
  "model": "sentence-transformers/all-MiniLM-L6-v2",
  "dimensions": 384
}
```

#### `GET /embed/health`

Health check.

**Response:**

```json
{
  "status": "healthy",
  "model": "sentence-transformers/all-MiniLM-L6-v2",
  "dimensions": 384,
  "device": "cuda:0"
}
```

---

### 2. RAG Service (`/rag`)

**Purpose:** Store and retrieve documents using vector similarity search.

**Backend:** Qdrant vector database

**Endpoints:**

#### `POST /rag/upsert`

Store documents with their embeddings.

**Request:**

```json
{
  "documents": [
    {
      "id": 1,
      "text": "Paris is the capital of France",
      "vector": [0.123, -0.456, ...],
      "metadata": {"source": "geography", "timestamp": "2025-11-30"}
    },
    {
      "id": 2,
      "text": "Python is a programming language",
      "vector": [0.234, -0.567, ...],
      "metadata": {"source": "programming"}
    }
  ]
}
```

**Response:**

```json
{
  "status": "success",
  "upserted": 2,
  "collection": "aura_documents"
}
```

#### `POST /rag/query`

Search for similar documents.

**Request:**

```json
{
  "query_vector": [0.123, -0.456, ...],
  "top_k": 5,
  "score_threshold": 0.7
}
```

**Response:**

```json
{
  "results": [
    {
      "id": 1,
      "score": 0.95,
      "text": "Paris is the capital of France",
      "metadata": {"source": "geography"}
    },
    {
      "id": 3,
      "score": 0.82,
      "text": "London is the capital of UK",
      "metadata": {"source": "geography"}
    }
  ],
  "query_length": 384,
  "top_k": 5
}
```

#### `GET /rag/health`

Health check.

**Response:**

```json
{
  "status": "healthy",
  "collection": "aura_documents",
  "points_count": 1024,
  "vector_size": 384
}
```

---

### 3. LLM Proxy Service (`/llm`)

**Purpose:** Generate text using multiple LLM backends.

**Supported Backends:**

- `ollama` - Local Ollama server (default)
- `openai` - OpenAI API
- `vllm` - vLLM inference server

**Endpoints:**

#### `POST /llm/generate`

Generate text completion.

**Request:**

```json
{
  "prompt": "Explain what RAG is in one sentence",
  "model": "llama3.2:1b",
  "max_tokens": 128,
  "temperature": 0.7,
  "backend": "ollama"
}
```

**Response:**

```json
{
  "generated_text": "RAG (Retrieval-Augmented Generation) is a technique that enhances language models by retrieving relevant documents before generating responses.",
  "model": "llama3.2:1b",
  "backend": "ollama",
  "prompt_tokens": 12,
  "completion_tokens": 28
}
```

#### `GET /llm/health`

Health check for all backends.

**Response:**

```json
{
  "status": "healthy",
  "backends": {
    "ollama": "healthy",
    "openai": "configured",
    "vllm": "unavailable"
  }
}
```

---

## Complete Integration Example

Here's a full RAG pipeline: **ingest documents → query → generate answer**.

### Python Example

```python
import httpx
import asyncio

BASE_URL = "http://localhost:9200"

async def rag_pipeline():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Generate embeddings for documents
        print("Step 1: Generating embeddings...")
        embed_response = await client.post(
            f"{BASE_URL}/embed/vectors",
            json={
                "texts": [
                    "Paris is the capital of France",
                    "Python is a programming language",
                    "RAG combines retrieval and generation"
                ],
                "normalize": True
            }
        )
        embeddings = embed_response.json()["embeddings"]
        print(f"✓ Generated {len(embeddings)} embeddings")

        # Step 2: Store documents in RAG
        print("\nStep 2: Storing documents in RAG...")
        documents = [
            {
                "id": i + 1,
                "text": text,
                "vector": vector,
                "metadata": {"source": "example"}
            }
            for i, (text, vector) in enumerate(zip(
                ["Paris is the capital of France",
                 "Python is a programming language",
                 "RAG combines retrieval and generation"],
                embeddings
            ))
        ]

        upsert_response = await client.post(
            f"{BASE_URL}/rag/upsert",
            json={"documents": documents}
        )
        print(f"✓ Upserted {upsert_response.json()['upserted']} documents")

        # Step 3: Query with user question
        print("\nStep 3: Querying RAG with user question...")
        query = "What is the capital of France?"

        # Generate query embedding
        query_embed = await client.post(
            f"{BASE_URL}/embed/vectors",
            json={"texts": [query], "normalize": True}
        )
        query_vector = query_embed.json()["embeddings"][0]

        # Search RAG
        rag_response = await client.post(
            f"{BASE_URL}/rag/query",
            json={"query_vector": query_vector, "top_k": 2}
        )
        results = rag_response.json()["results"]
        print(f"✓ Found {len(results)} relevant documents")

        # Step 4: Generate answer using retrieved context
        print("\nStep 4: Generating answer with LLM...")
        context = "\n".join([r["text"] for r in results])
        prompt = f"""Context:
{context}

Question: {query}

Answer:"""

        llm_response = await client.post(
            f"{BASE_URL}/llm/generate",
            json={
                "prompt": prompt,
                "model": "llama3.2:1b",
                "max_tokens": 100,
                "backend": "ollama"
            }
        )
        answer = llm_response.json()["generated_text"]
        print(f"✓ Generated answer:\n{answer}")

asyncio.run(rag_pipeline())
```

### cURL Examples

```bash
# 1. Generate embeddings
curl -X POST http://localhost:9200/embed/vectors \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Hello world"], "normalize": true}'

# 2. Store in RAG
curl -X POST http://localhost:9200/rag/upsert \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [{
      "id": 1,
      "text": "Hello world",
      "vector": [0.1, 0.2, ...],
      "metadata": {}
    }]
  }'

# 3. Query RAG
curl -X POST http://localhost:9200/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query_vector": [0.1, 0.2, ...],
    "top_k": 5
  }'

# 4. Generate with LLM
curl -X POST http://localhost:9200/llm/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain RAG",
    "model": "llama3.2:1b",
    "backend": "ollama"
  }'
```

---

## Configuration

### Environment Variables

```bash
# Qdrant connection
export QDRANT_URL="http://localhost:9202"

# Ollama connection
export OLLAMA_URL="http://localhost:11434"

# OpenAI (optional)
export OPENAI_API_KEY="sk-..."

# vLLM (optional)
export VLLM_URL="http://localhost:9204"
```

### Docker Compose Setup

Add to `docker-compose.yml`:

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "9202:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  qdrant_data:
```

---

## Performance Considerations

### Embeddings Service

- **Model Loading:** ~200MB, loaded on first request (cached)
- **Throughput:** ~500 texts/sec on CPU, ~2000/sec on GPU
- **Latency:** 5-20ms per text (batch processing recommended)

### RAG Service

- **Qdrant Performance:** 1000+ queries/sec with 1M vectors
- **Memory:** ~4GB per 1M vectors (384 dims)
- **Disk:** ~2GB per 1M vectors

### LLM Proxy

- **Ollama:** Depends on model size and hardware
  - Small models (1B-3B): 10-50 tokens/sec on CPU
  - Medium models (7B-13B): Requires GPU for reasonable speed
- **OpenAI API:** Rate limited by plan
- **vLLM:** High throughput for batch inference

---

## Metrics & Monitoring

All services expose metrics compatible with the [metrics taxonomy](metrics_taxonomy.md):

```
# Embeddings
embedding_requests_total{status="success"}
embedding_latency_seconds{p95="0.015"}

# RAG
rag_queries_total{source="aura_documents"}
rag_latency_seconds{p95="0.025"}
rag_topk_mean{source="aura_documents"}

# LLM
model_inference_requests_total{model="llama3.2",backend="ollama"}
tokens_in_total{model="llama3.2"}
tokens_out_total{model="llama3.2"}
```

---

## Troubleshooting

### Embeddings Service

**Issue:** Model download slow

- **Solution:** Pre-download model: `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"`

**Issue:** Out of memory

- **Solution:** Reduce batch size or use CPU: `device='cpu'`

### RAG Service

**Issue:** Connection refused to Qdrant

- **Solution:** Start Qdrant: `docker run -p 9202:6333 qdrant/qdrant`

**Issue:** Low relevance scores

- **Solution:** Ensure embeddings are normalized, increase top_k, lower score_threshold

### LLM Proxy

**Issue:** Ollama not responding

- **Solution:** Start Ollama: `ollama serve` and pull model: `ollama pull llama3.2:1b`

**Issue:** OpenAI authentication failed

- **Solution:** Set `OPENAI_API_KEY` environment variable

---

## Next Steps

With Wave 1 complete, the following capabilities are now available:

✅ Semantic search across documents
✅ Context-aware question answering
✅ Multi-backend LLM generation
✅ Production-ready health checks

**Wave 2 (SICD Training Loop)** will use these services for autonomous code improvement with retrieval-augmented generation.
