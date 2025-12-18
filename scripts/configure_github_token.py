#!/usr/bin/env python3
"""
Prompt for a GitHub token and write/update it in the project .env file.
Compose will read .env automatically when running `docker compose ...`.
"""
from __future__ import annotations

import getpass
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    token = getpass.getpass("Enter GITHUB_TOKEN (input hidden): ")
    if not token.strip():
        print("No token entered. Aborting.")
        return
    lines: list[str] = []
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line.lstrip().startswith("GITHUB_TOKEN="):
                lines.append(line)
    lines.append(f"GITHUB_TOKEN={token.strip()}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {env_path}")
    print("Next:")
    print("  docker compose up -d")


if __name__ == "__main__":
    main()
