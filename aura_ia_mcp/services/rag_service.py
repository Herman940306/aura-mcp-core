"""RAG Service with Qdrant vector database integration."""

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])

# Global client (initialized on first use)
_qdrant_client: QdrantClient | None = None
COLLECTION_NAME = "aura_documents"
VECTOR_SIZE = 768  # nomic-embed-text (v1.5) default


class UpsertRequest(BaseModel):
    """Request to upsert documents."""

    documents: list[dict[str, Any]] = Field(
        ..., description="Documents with 'id', 'text', and optional 'metadata'"
    )


class QueryRequest(BaseModel):
    """Request to query similar documents."""

    query_vector: list[float] = Field(
        ..., description="Query embedding vector"
    )
    top_k: int = Field(5, description="Number of results to return")
    score_threshold: float | None = Field(
        None, description="Minimum similarity score"
    )


class UpsertTextRequest(BaseModel):
    """Request to upsert raw texts (server-side embedding)."""

    items: list[dict[str, Any]] = Field(
        ..., description="List of items with 'id', 'text', optional 'metadata'"
    )


def get_qdrant_client(settings) -> QdrantClient:
    """Get or create Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        # Use env vars or Docker network hostname (internal port is 6333)
        qdrant_host = os.getenv("QDRANT_HOST", "aura-ia-rag")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        qdrant_url = getattr(
            settings, "qdrant_url", f"http://{qdrant_host}:{qdrant_port}"
        )
        _qdrant_client = QdrantClient(url=qdrant_url)
        logger.info(f"Connected to Qdrant at {qdrant_url}")

        # Ensure collection exists
        try:
            _qdrant_client.get_collection(COLLECTION_NAME)
            logger.info(f"Collection '{COLLECTION_NAME}' exists")
        except Exception:
            logger.info(f"Creating collection '{COLLECTION_NAME}'")
            _qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=VECTOR_SIZE, distance=Distance.COSINE
                ),
            )
    return _qdrant_client


async def embed_texts(texts: list[str], settings) -> list[list[float]]:
    """Embed texts using Ollama /api/embeddings (with fallback to legacy API)."""
    base_url = getattr(
        settings,
        "ollama_url",
        os.getenv("OLLAMA_BASE_URL", "http://aura-ia-ollama:11434"),
    )
    model = getattr(
        settings,
        "embedding_model",
        os.getenv("EMBEDDING_MODEL", "phi3.5:3.8b"),
    )

    logger.info(
        f"Ollama embedding request: model={model}, base_url={base_url}"
    )

    # Debug: Resolve hostname
    try:
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(base_url)
        if parsed.hostname:
            resolved_ip = socket.gethostbyname(parsed.hostname)
            logger.info(f"Resolved {parsed.hostname} to {resolved_ip}")
        else:
            logger.warning(f"Could not parse hostname from {base_url}")
    except Exception as e:
        logger.error(f"Failed to resolve Ollama hostname: {e}")

    vectors = []
    # Disable proxy env vars for this client to ensure direct container connection
    # and add detailed error handling
    async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
        for text in texts:
            try:
                # Try new /api/embed endpoint first
                response = await client.post(
                    f"{base_url}/api/embed",
                    json={"model": model, "input": text},
                    headers={"Content-Type": "application/json"},
                )

                # Check directly for 404 to trigger fallback
                if response.status_code == 404:
                    logger.warning(
                        f"/api/embed not found at {base_url}, falling back to /api/embeddings"
                    )
                    response = await client.post(
                        f"{base_url}/api/embeddings",
                        json={"model": model, "prompt": text},
                        headers={"Content-Type": "application/json"},
                    )

                response.raise_for_status()
                data = response.json()

                # Handle both response formats
                # /api/embed returns {"embeddings": [[...]]}
                # /api/embeddings returns {"embedding": [...]}
                embeddings = data.get("embeddings")
                embedding = data.get("embedding")

                if embeddings and len(embeddings) > 0:
                    vectors.append(embeddings[0])
                elif embedding:
                    vectors.append(embedding)
                else:
                    raise RuntimeError(
                        f"No embedding returned for text: {text[:50]}..."
                    )
            except httpx.ConnectError as e:
                # Log detailed connection error but re-raise as RuntimeError for higher-level handling
                logger.error(f"Connection failed to {base_url}: {e!r}")
                raise RuntimeError(
                    f"Failed to connect to Ollama at {base_url}: {e}"
                )
            except Exception as e:
                logger.error(f"Error during embedding: {e!r}")
                raise

    if not vectors:
        raise RuntimeError("No embeddings returned from Ollama")
    return vectors


@router.post("/upsert")
async def upsert_documents(request: UpsertRequest):
    """Upsert documents into vector database.

    Expects documents with:
    - id: unique identifier
    - vector: pre-computed embedding (list of floats)
    - text: original text (stored as payload)
    - metadata: optional additional fields
    """
    try:
        from ..core.config import get_settings

        settings = get_settings()
        client = get_qdrant_client(settings)

        points = []
        for doc in request.documents:
            if "vector" not in doc or "id" not in doc:
                raise HTTPException(
                    status_code=400,
                    detail="Each document must have 'id' and 'vector'",
                )

            points.append(
                PointStruct(
                    id=doc["id"],
                    vector=doc["vector"],
                    payload={
                        "text": doc.get("text", ""),
                        "metadata": doc.get("metadata", {}),
                    },
                )
            )

        client.upsert(collection_name=COLLECTION_NAME, points=points)

        return {
            "status": "success",
            "upserted": len(points),
            "collection": COLLECTION_NAME,
        }

    except Exception as e:
        logger.error(f"RAG upsert failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upsert_texts")
async def upsert_texts(request: UpsertTextRequest):
    """Upsert raw texts; server will embed via Ollama then store in Qdrant."""
    try:
        from ..core.config import get_settings

        settings = get_settings()
        client = get_qdrant_client(settings)

        texts = []
        ids = []
        metas = []
        for item in request.items:
            if "id" not in item or "text" not in item:
                raise HTTPException(
                    status_code=400,
                    detail="Each item must have 'id' and 'text'",
                )
            ids.append(item["id"])
            texts.append(item["text"])
            metas.append(item.get("metadata", {}))

        vectors = await embed_texts(texts, settings)
        if len(vectors) != len(ids):
            raise HTTPException(
                status_code=500,
                detail="Embedding count mismatch",
            )

        points = [
            PointStruct(
                id=ids[i],
                vector=vectors[i],
                payload={"text": texts[i], "metadata": metas[i]},
            )
            for i in range(len(ids))
        ]

        client.upsert(collection_name=COLLECTION_NAME, points=points)

        return {
            "status": "success",
            "upserted": len(points),
            "collection": COLLECTION_NAME,
            "embedding_model": getattr(
                settings, "embedding_model", "nomic-embed-text"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG upsert_texts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_documents(request: QueryRequest):
    """Query similar documents using vector search."""
    try:
        from ..core.config import get_settings

        settings = get_settings()
        client = get_qdrant_client(settings)

        search_result = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=request.query_vector,
            limit=request.top_k,
            score_threshold=request.score_threshold,
        )

        results = [
            {
                "id": hit.id,
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "metadata": hit.payload.get("metadata", {}),
            }
            for hit in search_result
        ]

        return {
            "results": results,
            "query_length": len(request.query_vector),
            "top_k": request.top_k,
        }

    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def rag_health():
    """Health check for RAG service."""
    try:
        from ..core.config import get_settings

        settings = get_settings()
        client = get_qdrant_client(settings)
        collection_info = client.get_collection(COLLECTION_NAME)

        return {
            "status": "healthy",
            "collection": COLLECTION_NAME,
            "points_count": collection_info.points_count,
            "vector_size": VECTOR_SIZE,
        }
    except Exception as e:
        logger.error(f"RAG health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


def register(app: FastAPI, settings) -> None:
    """Register RAG service routes."""
    app.include_router(router)
    logger.info("RAG service registered")
