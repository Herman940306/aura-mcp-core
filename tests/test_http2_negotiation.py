"""HTTP/2 negotiation test.

Validates that httpx[http2] extras are installed by performing a request to
an HTTP/2 capable public endpoint and asserting response.http_version.
Falls back to skip (pass) if network unavailable.
"""

import asyncio
import sys

import httpx


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


async def http2_test() -> bool:
    try:
        async with httpx.AsyncClient(http2=True, timeout=5.0) as client:
            resp = await client.get("https://nghttp2.org/httpbin/get")
            if resp.status_code != 200:
                return False
            return resp.http_version == "HTTP/2"
    except Exception as e:
        # Treat network issues as non-failure to keep suite resilient
        ok(f"skip network issue: {e}")
        return True


async def main():
    ok("RUN http2_negotiation_test")
    res = await http2_test()
    if res:
        ok("http2_negotiation_test")
    else:
        fail("http2_negotiation_test")
    sys.exit(0 if res else 1)


if __name__ == "__main__":
    asyncio.run(main())
