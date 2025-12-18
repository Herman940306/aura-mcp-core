"""ASGI test client wrapper using httpx.ASGITransport.

Replaces deprecated fastapi.testclient usage to comply with integration
checklist requirement for explicit ASGI transport.
"""

import asyncio

import httpx

from aura_ia_mcp.main import app

_transport = httpx.ASGITransport(app=app)


class SyncClient:
    def get(self, url: str, **kwargs):  # type: ignore[override]
        async def _do():
            async with httpx.AsyncClient(
                transport=_transport, base_url="http://test"
            ) as c:
                return await c.get(url, **kwargs)

        return asyncio.run(_do())


client = SyncClient()
client = SyncClient()
client = SyncClient()
