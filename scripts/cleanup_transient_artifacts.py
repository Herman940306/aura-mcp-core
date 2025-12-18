from __future__ import annotations

import argparse
import shutil
import stat
import sys
from pathlib import Path

TRANSIENT_DIRS = [
    "temp_migration_matrix",
    "temp_migration_matrix_perm",
    "temp_migration_test",
    "upgraded_mcp_universal",
]


def resolve_targets(repo_root: Path) -> list[Path]:
    return [repo_root / d for d in TRANSIENT_DIRS if (repo_root / d).exists()]


def ensure_within_repo(repo_root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(repo_root.resolve())
    except Exception as exc:  # safety net: never delete outside repo
        raise RuntimeError(
            f"Refusing to delete outside repo: {target}"
        ) from exc


def force_permissions(path: Path) -> None:
    """Attempt to make path writable to allow deletion on Windows."""
    try:
        path.chmod(stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Remove transient staging artifacts per PRD hygiene. "
            "Defaults to dry-run. Use --yes to actually delete."
        )
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Perform deletion instead of dry-run.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Only list targets and exit.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    targets = resolve_targets(repo_root)

    if not targets:
        print("No transient artifacts found.")
        return 0

    print("Transient artifact targets:")
    for t in targets:
        print(f" - {t}")

    if args.list and not args.yes:
        return 0

    if not args.yes:
        print("Dry-run: no deletions performed. Use --yes to delete.")
        return 0

    for t in targets:
        ensure_within_repo(repo_root, t)
        print(f"Deleting {t} ...")
        # Walk and force write perms before deletion (Windows ACL edge cases)
        for p in t.rglob("*"):
            force_permissions(p)
        try:
            shutil.rmtree(t, ignore_errors=False)
        except PermissionError:
            print(f"PermissionError: retrying with forced perms for {t}")
            for p in t.rglob("*"):
                force_permissions(p)
            shutil.rmtree(t, ignore_errors=False)

    print("Cleanup complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
