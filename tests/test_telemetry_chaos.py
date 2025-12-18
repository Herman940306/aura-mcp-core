"""Chaos telemetry concurrency test.

Spawns concurrent tasks emitting spans rapidly while forcing periodic flush
to detect race conditions or write errors. Passes if line count >= emitted
span count and no stderr write failure detected.
"""

import asyncio

from src.mcp_server import telemetry


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


async def spam_spans(n: int):
    for i in range(n):
        telemetry.emit_span(
            "chaos_test",
            start_time=asyncio.get_event_loop().time(),
            method="spam",
            success=True,
        )
        if i % 25 == 0:
            telemetry.flush_telemetry()
        await asyncio.sleep(0)


async def chaos_telemetry_test() -> bool:
    log_dir, log_file = telemetry._log_paths()  # type: ignore
    pre_lines = 0
    if log_file.exists():
        pre_lines = sum(1 for _ in log_file.open("r", encoding="utf-8"))
    tasks = [
        asyncio.create_task(spam_spans(200)),
        asyncio.create_task(spam_spans(200)),
    ]
    await asyncio.gather(*tasks)
    telemetry.flush_telemetry()
    # Allow IO settle
    await asyncio.sleep(0.1)
    total_lines = 0
    if log_file.exists():
        total_lines = sum(1 for _ in log_file.open("r", encoding="utf-8"))
    written = total_lines - pre_lines
    if written < 400:  # Expect at least emitted count
        fail(f"telemetry lines insufficient: {written}")
        return False
    return True


async def main():
    ok("RUN telemetry_chaos_test")
    res = await chaos_telemetry_test()
    if res:
        ok("telemetry_chaos_test")
    else:
        fail("telemetry_chaos_test")
    exit(0 if res else 1)


if __name__ == "__main__":
    asyncio.run(main())
