import asyncio
import json
import logging
import os

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

logging.basicConfig(level=logging.INFO, format="%(message)s")


async def main():
    # Allow override via env; attempt compatible fallbacks
    # Canonical Aura IA port: 9200
    base = (
        os.getenv("MCP_SSE_URL")
        or os.getenv("MCP_URL")
        or "http://localhost:9200"
    )
    candidates = [base.rstrip("/") + "/sse", base.rstrip("/")]

    last_err: Exception | None = None
    for url in candidates:
        try:
            async with sse_client(url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    ready = await session.call_tool("ide_agents_readyz", {})
                    healthz = await session.call_tool("ide_agents_healthz", {})
                    health = await session.call_tool("ide_agents_health", {})
                    metrics = await session.call_tool(
                        "ide_agents_metrics_snapshot", {}
                    )

                    def extract(obj):
                        # unwrap TextContent result to text then to JSON when possible
                        try:
                            text = obj.content[0].text  # type: ignore[attr-defined]
                            return json.loads(text)
                        except Exception:
                            return str(obj)

                    print("READYZ:")
                    print(json.dumps(extract(ready), indent=2))
                    print("\nHEALTHZ:")
                    print(json.dumps(extract(healthz), indent=2))
                    print("\nHEALTH:")
                    print(json.dumps(extract(health), indent=2))
                    print("\nMETRICS:")
                    print(json.dumps(extract(metrics), indent=2))
                    return
        except Exception as exc:  # try next candidate on failure
            last_err = exc
            continue
    # If all candidates failed, re-raise last error
    if last_err:
        raise last_err


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
