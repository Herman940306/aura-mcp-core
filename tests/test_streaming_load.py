"""Streaming load test.

Starts the SSE server and opens multiple concurrent client connections to
verify all event streams reach 100% progress with expected event count.
"""

import asyncio
import json

from tests.stubs.streaming import start_server, stop_server


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


async def consume_stream(session_id: int) -> int:
    import httpx

    events = 0
    async with httpx.AsyncClient(timeout=5.0) as client:
        async with client.stream(
            "GET", "http://127.0.0.1:8765/_mcp/stream_test"
        ) as resp:
            if resp.status_code != 200:
                raise RuntimeError(
                    f"session {session_id} bad status {resp.status_code}"
                )
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    payload = json.loads(line[len("data: ") :])
                except json.JSONDecodeError:
                    continue
                events += 1
                if payload.get("progress") == 100:
                    break
    return events


async def streaming_load_test() -> bool:
    server, thread = start_server()
    try:
        consumers: list[asyncio.Task] = []
        for i in range(8):  # 8 parallel SSE sessions
            consumers.append(asyncio.create_task(consume_stream(i)))
        results = await asyncio.gather(*consumers, return_exceptions=True)
    finally:
        stop_server(server)
        thread.join(timeout=1.0)
    ok_counts = []
    for r in results:
        if isinstance(r, Exception):
            fail(f"stream error: {r}")
            return False
        ok_counts.append(r)
    # Each stream should emit 5 events (progress steps)
    return len(ok_counts) == 8 and all(c == 5 for c in ok_counts)


async def main():
    ok("RUN streaming_load_test")
    try:
        res = await streaming_load_test()
        if res:
            ok("streaming_load_test")
        else:
            fail("streaming_load_test")
    except Exception as e:
        fail(f"streaming_load_test error: {e}")
        res = False
    exit(0 if res else 1)


if __name__ == "__main__":
    asyncio.run(main())
