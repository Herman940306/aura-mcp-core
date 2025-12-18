#!/usr/bin/env python3
"""
Verify GITHUB_TOKEN before composing containers.
Reads token from .env (repo root) or from environment, then calls GitHub /user.
Exit code 0 on success, non-zero otherwise.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_token() -> str | None:
    # Prefer .env in repo root
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("GITHUB_TOKEN="):
                val = line.split("=", 1)[1].strip()
                # strip surrounding quotes if present
                if (val.startswith('"') and val.endswith('"')) or (
                    val.startswith("'") and val.endswith("'")
                ):
                    val = val[1:-1]
                return val
    val = os.getenv("GITHUB_TOKEN")
    if val:
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
    return val


def try_call(token: str, scheme: str) -> tuple[bool, dict, int]:
    try:
        req = Request(
            "https://api.github.com/user",
            headers={
                "Authorization": f"{scheme} {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "mcp-server-token-verifier",
            },
        )
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data, 0
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = ""
        return (
            False,
            {"status": e.code, "reason": e.reason, "body": body[:200]},
            1,
        )
    except URLError as e:
        return False, {"error": str(e)}, 1


def main() -> int:
    token = load_token()
    if not token:
        print("GITHUB_TOKEN not found in .env or environment.")
        return 2
    # Try preferred scheme for PATs
    ok, data, code = try_call(token, "token")
    if ok:
        print(
            json.dumps(
                {
                    "ok": True,
                    "login": data.get("login"),
                    "id": data.get("id"),
                    "scheme": "token",
                },
                indent=2,
            )
        )
        return 0
    # Fallback to Bearer (e.g., GitHub App tokens)
    ok2, data2, code2 = try_call(token, "Bearer")
    if ok2:
        print(
            json.dumps(
                {
                    "ok": True,
                    "login": data2.get("login"),
                    "id": data2.get("id"),
                    "scheme": "Bearer",
                },
                indent=2,
            )
        )
        return 0
    out = {"ok": False, "attempts": {"token": data, "Bearer": data2}}
    print(json.dumps(out, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
