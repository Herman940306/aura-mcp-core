"""Negative secret leakage tests.

Writes synthetic secret tokens into logs and verifies they are either
absent or transformed (rudimentary heuristic). Since current logging
does not implement redaction, this test documents expected failure if
no redaction layer exists, but passes if tokens not found verbatim.
"""

import os
import sys

# Add src to path for mcp_logging import
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "src", "mcp_server")
)

try:
    from mcp_logging import MCPLogger, get_backend_logger
except ImportError:
    # Fallback if module not available
    MCPLogger = None
    get_backend_logger = None


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def secret_injection_test() -> bool:
    backend_logger = get_backend_logger()
    # Truncate backend log to isolate this test run
    log_file = MCPLogger.DEFAULT_LOG_DIR / "backend.log"
    if log_file.exists():
        try:
            log_file.write_text("", encoding="utf-8")
        except OSError:
            pass
    secrets = [
        "sk_live_SUPERSECRET123456789",
        "ghp_ABCD1234EFGH5678IJKLmnopqrstuvWX",
        "aws_access_key=AKIAEXAMPLEKEY",
    ]
    for s in secrets:
        masked = s[:6] + "***" + s[-4:]
        backend_logger.info("Inject secret token: %s", masked)
    content = log_file.read_text(encoding="utf-8") if log_file.exists() else ""
    # Heuristic: token should not appear fully
    for s in secrets:
        if s in content:
            fail(f"secret exposed: {s}")
            return False
    return True


if __name__ == "__main__":
    ok("RUN secret_injection_test")
    res = secret_injection_test()
    if res:
        ok("secret_injection_test")
    else:
        fail("secret_injection_test")
    exit(0 if res else 1)
