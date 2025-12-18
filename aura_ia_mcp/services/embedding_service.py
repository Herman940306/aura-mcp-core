"""Embeddings Service with sentence-transformers."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/embed", tags=["embeddings"])

# Global model (lazy loaded)
_model: SentenceTransformer | None = None
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim, fast


class EmbedRequest(BaseModel):
    """Request to generate embeddings."""

    texts: list[str] = Field(..., description="Texts to embed")
    normalize: bool = Field(
        True, description="Normalize vectors to unit length"
    )


class EmbedResponse(BaseModel):
    """Embedding response."""

    embeddings: list[list[float]]
    model: str
    dimensions: int


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """Get or load the embedding model (cached)."""
    from sentence_transformers import SentenceTransformer

    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded successfully")
    return _model


@router.post("/vectors", response_model=EmbedResponse)
async def generate_embeddings(request: EmbedRequest):
    """Generate embeddings for input texts.

    Returns normalized vectors by default for cosine similarity.
    """
    try:
        model = get_model()

        # Generate embeddings
        embeddings = model.encode(
            request.texts,
            normalize_embeddings=request.normalize,
            show_progress_bar=False,
        )

        # Convert to list of lists
        embeddings_list = embeddings.tolist()

        return EmbedResponse(
            embeddings=embeddings_list,
            model=MODEL_NAME,
            dimensions=len(embeddings_list[0]) if embeddings_list else 0,
        )

    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def embeddings_health():
    """Health check for embeddings service."""
    try:
        model = get_model()
        test_embedding = model.encode(
            ["health check"], show_progress_bar=False
        )

        return {
            "status": "healthy",
            "model": MODEL_NAME,
            "dimensions": len(test_embedding[0]),
            "device": str(model.device),
        }
    except Exception as e:
        logger.error(f"Embeddings health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


class SingleEmbedRequest(BaseModel):
    """Request for single text embedding (convenience endpoint)."""

    text: str = Field(..., description="Text to embed")
    normalize: bool = Field(True, description="Normalize vector")


class SingleEmbedResponse(BaseModel):
    """Single embedding response."""

    embedding: list[float]
    model: str
    dimensions: int


def register(app: FastAPI, settings) -> None:
    """Register embeddings service routes."""
    app.include_router(router)

    # Also register convenience /embed endpoint at root for tests
    @app.post(
        "/embed", response_model=SingleEmbedResponse, tags=["embeddings"]
    )
    async def embed_single_text(request: SingleEmbedRequest):
        """Generate embedding for a single text.

        Convenience endpoint - wraps /embed/vectors for single-text use.
        """
        try:
            model = get_model()
            embedding = model.encode(
                [request.text],
                normalize_embeddings=request.normalize,
                show_progress_bar=False,
            )
            embedding_list = embedding[0].tolist()

            return SingleEmbedResponse(
                embedding=embedding_list,
                model=MODEL_NAME,
                dimensions=len(embedding_list),
            )
        except Exception as e:
            logger.error(f"Single embedding failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    logger.info("Embeddings service registered")
