"""Streaming SSE test.

Starts local SSE server and consumes incremental events.
"""

import json
import time
from urllib.request import urlopen

from tests.stubs.streaming import start_server, stop_server


def main() -> None:
    server, _thread = start_server()
    time.sleep(0.1)
    url = "http://127.0.0.1:8765/_mcp/stream_test"
    try:
        with urlopen(url, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
    finally:
        stop_server(server)
    chunks = [c for c in raw.split("\n\n") if c.strip()]
    parsed = []
    for c in chunks:
        if c.startswith("data: "):
            try:
                parsed.append(json.loads(c[len("data: ") :]))
            except ValueError:
                pass
    if len(parsed) == 5 and all("progress" in p for p in parsed):
        print("✓ streaming sse passed")
        exit(0)
    print("✗ streaming sse failed", parsed)
    exit(1)


if __name__ == "__main__":
    main()
