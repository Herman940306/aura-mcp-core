import argparse
import json
import os
import sys
from pathlib import Path

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
except Exception:
    QdrantClient = None
    PointStruct = None
    VectorParams = None
    Distance = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore

import hashlib

# Wave 6: Try to import EmbeddingService
try:
    # Add parent directory to path for import
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from aura_ia_mcp.services.model_gateway.embedding_service import (
        EmbeddingService,
    )
except ImportError:
    EmbeddingService = None  # type: ignore


def simple_embed(text: str, dim: int = 384) -> list[float]:
    # Deterministic pseudo-embedding based on SHA256; replace with real model
    h = hashlib.sha256(text.encode("utf-8")).digest()
    # Repeat bytes to fill dim
    data = (h * ((dim // len(h)) + 1))[:dim]
    return [b / 255.0 for b in data]


def ensure_collection(client: QdrantClient, collection: str, vector_size: int):
    existing = client.get_collections()
    names = {c.name for c in existing.collections}
    if collection not in names:
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=vector_size, distance=Distance.COSINE
            ),
        )


def load_jsonl(path: Path) -> list[dict]:
    items = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def main():
    parser = argparse.ArgumentParser(
        description="Upsert JSONL docs into Qdrant (Wave 6: supports real embeddings)"
    )
    parser.add_argument(
        "jsonl",
        type=Path,
        help="Path to JSONL with docs {id?, text, namespace?}",
    )
    parser.add_argument("collection", type=str, help="Qdrant collection name")
    parser.add_argument(
        "--url",
        dest="url",
        default=os.environ.get("QDRANT_URL", "http://localhost:9202"),
    )
    parser.add_argument(
        "--vector-size", dest="vector_size", type=int, default=384
    )
    # Wave 6: New arguments
    parser.add_argument(
        "--model",
        dest="model",
        default="",
        help="Embedding model name (Wave 6, e.g., all-MiniLM-L6-v2). If empty, uses pseudo-embeddings.",
    )
    parser.add_argument(
        "--device",
        dest="device",
        default="cpu",
        help="Device for embeddings: cpu or cuda (default: cpu)",
    )
    parser.add_argument(
        "--batch-size",
        dest="batch_size",
        type=int,
        default=100,
        help="Batch size for upsert (default: 100)",
    )
    args = parser.parse_args()

    if QdrantClient is None:
        raise RuntimeError(
            "qdrant-client not available. Install it in requirements."
        )

    client = QdrantClient(args.url)
    ensure_collection(client, args.collection, args.vector_size)

    items = load_jsonl(args.jsonl)

    # Wave 6: Initialize embedding service if model specified
    embed_service = None
    if args.model:
        if EmbeddingService is None:
            print(
                "ERROR: EmbeddingService not available. Install sentence-transformers."
            )
            return
        print(f"Loading embedding model: {args.model} (device: {args.device})")
        embed_service = EmbeddingService(
            model_name=args.model, device=args.device, normalize=True
        )
        # Verify dimension matches
        actual_dim = embed_service.get_dimension()
        if actual_dim != args.vector_size:
            print(
                f"WARNING: Model dimension ({actual_dim}) != --vector-size ({args.vector_size})"
            )
            print(f"Using model dimension: {actual_dim}")
            args.vector_size = actual_dim
            # Recreate collection with correct dimension
            client.delete_collection(args.collection)
            ensure_collection(client, args.collection, args.vector_size)

    # Batch processing
    total_batches = (len(items) + args.batch_size - 1) // args.batch_size
    iterator = range(0, len(items), args.batch_size)

    if tqdm:
        iterator = tqdm(
            iterator, desc="Upserting batches", total=total_batches
        )

    total_upserted = 0
    for start_idx in iterator:
        batch = items[start_idx : start_idx + args.batch_size]
        points: list[PointStruct] = []

        # Filter valid texts
        valid_items = [
            (idx, item)
            for idx, item in enumerate(batch, start=start_idx)
            if item.get("text", "")
        ]

        if not valid_items:
            continue

        # Get embeddings for batch
        if embed_service:
            # Wave 6: Real embeddings (batch)
            texts = [item.get("text", "") for _, item in valid_items]
            embeddings = embed_service.encode(texts, show_progress=False)
            vectors = embeddings.tolist()
        else:
            # Legacy: Pseudo-embeddings
            vectors = [
                simple_embed(item.get("text", ""), dim=args.vector_size)
                for _, item in valid_items
            ]

        # Build points
        for (idx, item), vec in zip(valid_items, vectors, strict=False):
            point_id = item.get("id", idx)
            payload = {
                "text": item.get("text", ""),
                "namespace": item.get("namespace", "default"),
                "path": item.get("path", None),
            }
            points.append(
                PointStruct(id=point_id, vector=vec, payload=payload)
            )

        if points:
            client.upsert(collection_name=args.collection, points=points)
            total_upserted += len(points)

    print(f"\nUpserted {total_upserted} points into '{args.collection}'.")
    if embed_service:
        print(f"Using real embeddings: {args.model} ({args.vector_size}-dim)")
    else:
        print("Using pseudo-embeddings (legacy mode)")


if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
