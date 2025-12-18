import json
import os
import re
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent.resolve()
REPO_ROOT = THIS_DIR.parent


def has_transition_label() -> bool:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not Path(event_path).is_file():
        return False
    try:
        with open(event_path, encoding="utf-8") as f:
            data = json.load(f)
        labels = []
        # pull_request event
        if "pull_request" in data and isinstance(data["pull_request"], dict):
            labels = [
                lbl.get("name", "")
                for lbl in data["pull_request"].get("labels", [])
            ]
        # label event
        if "label" in data and isinstance(data["label"], dict):
            labels.append(data["label"].get("name", ""))
        labels = [str(x).strip().lower() for x in labels if isinstance(x, str)]
        return any(
            lbl_name
            in {
                "allow-safe-mode-off",
                "transition-approved",
                "approve-safe-mode-off",
            }
            for lbl_name in labels
        )
    except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError):
        return False


def ensure_safe_mode_default_true() -> list[str]:
    """Ensure the default for AURA_SAFE_MODE remains True in config code."""
    errors: list[str] = []
    # Search common locations
    candidate_files = [
        REPO_ROOT / "src" / "aura_ia_mcp" / "core" / "config.py",
        REPO_ROOT / "aura_ia_mcp" / "core" / "config.py",
        REPO_ROOT / "src" / "mcp_server" / "core" / "config.py",
    ]
    found_any = False
    for path in candidate_files:
        if path.is_file():
            found_any = True
            text = path.read_text(encoding="utf-8", errors="ignore")
            # Match pydantic v2 style default assignment
            # e.g., AURA_SAFE_MODE: bool = True
            m = re.search(
                r"AURA_SAFE_MODE\s*:\s*bool\s*=\s*(True|False)",
                text,
            )
            if not m:
                continue
            val = m.group(1)
            if val != "True":
                errors.append(
                    f"SAFE MODE default must be True in {path}; found {val}."
                )
    if not found_any:
        # If config isn't found, do not fail here;
        # compliance job will catch structure issues
        pass
    return errors


def ensure_env_not_disabling_safe_mode() -> list[str]:
    errors: list[str] = []
    env_files = [REPO_ROOT / ".env", REPO_ROOT / "env" / ".env"]
    pattern = re.compile(r"^\s*AURA_SAFE_MODE\s*=\s*false\s*$", re.IGNORECASE)
    for envf in env_files:
        if envf.is_file():
            content = envf.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.splitlines(), start=1):
                if pattern.search(line):
                    errors.append(
                        f"{envf}:{i} sets AURA_SAFE_MODE=false; "
                        f"keep TRUE until approved."
                    )
    return errors


def main() -> int:
    if has_transition_label():
        # Transition explicitly approved; no enforcement.
        print("Transition label present; SAFE MODE enforcement bypassed.")
        return 0

    errors: list[str] = []
    errors += ensure_safe_mode_default_true()
    errors += ensure_env_not_disabling_safe_mode()

    if errors:
        print("SAFE MODE enforcement check failed:")
        for e in errors:
            print(f" - {e}")
        print(
            "Set PR label 'allow-safe-mode-off' once reviewers approve "
            "flipping flags."
        )
        return 1

    print("SAFE MODE remains enforced (AURA_SAFE_MODE=True).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
