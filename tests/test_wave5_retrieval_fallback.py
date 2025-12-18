from aura_ia_mcp.services.model_gateway.retrieval_pipeline import (
    RetrievalConfig,
    Retriever,
)


class FailingClient:
    def search(self, **kwargs):
        raise RuntimeError("simulated qdrant failure")


def dummy_embed(text: str):
    return [0.0, 0.0, 0.0]


def test_retriever_graceful_fallback_on_error():
    cfg = RetrievalConfig(collection="default", top_k=3)
    retriever = Retriever(FailingClient(), dummy_embed, cfg)
    result = retriever.retrieve("query text")
    assert result == []
