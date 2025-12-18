import time
import uuid
from collections.abc import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from .audit import write_audit_log

EXCLUDE_PATHS = {"/healthz", "/readyz", "/livez"}


class AuditMiddleware(BaseHTTPMiddleware):
    """Attach request IDs and persist basic HTTP audit records."""

    async def dispatch(self, request: Request, call_next: Callable):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = req_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        response.headers["X-Request-ID"] = req_id

        if request.url.path not in EXCLUDE_PATHS:
            write_audit_log(
                {
                    "type": "http",
                    "rid": req_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 3),
                    "ua": request.headers.get("user-agent", "-"),
                    "client": request.client.host if request.client else "-",
                }
            )
        return response
