import json
import os

EXPECTED_TOP_LEVEL = {
    # Core packages & source
    "aura_ia_mcp",
    "src",
    "plugins",
    "approval",
    "streaming",
    "telemetry",
    "mcp_sync_manager",
    "mcp_sync_trigger",
    # Infra / ops / training
    "ops",
    "training",
    "docker",
    "k8s",
    "model_artifacts",
    "simulator",
    "observability",
    # Configuration & environment
    "config",
    "env",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "pyrightconfig.json",
    "pytest.ini",
    # Data & dashboards
    "data",
    "dashboard",
    "docs",
    "mcp",
    # Governance & documentation artifacts
    "AURA_IA_MCP_PRD.md",
    "IN‑DEPTH AGENT INSTRUCTION GUIDE.md",
    "MERGE_AND_IMPLEMENT_SUPER_MCP.md",
    "AGENT_ISOLATION_NOTICE.md",
    "NEW COMPLETE README.md",
    "README.md",
    "Full_Agent_Implementation_Guide.md",
    # Logs & scripts & tests
    "logs",
    "scripts",
    "tests",
    # Compose & SBOM
    "docker-compose.yml",
    "docker-compose.cpu.yml",
    "docker-compose.gpu.yml",
    "docker-compose.observability.yml",
    "SBOM",
    # Audio service (Phase 9)
    "aura-audio-service",
    # E2E evidence artifacts
    "e2e-evidence",
    # Security (PII, OPA, SBOM, signing)
    "security",
    # Backups directory
    "backups",
    # Split requirements files
    "requirements-base.txt",
    "requirements-backend.txt",
    "requirements-dev.txt",
    "requirements-gateway.txt",
    # Test reports
    "test_report.json",
    # Sandbox run helpers
    "sandbox_dev_run.sh",
    "sandbox_dev_run.ps1",
    # Build artifacts (allowed)
    "build.log",
    # Legacy archived installers & scratch (to be removed in PR cleanup)
    # Legacy installer scripts removed
    "New Text Document.txt",
}

ALLOWED_TEMP_PREFIXES = {
    "temp_",
    "upgraded_mcp_universal",
    "venv",
    "__pycache__",
}


def scan_root():
    entries = os.listdir(".")
    unexpected = []
    for e in entries:
        if e in EXPECTED_TOP_LEVEL:
            continue
        if any(e.startswith(p) for p in ALLOWED_TEMP_PREFIXES):
            continue
        # ignore hidden
        if e.startswith("."):
            continue
        unexpected.append(e)
    return unexpected


if __name__ == "__main__":
    result = {"unexpected": scan_root()}
    print(json.dumps(result))
