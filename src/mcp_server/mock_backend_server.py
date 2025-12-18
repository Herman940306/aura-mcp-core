"""Mock backend server for testing MCP server integration.

This provides a minimal backend service on port 8001 for testing purposes.

Project Creator: Herman Swanepoel
"""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class MockBackendHandler(BaseHTTPRequestHandler):
    """Handle requests to mock backend."""

    def log_message(self, format: str, *args: Any) -> None:
        """Override to reduce noise."""
        pass

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self) -> None:
        """Handle GET requests."""
        start_ts = time.time()
        if self.path == "/health":
            latency_ms = int((time.time() - start_ts) * 1000)
            self._send_json(
                {
                    "ok": True,
                    "status": "ok",
                    "service": "mock-backend",
                    "latency_ms": latency_ms,
                }
            )
        elif self.path == "/ready":
            self._send_json({"ready": True})
        elif self.path == "/":
            self._send_json(
                {"message": "Mock IDE Agents Backend", "version": "1.0"}
            )
        elif self.path == "/entities/mappings":
            self._send_json(
                [
                    {"name": "test_entity", "type": "command"},
                    {"name": "example_entity", "type": "resource"},
                ]
            )
        elif self.path.startswith("/documentation"):
            self._send_json({"topic": "test", "content": "Mock documentation"})
        elif self.path.startswith("/ai/intelligence/predictions/"):
            self._send_json(
                {
                    "predictions": [
                        {"action": "test_action", "confidence": 0.85},
                        {"action": "example_action", "confidence": 0.72},
                    ]
                }
            )
        elif self.path.startswith("/ai/intelligence/mood/analyze/"):
            text = self.path.split("/")[-1]
            self._send_json(
                {"text": text, "mood": "neutral", "confidence": 0.75}
            )
        elif self.path.startswith("/ai/intelligence/insights/"):
            self._send_json(
                {
                    "insights": [
                        {
                            "category": "usage",
                            "value": "High activity detected",
                        },
                    ]
                }
            )
        elif self.path == "/ai/intelligence/status":
            self._send_json(
                {
                    "emotion_engine": "running",
                    "prediction_engine": "running",
                    "reasoning_engine": "running",
                }
            )
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        """Handle POST requests."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = (
            self.rfile.read(content_length).decode()
            if content_length > 0
            else "{}"
        )

        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if self.path == "/command":
            self._send_json(
                {
                    "result": "success",
                    "command": data.get("command", ""),
                    "output": "Mock command executed",
                }
            )
        elif self.path == "/ai/intelligence/mood/analyze":
            # Handle emotion analysis POST request
            text = data.get("text", "")
            # Simple sentiment detection
            positive_words = [
                "excited",
                "thrilled",
                "happy",
                "great",
                "wonderful",
                "perfect",
                "love",
                "amazing",
            ]
            negative_words = [
                "sad",
                "angry",
                "frustrated",
                "terrible",
                "hate",
                "awful",
                "bad",
            ]

            text_lower = text.lower()
            positive_count = sum(
                1 for word in positive_words if word in text_lower
            )
            negative_count = sum(
                1 for word in negative_words if word in text_lower
            )

            if positive_count > negative_count:
                mood = "happy"
                confidence = min(0.95, 0.7 + (positive_count * 0.1))
            elif negative_count > positive_count:
                mood = "sad"
                confidence = min(0.95, 0.7 + (negative_count * 0.1))
            else:
                mood = "neutral"
                confidence = 0.75

            self._send_json(
                {"text": text, "mood": mood, "confidence": confidence}
            )
        elif self.path == "/ai/intelligence/rank":
            query = data.get("query", "")
            candidates = data.get("candidates", [])
            # Simple mock ranking
            ranking = [
                {"candidate": c, "score": 0.9 - (i * 0.1)}
                for i, c in enumerate(candidates[:5])
            ]
            self._send_json({"ranking": ranking})
        elif self.path == "/ai/intelligence/calibrate":
            scores = data.get("scores", [])
            calibrated = [s * 0.9 for s in scores]  # Simple mock calibration
            self._send_json({"calibration": calibrated})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests for CORS."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_server(port: int = 8001) -> None:
    """Run the mock backend server."""
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, MockBackendHandler)
    print(f"Mock backend server running on http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    run_server()
