import json
import os

from aura_ia_mcp.core.audit import audit_safe_mode_transition
from aura_ia_mcp.core.capabilities import load_capabilities


def main() -> None:
    state = load_capabilities()
    if not state.safe_mode:
        print(json.dumps({"status": "already_off"}))
        return
    audit_safe_mode_transition(
        False,
        os.getenv("GITHUB_ACTOR", "local"),
        state.export(),
    )
    print(json.dumps({"status": "logged", "active": False}))


if __name__ == "__main__":
    main()
    main()
