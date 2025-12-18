from typing import Any

import anyio
import httpx
from httpx import ASGITransport


class SyncASGIClient:
    def __init__(self, app: Any, base_url: str = "http://test") -> None:
        self._transport = ASGITransport(app=app)
        self._client = httpx.AsyncClient(
            transport=self._transport,
            base_url=base_url,
        )

    def request(self, method: str, url: str, **kwargs):
        async def _do():
            return await self._client.request(method, url, **kwargs)

        return anyio.run(_do)

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        anyio.run(self._client.aclose)


def make_sync_client(
    app: Any, base_url: str = "http://test"
) -> SyncASGIClient:
    return SyncASGIClient(app=app, base_url=base_url)
