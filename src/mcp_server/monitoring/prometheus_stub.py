"""Prometheus metrics stub.

Expose basic metrics via a lightweight HTTP server on configurable port.
Avoid heavy deps; plain text exposition format.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from mcp_server import metrics
from mcp_server.security import anomaly_detector

_PORT = 9103


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_GET(self):  # noqa: D401
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        snapshot = metrics.snapshot()
        anomalies = anomaly_detector.analyze(3600)
        # Parse telemetry spans for latency stats
        spans_file = Path("logs/mcp_tool_spans.jsonl")
        durations = []
        successes = 0
        failures = 0
        if spans_file.exists():
            try:
                for line in spans_file.read_text(
                    encoding="utf-8"
                ).splitlines():
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    d = obj.get("duration_ms")
                    if isinstance(d, (int, float)):
                        durations.append(float(d))
                    if obj.get("success") is True:
                        successes += 1
                    elif obj.get("success") is False:
                        failures += 1
            except Exception:
                pass
        durations.sort()

        def pct(p: float) -> float:
            if not durations:
                return 0.0
            idx = int(p * (len(durations) - 1))
            return durations[idx]

        # Bucket counts for histogram approximation
        buckets = [10, 50, 100, 200, 500, 1000]
        bucket_counts = {b: 0 for b in buckets}
        for v in durations:
            for b in buckets:
                if v <= b:
                    bucket_counts[b] += 1
        lines.append(
            "# HELP mcp_latency_hist Approx latency histogram buckets"
        )
        lines.append("# TYPE mcp_latency_hist histogram")
        for b in buckets:
            lines.append(
                f'mcp_latency_hist_bucket{{le="{b}"}} {bucket_counts[b]}'
            )
        lines.append(f"mcp_latency_hist_count {len(durations)}")
        lines = []
        for k, v in snapshot.items():
            if isinstance(v, (int, float)):
                lines.append(f"mcp_{k} {v}")
        lines.append(
            f"mcp_breaker_open {1 if snapshot.get('breaker',{}).get('state')=='open' else 0}"
        )
        lines.append(f"mcp_anomaly_count {len(anomalies.get('anomalies',[]))}")
        lines.append(f"mcp_telemetry_spans_total {len(durations)}")
        lines.append(f"mcp_telemetry_spans_success {successes}")
        lines.append(f"mcp_telemetry_spans_failure {failures}")
        lines.append(f"mcp_latency_p50_ms {pct(0.50):.2f}")
        lines.append(f"mcp_latency_p90_ms {pct(0.90):.2f}")
        lines.append(f"mcp_latency_p99_ms {pct(0.99):.2f}")
        data = "\n".join(lines) + "\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(data.encode())


def start_async(port: int = _PORT):
    httpd = HTTPServer(("0.0.0.0", port), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


if __name__ == "__main__":
    print(f"Starting Prometheus stub on {_PORT}")
    start_async(_PORT)
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
