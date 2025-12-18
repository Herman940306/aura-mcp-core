"""FastAPI middleware for HTTP request metrics.

Instruments HTTP requests with prometheus-client to track:
- http_requests_total (counter by endpoint, method, status)
- http_request_duration_seconds (histogram by endpoint)

Integrates with existing metrics taxonomy (http_requests_total).
"""

from __future__ import annotations

import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests by endpoint and status",
    labelnames=("method", "endpoint", "status"),
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency distribution",
    labelnames=("method", "endpoint"),
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        method = request.method
        path = request.url.path
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start
        status = response.status_code
        http_requests_total.labels(
            method=method, endpoint=path, status=status
        ).inc()
        http_request_duration_seconds.labels(
            method=method, endpoint=path
        ).observe(duration)
        return response


__all__ = ["HTTPMetricsMiddleware"]
