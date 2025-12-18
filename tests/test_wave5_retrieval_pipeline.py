from aura_ia_mcp.services.model_gateway.retrieval_pipeline import (
    RetrievalConfig,
    Retriever,
)


class DummyClient:
    def __init__(self, payloads):
        self._payloads = payloads

    def search(self, collection_name, query_vector, limit, filter=None):
        class Point:
            def __init__(self, payload, score):
                self.payload = payload
                self.score = score

        return [Point(p, p.get("score", 0.5)) for p in self._payloads][:limit]


def dummy_embed(x):
    return [0.0, 0.1, 0.2]


def test_basic_retrieval_truncates_to_budget():
    client = DummyClient(
        [
            {"text": "alpha beta gamma", "score": 0.8},
            {"text": "delta epsilon zeta", "score": 0.7},
            {"text": "eta theta iota", "score": 0.6},
        ]
    )
    cfg = RetrievalConfig(
        collection="test", top_k=5, retrieval_budget_tokens=8
    )
    r = Retriever(client, dummy_embed, cfg)
    out = r.retrieve("alpha")
    assert len(out) >= 1
    assert (
        sum((len(d["text"]) + 3) // 4 for d in out)
        <= cfg.retrieval_budget_tokens
    )


def test_metadata_filter_optional():
    client = DummyClient([{"text": "foo", "score": 0.9, "tag": "x"}])
    cfg = RetrievalConfig(collection="test", metadata_filter=None)
    r = Retriever(client, dummy_embed, cfg)
    out = r.retrieve("foo")
    assert out and out[0]["text"] == "foo"
    cfg = RetrievalConfig(collection="test", metadata_filter=None)
    r = Retriever(client, dummy_embed, cfg)
    out = r.retrieve("foo")
    assert out and out[0]["text"] == "foo"
