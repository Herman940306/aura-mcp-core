from pathlib import Path

from prometheus_client.registry import CollectorRegistry

from aura_ia_mcp.services.model_gateway.retrieval_pipeline import (
    RetrievalConfig,
    Retriever,
)


class FailingClient:
    def search(self, **kwargs):
        raise RuntimeError("simulated qdrant failure")


def dummy_embed(text: str):
    return [0.0, 0.0, 0.0]


def test_retriever_audit_log_on_error(tmp_path: Path, monkeypatch):
    audit_path = tmp_path / "security_audit.jsonl"
    monkeypatch.setenv("RETRIEVAL_AUDIT_LOG", "1")
    monkeypatch.setenv("RETRIEVAL_AUDIT_PATH", str(audit_path))

    cfg = RetrievalConfig(collection="default", top_k=3)
    retriever = Retriever(
        FailingClient(), dummy_embed, cfg, metrics_registry=CollectorRegistry()
    )

    # Execute retrieval to trigger failure and audit logging
    result = retriever.retrieve("query text for audit")
    assert result == []

    # Verify audit file was written
    assert audit_path.exists()
    content = audit_path.read_text(encoding="utf-8").strip()
    assert content, "Audit log should contain at least one entry"
    # Basic structure check
    assert "retrieval_failure" in content
    assert "query_preview" in content


def test_retriever_no_audit_when_disabled(tmp_path: Path, monkeypatch):
    # Ensure audit is disabled
    monkeypatch.delenv("RETRIEVAL_AUDIT_LOG", raising=False)
    monkeypatch.setenv("RETRIEVAL_AUDIT_PATH", str(tmp_path / "audit.jsonl"))

    cfg = RetrievalConfig(collection="default", top_k=2)
    retriever = Retriever(
        FailingClient(), dummy_embed, cfg, metrics_registry=CollectorRegistry()
    )
    result = retriever.retrieve("query text")
    assert result == []
    # File should not be created
    assert not (tmp_path / "audit.jsonl").exists()


def test_retriever_default_audit_path(monkeypatch, tmp_path: Path):
    # Enable audit but do not set path; should use default under logs/
    monkeypatch.setenv("RETRIEVAL_AUDIT_LOG", "1")
    monkeypatch.delenv("RETRIEVAL_AUDIT_PATH", raising=False)

    cfg = RetrievalConfig(collection="default", top_k=2)
    retriever = Retriever(
        FailingClient(), dummy_embed, cfg, metrics_registry=CollectorRegistry()
    )
    result = retriever.retrieve("query text")
    assert result == []
    # Verify default path received a line
    default_path = Path("logs") / "security_audit.jsonl"
    assert default_path.exists()
    content = default_path.read_text(encoding="utf-8").strip()
    assert content
    assert content
