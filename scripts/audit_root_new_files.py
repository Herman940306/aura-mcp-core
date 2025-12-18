#!/usr/bin/env python3
"""Audit for unexpected new root-level files per PRD Section 7.1.

Allowed top-level entries (directories or files) are whitelisted; anything else
is reported and exits non-zero for CI enforcement.
"""
from __future__ import annotations

import json
import pathlib
import sys

ALLOWED = {
    # Core directories
    "aura_ia_mcp",
    "mcp",
    "ops",
    "training",
    "tools",
    "tests",
    "docs",
    "scripts",
    "docker",
    "k8s",
    "config",
    "logs",
    "data",
    "plugins",
    "env",
    ".vscode",
    "src",  # legacy source tree during transition
    # Observability / artifacts
    "observability",
    "model_artifacts",
    "simulator",
    "SBOM",
    # Added placeholder/stub modules for test stabilization
    "telemetry",
    "approval",
    "streaming",
    "mcp_sync_manager",
    "mcp_sync_trigger",
    # Governance / meta files
    "AURA_IA_MCP_PRD.md",
    "README.md",
    "NEW COMPLETE README.md",
    "MERGE_AND_IMPLEMENT_SUPER_MCP.md",
    "pytest.ini",
    "setup.cfg",
    "requirements.txt",
    "docker-compose.yml",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    # Environment examples
    ".env.example",
    ".env",  # tolerated but must be gitignored
    # Misc known artifacts
    "AGENT_ISOLATION_NOTICE.md",
    "sandbox_dev_run.sh",
    "sandbox_dev_run.ps1",
}

# Files prefixed with these values are ignored (system tooling side-effects)
PREFIX_ALLOW = (
    ".git",
    ".github",
)

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    unexpected: list[str] = []
    for item in ROOT.iterdir():
        name = item.name
        if name in ALLOWED:
            continue
        if any(name.startswith(pfx) for pfx in PREFIX_ALLOW):
            continue
        # ignore Python cache & common ephemeral dirs
        if name in ("__pycache__",):
            continue
        # ignore virtual env folder markers if not named 'env'
        if item.is_dir() and name.startswith("venv"):
            continue
        unexpected.append(name)
    result: dict[str, object] = {
        "root": str(ROOT),
        "unexpected": sorted(unexpected),
        "count": len(unexpected),
    }
    print(json.dumps(result, indent=2))
    if unexpected:
        print(
            "Non-compliant root artifacts detected; relocate or delete; "
            "review whitelist if items are legitimate.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
