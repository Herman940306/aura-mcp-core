from __future__ import annotations

import sys
from pathlib import Path

TRANSIENT_DIRS = [
    "temp_migration_matrix",
    "temp_migration_matrix_perm",
    "temp_migration_test",
    "upgraded_mcp_universal",
]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    offenders: list[Path] = []
    for rel in TRANSIENT_DIRS:
        p = repo_root / rel
        if p.exists():
            offenders.append(p)

    if offenders:
        print("Transient staging artifacts found (must be removed per PRD):")
        for p in offenders:
            print(f" - {p}")
        print("Delete these before merging or add explicit PR justification.")
        return 1

    print("No transient staging artifacts detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
