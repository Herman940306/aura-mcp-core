from __future__ import annotations

import sys
from pathlib import Path

import anyio
import httpx


async def main() -> None:
    # Import the ASGI app directly to avoid starting a server.
    # Ensure repository root is on sys.path for direct module import.
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from aura_ia_mcp.main import app  # lazy import

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as c:
        # 1) Allowed read-only route
        try:
            r1 = await c.get("/roles/load")
            print("GET /roles/load:", r1.status_code, r1.text)
        except Exception as exc:
            print("GET /roles/load failed:", exc)

        # 2) Restricted role mutation (gated by SAFE MODE/capability)
        try:
            r2 = await c.post("/roles/mutate", json={"approved": False})
            print("POST /roles/mutate:", r2.status_code, r2.text)
        except Exception as exc:
            print("POST /roles/mutate failed:", exc)

        # 3) Training start (should be gated by SAFE MODE/capability)
        try:
            r3 = await c.post(
                "/training/start",
                json={"episodes": 1, "dry_run": True},
            )
            print("POST /training/start:", r3.status_code, r3.text)
        except Exception as exc:
            print("POST /training/start failed:", exc)


if __name__ == "__main__":
    anyio.run(main)
