"""Real Backend Server with Actual ML Models and GitHub API

This is a PRODUCTION backend with real implementations:
- Real GitHub API integration
- Real sentiment analysis using transformers
- Real semantic similarity for ULTRA
- Real command execution
- OpenTelemetry tracing support

Project Creator: Herman Swanepoel
Version: 1.0
"""

import json
import os
import subprocess
import threading
import time

try:
    import psutil
except ImportError:
    psutil = None
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import Any

# OpenTelemetry tracing (optional)
_tracer = None
try:
    from mcp_server.tracing_setup import init_tracing, is_tracing_enabled

    if is_tracing_enabled():
        if init_tracing("aura-ia-ml-backend"):
            from opentelemetry import trace

            _tracer = trace.get_tracer("aura-ia-ml-backend")
            print("✅ OpenTelemetry tracing enabled for ML Backend")
except ImportError:
    pass
except Exception as e:
    print(f"⚠️  OpenTelemetry init failed: {e}")

# Real GitHub API
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️  requests not available - GitHub integration will be limited")

# Real sentiment analysis
try:
    from transformers import pipeline

    sentiment_analyzer = pipeline(
        "sentiment-analysis",
        model="distilbert-base-uncased-finetuned-sst-2-english",
    )
    SENTIMENT_AVAILABLE = True
    print("✅ Sentiment analysis model loaded")
except ImportError:
    SENTIMENT_AVAILABLE = False
    print("⚠️  transformers not available - using fallback sentiment analysis")
except Exception as e:
    SENTIMENT_AVAILABLE = False
    print(f"⚠️  Could not load sentiment model: {e}")

# Real semantic similarity
try:
    from sentence_transformers import SentenceTransformer, util

    semantic_model = SentenceTransformer("all-MiniLM-L6-v2")
    SEMANTIC_AVAILABLE = True
    print("✅ Semantic similarity model loaded")
except ImportError:
    SEMANTIC_AVAILABLE = False
    print("⚠️  sentence-transformers not available - using fallback ranking")
except Exception as e:
    SEMANTIC_AVAILABLE = False
    print(f"⚠️  Could not load semantic model: {e}")

# Global state
github_token = os.getenv("GITHUB_TOKEN", "")
websocket_server = None


class SystemMonitor:
    """Monitors system resources and application metrics."""

    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.process = psutil.Process() if psutil else None

    def record_request(self, success=True):
        self.request_count += 1
        if not success:
            self.error_count += 1

    def get_stats(self):
        uptime = int(time.time() - self.start_time)
        stats = {
            "uptime_seconds": uptime,
            "requests_total": self.request_count,
            "error_count": self.error_count,
            "cpu_percent": 0.0,
            "memory_mb": 0.0,
            "memory_percent": 0.0,
            "disk_percent": 0.0,
            "network_kbs": 0.0,
            "gpu_percent": None,
            "gpu_memory_used_mb": None,
            "gpu_memory_total_mb": None,
            "temperature": None,
        }

        if self.process:
            try:
                # Get CPU with interval=None (non-blocking)
                stats["cpu_percent"] = self.process.cpu_percent(interval=None)
                mem = self.process.memory_info()
                stats["memory_mb"] = round(mem.rss / 1024 / 1024, 2)
                stats["memory_percent"] = round(
                    self.process.memory_percent(), 2
                )
            except Exception:
                pass

        # Get system-wide stats using psutil
        try:
            import psutil
            
            # System-wide CPU (more accurate than process CPU)
            stats["cpu_percent"] = psutil.cpu_percent(interval=None)
            
            # System-wide memory
            mem = psutil.virtual_memory()
            stats["memory_mb"] = round(mem.used / 1024 / 1024, 2)
            stats["memory_percent"] = round(mem.percent, 1)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            stats["disk_percent"] = round(disk.percent, 1)
            
            # Network I/O
            net = psutil.net_io_counters()
            total_bytes = net.bytes_sent + net.bytes_recv
            stats["network_kbs"] = round(total_bytes / 1024 / max(uptime, 1), 1)
            
            # CPU Temperature (if available)
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Try common sensor names
                    for name in ['coretemp', 'cpu_thermal', 'k10temp', 'acpitz']:
                        if name in temps and temps[name]:
                            stats["temperature"] = round(temps[name][0].current, 1)
                            break
            except (AttributeError, KeyError):
                pass  # sensors_temperatures not available on all systems
                
        except Exception as e:
            print(f"⚠️ psutil stats error: {e}")

        # Get GPU stats via nvidia-smi (subprocess)
        try:
            import subprocess
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu',
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(',')
                if len(parts) >= 4:
                    stats["gpu_percent"] = float(parts[0].strip())
                    stats["gpu_memory_used_mb"] = float(parts[1].strip())
                    stats["gpu_memory_total_mb"] = float(parts[2].strip())
                    stats["temperature"] = float(parts[3].strip())  # GPU temp overrides CPU temp
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            # nvidia-smi not available or failed
            pass

        return stats


system_monitor = SystemMonitor()


class BroadcastServer:
    """Simple WebSocket server for broadcasting DAG events."""

    def __init__(self):
        self.connected = set()
        self.loop = None

    async def register(self, websocket):
        self.connected.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self.connected.remove(websocket)

    async def broadcast(self, message: str):
        if not self.connected:
            return
        # Broadcast to all connected clients
        # We need to wrap in a task if we were calling this from outside,
        # but here we assume we are called from an async context or we schedule it.
        # Actually, websockets.broadcast is a helper for this in newer versions,
        # but let's iterate manually for safety on older versions.
        for ws in list(self.connected):
            try:
                await ws.send(message)
            except Exception:
                pass

    async def start(self, host, port):
        # Local import to avoid crash if not installed
        try:
            import websockets

            async with websockets.serve(self.register, host, port):
                print(f"✅ WebSocket Server running on ws://{host}:{port}")
                await asyncio.Future()  # Run forever
        except ImportError:
            print(
                "⚠️ websockets library not found. DAG real-time features disabled."
            )
        except Exception as e:
            print(f"❌ WebSocket Server failed to start: {e}")


def start_websocket_server(host, port):
    """Run WebSocket server in a separate thread."""
    global websocket_server
    websocket_server = BroadcastServer()

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        websocket_server.loop = loop
        loop.run_until_complete(websocket_server.start(host, port))

    t = threading.Thread(target=run, name="websocket-server", daemon=True)
    t.start()


def broadcast_event(event_type: str, data: dict):
    """Helper to broadcast event from anywhere."""
    if not websocket_server or not websocket_server.loop:
        return

    msg = json.dumps({"type": event_type, **data})

    # Schedule sending in the event loop
    asyncio.run_coroutine_threadsafe(
        websocket_server.broadcast(msg), websocket_server.loop
    )


def _safe_int(value: str | None, default: int) -> int:
    """Convert environment values to int with a fallback."""

    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        print(f"⚠️  Invalid integer value '{value}', using default {default}")
        return default


BACKEND_HOST_DEFAULT = os.getenv("BACKEND_HOST", "127.0.0.1") or "127.0.0.1"
BACKEND_PORT_DEFAULT = _safe_int(
    os.getenv("BACKEND_PORT"), 9201
)  # Match dashboard expectation


def _start_llm_warmup() -> None:
    """Fire-and-forget model load so first chat does not block the UI."""

    def _warm() -> None:
        try:
            from mcp_server.services.chat_service import get_chat_service

            chat_service = get_chat_service()
            adapter = (
                chat_service._get_llm()
            )  # Warm the same singleton the app uses
            if adapter and adapter.is_model_available():
                adapter.load_model()
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ LLM warmup skipped: {exc}")

    threading.Thread(target=_warm, name="llm-warmup", daemon=True).start()


def _load_inline_docs() -> dict[str, Any]:
    """Return inline documentation topics.

    In production this could read from a knowledge base or files.
    """
    return {
        "command": {
            "summary": "Execute safe shell commands (echo, ls, pwd, whoami, date, time).",
            "fields": ["command"],
            "security": "Allow list enforced; timeout 5s; output captured.",
        },
        "emotion": {
            "summary": "Analyze emotional tone of short text using transformers or keyword fallback.",
            "fields": ["text"],
            "models": {
                "transformers": SENTIMENT_AVAILABLE,
                "fallback": True,
            },
        },
        "rank": {
            "summary": "Semantic ranking of candidates using sentence-transformers or word overlap fallback.",
            "fields": ["query", "candidates"],
            "models": {
                "semantic": SEMANTIC_AVAILABLE,
                "fallback": True,
            },
        },
        "github": {
            "summary": "List authenticated user repositories (limited subset).",
            "fields": ["per_page"],
            "requires": "GITHUB_TOKEN env",
        },
    }


class RealBackendHandler(BaseHTTPRequestHandler):
    """Handle requests with REAL implementations."""

    def log_message(self, format: str, *args: Any) -> None:
        """Override to reduce noise."""
        pass

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        # Allow loopback calls from browser dashboards that trigger PNA preflights
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        try:
            self.wfile.write(json.dumps(data).encode())
        except BrokenPipeError:
            # Client hung up early (common with browser preflights); avoid noisy tracebacks
            return

    def _start_span(self, method: str, path: str):
        """Start an OpenTelemetry span for the request."""
        if _tracer is None:
            return None
        from opentelemetry import trace
        from opentelemetry.trace import SpanKind

        span = _tracer.start_span(
            f"{method} {path}",
            kind=SpanKind.SERVER,
            attributes={
                "http.method": method,
                "http.url": path,
                "http.target": path,
            },
        )
        return span

    def _end_span(
        self, span, status_code: int = 200, error: str | None = None
    ):
        """End an OpenTelemetry span."""
        if span is None:
            return
        from opentelemetry.trace import Status, StatusCode

        span.set_attribute("http.status_code", status_code)
        if error:
            span.set_status(Status(StatusCode.ERROR, error))
            span.set_attribute("error", True)
        else:
            span.set_status(Status(StatusCode.OK))
        span.end()

    def do_GET(self) -> None:
        """Handle GET requests."""
        span = self._start_span("GET", self.path)
        start_ts = time.time()
        if self.path not in [
            "/health",
            "/api/health",
            "/api/healthz",
            "/ready",
            "/api/readyz",
            "/documentation",
            "/entities/mappings",
            "/models/status",
            "/llm/status",
            "/models/status",
            "/llm/status",
            "/api/llm/status",
            "/api/system/stats",
            "/api/database/metrics",
        ]:
            print(f"📥 GET Request: {self.path}")

        if self.path in ["/health", "/api/health", "/api/healthz"]:
            latency_ms = int((time.time() - start_ts) * 1000)
            self._send_json(
                {
                    "ok": True,
                    "status": "ok",
                    "service": "real-backend",
                    "latency_ms": latency_ms,
                    "ml_models": {
                        "sentiment": SENTIMENT_AVAILABLE,
                        "semantic": SEMANTIC_AVAILABLE,
                        # YoanÉ removed; keep key for compatibility set to False
                        "yoane": False,
                    },
                    "integrations": {
                        "github": bool(github_token and REQUESTS_AVAILABLE)
                    },
                }
            )
        elif self.path in ["/ready", "/api/readyz"]:
            # Simple readiness: models loaded or fallback acceptable
            ready = True  # can extend with deeper diagnostics
            self._send_json({"ready": ready, "timestamp": time.time()})
        elif self.path == "/entities/mappings":
            # Standardized mapping entries
            self._send_json(
                [
                    {
                        "name": "command",
                        "type": "tool",
                        "description": "Execute safe shell commands.",
                    },
                    {
                        "name": "documentation",
                        "type": "tool",
                        "description": "Fetch inline backend docs.",
                    },
                    {
                        "name": "emotion",
                        "type": "ml",
                        "description": "Emotion analysis over text.",
                    },
                    {
                        "name": "rank",
                        "type": "ml",
                        "description": "Semantic or heuristic ranking.",
                    },
                    {
                        "name": "github",
                        "type": "integration",
                        "description": "GitHub repository listing.",
                    },
                    {
                        "name": "models.status",
                        "type": "ml",
                        "description": "Return ML model availability status.",
                    },
                ]
            )
        elif self.path == "/models/status":
            self._send_json(
                {
                    "sentiment": {
                        "available": SENTIMENT_AVAILABLE,
                        "model": (
                            "distilbert-base-uncased-finetuned-sst-2-english"
                            if SENTIMENT_AVAILABLE
                            else None
                        ),
                    },
                    "semantic": {
                        "available": SEMANTIC_AVAILABLE,
                        "model": (
                            "all-MiniLM-L6-v2" if SEMANTIC_AVAILABLE else None
                        ),
                    },
                    "timestamp": time.time(),
                }
            )
        elif self.path in ["/llm/status", "/api/llm/status"]:
            try:
                from mcp_server.model_adapters.local_llm_adapter import (
                    LocalLLMAdapter,
                )
                from mcp_server.services.chat_service import get_chat_service

                chat_service = get_chat_service()
                llm_info: dict[str, Any] = {}

                try:
                    adapter = LocalLLMAdapter.get_instance()
                    llm_info = adapter.get_model_info()
                except Exception as e:
                    import traceback

                    llm_info = {
                        "available": False,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    }

                watchdog = {}
                try:
                    watchdog = chat_service.get_watchdog_status()
                except Exception as e:  # noqa: BLE001
                    watchdog = {"error": str(e)}

                self._send_json(
                    {
                        "llm": llm_info,
                        "watchdog": watchdog,
                        "timestamp": time.time(),
                    }
                )
            except Exception as e:  # noqa: BLE001
                self._send_json({"error": str(e)}, 500)
        elif self.path.startswith("/documentation"):
            # Parse topic query param
            from urllib.parse import parse_qs, urlparse

            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            topic = (qs.get("topic") or [None])[0]
            docs = _load_inline_docs()
            if topic:
                entry = docs.get(topic)
                if not entry:
                    self._send_json(
                        {"error": "topic_not_found", "topic": topic}, 404
                    )
                else:
                    self._send_json({"topic": topic, "documentation": entry})
            else:
                self._send_json(
                    {"topics": list(docs.keys()), "count": len(docs)}
                )
        elif self.path == "/":
            self._send_json(
                {
                    "message": "Real IDE Agents Backend",
                    "version": "1.0",
                    "features": {
                        "sentiment_analysis": SENTIMENT_AVAILABLE,
                        "semantic_similarity": SEMANTIC_AVAILABLE,
                        "github_api": bool(
                            github_token and REQUESTS_AVAILABLE
                        ),
                    },
                }
            )
        elif self.path == "/api/system/stats":
            self._handle_system_stats()
        elif self.path == "/api/database/metrics":
            self._handle_database_metrics()
        elif self.path.startswith("/github/repos"):
            self._handle_github_repos()
        else:
            self._send_json({"error": "Not found"}, 404)
            self._end_span(span, 404)
            if self.path not in ["/metrics", "/favicon.ico"]:  # Reduce noise
                system_monitor.record_request(success=False)
            return

        # Log slow requests to spot real stalls beyond BrokenPipe noise
        duration_ms = int((time.time() - start_ts) * 1000)
        if duration_ms > 1500:
            print(f"⚠️  Slow GET {self.path} took {duration_ms}ms")

        # End the span successfully
        self._end_span(span, 200)
        system_monitor.record_request(success=True)

    def _handle_github_repos(self) -> None:
        """Handle GitHub repos request with REAL GitHub API."""
        if not REQUESTS_AVAILABLE:
            self._send_json({"error": "requests library not available"}, 500)
            return

        if not github_token:
            self._send_json({"error": "GitHub token not configured"}, 401)
            return

        try:
            headers = {
                "Authorization": f"token {github_token}",
                "Accept": "application/vnd.github.v3+json",
            }

            # Real GitHub API call
            response = requests.get(
                "https://api.github.com/user/repos",
                headers=headers,
                params={"per_page": 10, "sort": "updated"},
            )

            if response.status_code == 200:
                repos_data = response.json()
                repos = [
                    {
                        "name": repo["name"],
                        "url": repo["html_url"],
                        "description": repo.get("description", ""),
                        "stars": repo["stargazers_count"],
                        "language": repo.get("language", "Unknown"),
                        "updated_at": repo["updated_at"],
                    }
                    for repo in repos_data
                ]
                self._send_json(
                    {
                        "repos": repos,
                        "total": len(repos),
                        "source": "real_github_api",
                    }
                )
            else:
                self._send_json(
                    {
                        "error": f"GitHub API error: {response.status_code}",
                        "message": response.text[:200],
                    },
                    response.status_code,
                )

        except Exception as e:
            self._send_json(
                {"error": f"GitHub API request failed: {str(e)}"}, 500
            )

    def _handle_system_stats(self) -> None:
        """Return system metrics."""
        self._send_json(system_monitor.get_stats())

    def _handle_database_metrics(self) -> None:
        """Return PostgreSQL database metrics."""
        import asyncio
        try:
            from aura_ia_mcp.services.database_monitor import get_database_monitor
            
            monitor = get_database_monitor()
            # Run async method in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                metrics = loop.run_until_complete(monitor.get_database_metrics())
            finally:
                loop.close()
            
            self._send_json(metrics)
        except ImportError:
            # Database monitor not available - return mock data
            self._send_json({
                "status": "connected",
                "connections": {
                    "active": 3,
                    "idle": 5,
                    "total": 8,
                    "max": 100,
                    "utilization_percent": 8.0
                },
                "database_size": {
                    "bytes": 52428800,
                    "pretty": "50 MB",
                    "mb": 50.0
                },
                "table_sizes": [
                    {"table": "conversations", "size_pretty": "12 MB", "size_bytes": 12582912},
                    {"table": "messages", "size_pretty": "8 MB", "size_bytes": 8388608},
                    {"table": "debates", "size_pretty": "5 MB", "size_bytes": 5242880},
                    {"table": "model_rankings", "size_pretty": "2 MB", "size_bytes": 2097152}
                ],
                "health": {
                    "status": "healthy",
                    "uptime_seconds": 172800,
                    "long_running_queries": 0,
                    "blocked_queries": 0,
                    "accepting_connections": True
                },
                "note": "Mock data - database_monitor not available"
            })
        except Exception as e:
            self._send_json({
                "status": "error",
                "error": str(e)
            }, 500)

    def do_POST(self) -> None:
        """Handle POST requests."""
        span = self._start_span("POST", self.path)
        print(f"📨 POST Request: {self.path}")
        content_length = int(self.headers.get("Content-Length", 0))
        body = (
            self.rfile.read(content_length).decode()
            if content_length > 0
            else "{}"
        )

        try:
            data = json.loads(body)
        except Exception as e:
            print(f"❌ JSON Parse Error: {e}")
            data = {}

        try:
            if self.path == "/command":
                self._handle_real_command(data)
            elif self.path in [
                "/ai/intelligence/mood/analyze",
                "/ai/intelligence/emotion/analyze",
            ]:
                self._handle_real_emotion_analysis(data)
            elif self.path in [
                "/ai/intelligence/rank",
                "/ai/intelligence/ultra/rank",
            ]:
                self._handle_real_ultra_ranking(data)
            elif self.path == "/chat/send":
                self._handle_chat_message(data)
            elif self.path == "/chat/clear":
                self._handle_chat_clear(data)
            elif self.path == "/chat/status":
                self._handle_chat_status(data)
            elif self.path == "/embed":
                self._handle_embed_text(data)
            elif self.path == "/api/dag/simulate":
                self._handle_simulate_workflow(data)
            elif self.path == "/api/debate/simulate":
                self._handle_simulate_debate(data)
            else:
                self._send_json({"error": "Not found"}, 404)
                self._end_span(span, 404)
                system_monitor.record_request(success=False)
                return
            self._end_span(span, 200)
            system_monitor.record_request(success=True)
        except Exception as e:
            self._end_span(span, 500, str(e))
            system_monitor.record_request(success=False)
            raise

    def _handle_real_command(self, data: dict[str, Any]) -> None:
        """Execute REAL system commands safely."""
        command = data.get("command", "")

        if not command:
            self._send_json({"error": "No command provided"}, 400)
            return

        # Safety check - only allow safe commands
        safe_commands = ["echo", "dir", "ls", "pwd", "whoami", "date", "time"]
        command_parts = command.split()

        if not command_parts or command_parts[0] not in safe_commands:
            self._send_json(
                {
                    "error": "Command not allowed for security reasons",
                    "allowed_commands": safe_commands,
                },
                403,
            )
            return
        # Additional hardening: reject metacharacters and chaining
        dangerous = ["&&", "|", ">", "<", ";", "||", "$", "`", '"', "'", "../"]
        if any(tok in command for tok in dangerous):
            self._send_json({"error": "Disallowed characters in command"}, 403)
            return
        # Block variable expansion & grouping attempts
        if "%" in command or "(" in command or ")" in command:
            self._send_json(
                {"error": "Variable expansion / grouping not permitted"}, 403
            )
            return

        try:
            # Execute REAL command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            self._send_json(
                {
                    "result": {
                        "output": result.stdout + result.stderr,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.returncode,
                    },
                    "command": command,
                    "success": result.returncode == 0,
                    "source": "real_command_execution",
                }
            )

        except subprocess.TimeoutExpired:
            self._send_json({"error": "Command timeout"}, 408)
        except Exception as e:
            self._send_json(
                {"error": f"Command execution failed: {str(e)}"}, 500
            )

    def _handle_real_emotion_analysis(self, data: dict[str, Any]) -> None:
        """Perform REAL emotion analysis using transformers."""
        text = data.get("text", "")

        if not text:
            self._send_json({"error": "No text provided"}, 400)
            return

        if SENTIMENT_AVAILABLE:
            try:
                # REAL sentiment analysis using transformers
                result = sentiment_analyzer(text[:512])[0]  # Limit text length

                # Map sentiment to emotion
                label = result["label"].lower()
                score = result["score"]

                emotion_map = {"positive": "happy", "negative": "sad"}

                emotion = emotion_map.get(label, "neutral")

                self._send_json(
                    {
                        "text": text,
                        "emotion": emotion,
                        "mood": emotion,
                        "confidence": score,
                        "source": "real_transformers_model",
                        "model": "distilbert-base-uncased-finetuned-sst-2-english",
                    }
                )

            except Exception as e:
                self._send_json(
                    {"error": f"Sentiment analysis failed: {str(e)}"}, 500
                )
        else:
            # Fallback to keyword-based analysis
            self._fallback_emotion_analysis(text)

    def _fallback_emotion_analysis(self, text: str) -> None:
        """Fallback emotion analysis using keywords."""
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
            emotion = "happy"
            confidence = min(0.95, 0.7 + (positive_count * 0.1))
        elif negative_count > positive_count:
            emotion = "sad"
            confidence = min(0.95, 0.7 + (negative_count * 0.1))
        else:
            emotion = "neutral"
            confidence = 0.75

        self._send_json(
            {
                "text": text,
                "emotion": emotion,
                "mood": emotion,
                "confidence": confidence,
                "source": "fallback_keyword_analysis",
            }
        )

    def _handle_real_ultra_ranking(self, data: dict[str, Any]) -> None:
        """Perform REAL semantic ranking using sentence transformers."""
        query = data.get("query", "")
        candidates = data.get("candidates", [])

        if not query or not candidates:
            self._send_json({"error": "Query and candidates required"}, 400)
            return

        if SEMANTIC_AVAILABLE:
            try:
                query_emb = semantic_model.encode(
                    query, convert_to_tensor=True
                )
                ranked: list[dict[str, Any]] = []
                for cand in candidates:
                    if isinstance(cand, dict):
                        text = cand.get("text") or ""
                    else:
                        text = str(cand)
                    text = str(text)
                    cand_emb = semantic_model.encode(
                        text, convert_to_tensor=True
                    )
                    try:
                        sim_val = util.cos_sim(query_emb, cand_emb)
                        # Handle potential nested tensor/list
                        if hasattr(sim_val, "item"):
                            score = float(sim_val.item())
                        else:
                            score = float(sim_val)
                    except Exception:
                        score = 0.0
                    ranked.append({"candidate": text, "score": score})
                ranked.sort(key=lambda x: x["score"], reverse=True)
                self._send_json(
                    {
                        "query": query,
                        "total": len(ranked),
                        "source": "real_sentence_transformers",
                        "model": "all-MiniLM-L6-v2",
                        "ranked": ranked,
                    }
                )
            except Exception as e:
                self._send_json(
                    {"error": f"Semantic ranking failed: {str(e)}"}, 500
                )
        else:
            # Fallback to simple ranking
            self._fallback_ultra_ranking(query, candidates)

    def _fallback_ultra_ranking(self, query: str, candidates: list) -> None:
        """Fallback ranking using simple text matching."""
        import random

        ranked = []
        query_lower = query.lower()

        for i, candidate in enumerate(candidates):
            text = candidate.get("text", str(candidate))
            text_lower = text.lower()

            # Simple word overlap score
            query_words = set(query_lower.split())
            text_words = set(text_lower.split())
            overlap = len(query_words & text_words)

            score = 0.5 + (overlap * 0.1) + random.uniform(-0.05, 0.05)
            score = min(1.0, max(0.0, score))

            ranked.append(
                {
                    "id": candidate.get("id", str(i)),
                    "text": text,
                    "score": score,
                }
            )

        ranked.sort(key=lambda x: x["score"], reverse=True)

        self._send_json(
            {
                "ranked": ranked,
                "query": query,
                "total": len(candidates),
                "source": "fallback_word_overlap",
            }
        )

    def _handle_chat_message(self, data: dict[str, Any]) -> None:
        """Handle chat messages using the embedded LLM."""
        import asyncio

        message = data.get("message", "")
        mode = data.get("mode", "general")
        conversation_id = data.get("conversation_id", "default")

        if not message:
            self._send_json({"error": "No message provided"}, 400)
            return

        try:
            # Import chat service
            import sys
            from pathlib import Path

            # Ensure src is in path
            src_path = Path(__file__).parent.parent
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            from mcp_server.services.chat_service import get_chat_service

            chat_service = get_chat_service(
                backend_url=f"http://127.0.0.1:{BACKEND_PORT_DEFAULT}"
            )

            # Run async chat in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    chat_service.chat(message, conversation_id, mode)
                )
            finally:
                loop.close()

            self._send_json(
                {
                    "response": result.get("response", ""),
                    "tool_calls": result.get("tool_calls", []),
                    "conversation_id": result.get(
                        "conversation_id", conversation_id
                    ),
                    "mode": result.get("mode", mode),
                    "llm_used": result.get("llm_used", False),
                    "success": True,
                }
            )

        except Exception as e:
            print(f"❌ Chat error: {e}")
            import traceback

            traceback.print_exc()
            self._send_json(
                {
                    "error": str(e),
                    "success": False,
                    "response": f"Chat service error: {str(e)}",
                },
                500,
            )

    def _handle_chat_clear(self, data: dict[str, Any]) -> None:
        """Clear conversation history."""
        conversation_id = data.get("conversation_id", "default")
        
        try:
            import sys
            from pathlib import Path

            src_path = Path(__file__).parent.parent
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            from mcp_server.services.chat_service import get_chat_service

            chat_service = get_chat_service(
                backend_url=f"http://127.0.0.1:{BACKEND_PORT_DEFAULT}"
            )
            
            result = chat_service.clear_conversation(conversation_id)
            
            self._send_json({
                "success": result,
                "message": f"Cleared conversation: {conversation_id}",
                "conversation_id": conversation_id,
            })
            
        except Exception as e:
            print(f"❌ Clear conversation error: {e}")
            self._send_json({
                "error": str(e),
                "success": False,
            }, 500)

    def _handle_chat_status(self, data: dict[str, Any]) -> None:
        """Get chat service status."""
        try:
            import sys
            from pathlib import Path

            src_path = Path(__file__).parent.parent
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            from mcp_server.model_adapters.local_llm_adapter import (
                LocalLLMAdapter,
            )
            from mcp_server.services.chat_service import get_chat_service

            chat_service = get_chat_service()
            llm_info = {}

            try:
                adapter = LocalLLMAdapter.get_instance()
                llm_info = adapter.get_model_info()
            except Exception as e:
                llm_info = {"error": str(e), "available": False}

            self._send_json(
                {
                    "llm": llm_info,
                    "tools_available": len(chat_service.tool_registry.tools),
                    "conversations_active": len(chat_service.conversations),
                    "backend_url": chat_service.backend_url,
                }
            )

        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_embed_text(self, data: dict[str, Any]) -> None:
        """Generate embedding for text using sentence-transformers.

        Request: {"text": "string to embed"}
        Response: {"embedding": [...], "model": "...", "dimensions": int}
        """
        text = data.get("text", "")

        if not text:
            self._send_json({"error": "No text provided"}, 400)
            return

        if SEMANTIC_AVAILABLE:
            try:
                # Use the already-loaded semantic_model (all-MiniLM-L6-v2)
                embedding = semantic_model.encode(
                    [text],
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                embedding_list = embedding[0].tolist()

                self._send_json(
                    {
                        "embedding": embedding_list,
                        "model": "all-MiniLM-L6-v2",
                        "dimensions": len(embedding_list),
                        "source": "real_sentence_transformers",
                    }
                )

            except Exception as e:
                self._send_json(
                    {"error": f"Embedding generation failed: {str(e)}"}, 500
                )
        else:
            # Fallback: return a mock 384-dim embedding
            import hashlib

            # Deterministic pseudo-embedding based on text hash
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            mock_embedding = [
                (int(text_hash[i : i + 2], 16) - 128) / 256.0
                for i in range(0, min(768, len(text_hash)), 2)
            ]
            # Pad or truncate to 384 dimensions
            while len(mock_embedding) < 384:
                mock_embedding.extend(
                    mock_embedding[: 384 - len(mock_embedding)]
                )
            mock_embedding = mock_embedding[:384]

            self._send_json(
                {
                    "embedding": mock_embedding,
                    "model": "fallback_hash_embedding",
                    "dimensions": 384,
                    "source": "fallback_deterministic",
                    "warning": "sentence-transformers not available",
                }
            )

    def _handle_simulate_workflow(self, data: dict[str, Any]) -> None:
        """Simulate a DAG execution flow for visualization verification."""

        def run_simulation():
            time.sleep(1)  # Initial delay

            steps = [
                ("Start", "start", {"status": "running"}),
                ("Start", "complete", {"status": "success"}),
                ("Data_Ingest", "start", {"status": "running"}),
                ("Data_Ingest", "progress", {"percent": 50}),
                (
                    "Data_Ingest",
                    "complete",
                    {"status": "success", "rows": 1500},
                ),
                ("Preprocessing", "start", {"status": "running"}),
                ("Preprocessing", "complete", {"status": "success"}),
                ("Model_Training", "start", {"status": "running"}),
                ("Model_Training", "progress", {"percent": 20, "loss": 0.9}),
                ("Model_Training", "progress", {"percent": 50, "loss": 0.5}),
                ("Model_Training", "progress", {"percent": 80, "loss": 0.2}),
                (
                    "Model_Training",
                    "complete",
                    {"status": "success", "accuracy": 0.95},
                ),
                ("Evaluation", "start", {"status": "running"}),
                ("Evaluation", "complete", {"status": "success"}),
                ("Deployment", "start", {"status": "running"}),
                ("Deployment", "complete", {"status": "success"}),
            ]

            for node, status, payload in steps:
                broadcast_event(
                    "dag_node_update",
                    {
                        "nodeId": node,
                        "status": payload.get("status", "running"),
                        "event": status,
                        "payload": payload,
                    },
                )
                time.sleep(0.8)  # Visualization delay

            broadcast_event("dag_complete", {"status": "success"})

        threading.Thread(target=run_simulation, daemon=True).start()

        self._send_json({"message": "Simulation started", "steps": 6})

    def _handle_simulate_debate(self, data: dict[str, Any]) -> None:
        """Simulate a debate for visualization verification."""

        def run_debate():
            time.sleep(1)

            # Phase 1: Opening
            broadcast_event(
                "debate_event",
                {
                    "phase": "opening",
                    "speaker": "Moderator",
                    "text": "The debate topic is: Artificial General Intelligence safety protocols.",
                },
            )
            time.sleep(2)
            broadcast_event(
                "debate_event",
                {
                    "phase": "opening",
                    "speaker": "Model A (Proponent)",
                    "text": "I argue that strict containment is necessary for all AGI systems.",
                },
            )
            time.sleep(3)
            broadcast_event(
                "debate_event",
                {
                    "phase": "opening",
                    "speaker": "Model B (Opponent)",
                    "text": "Containment limits utility. We should focus on alignment instead.",
                },
            )
            time.sleep(3)

            # Phase 2: Argument
            broadcast_event(
                "debate_event",
                {
                    "phase": "argument",
                    "speaker": "Model A (Proponent)",
                    "text": "Without containment, a misalignment could be catastrophic immediately.",
                },
            )
            time.sleep(3)
            broadcast_event(
                "debate_event",
                {
                    "phase": "rebuttal",
                    "speaker": "Model B (Opponent)",
                    "text": "But an air-gapped AI cannot perform useful real-time inference.",
                },
            )
            time.sleep(3)

            # Phase 3: Verdict
            broadcast_event(
                "debate_event",
                {
                    "phase": "verdict",
                    "speaker": "Judge (Model C)",
                    "text": "Verdict: Proponent argument is stronger on safety, but Opponent wins on utility.",
                },
            )
            time.sleep(2)
            broadcast_event("debate_complete", {"winner": "Draw"})

        threading.Thread(target=run_debate, daemon=True).start()
        self._send_json({"message": "Debate simulation started"})

    def do_OPTIONS(self) -> None:
        """Handle OPTIONS requests for CORS."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()


def run_server(host: str | None = None, port: int | None = None) -> None:
    """Run the REAL backend server."""
    resolved_host = host or os.getenv("BACKEND_HOST") or BACKEND_HOST_DEFAULT
    resolved_port = port or _safe_int(
        os.getenv("BACKEND_PORT"), BACKEND_PORT_DEFAULT
    )
    print("=" * 60)
    print("  🚀 REAL KIRO MCP Backend")
    print("  With Actual ML Models & GitHub API")
    print("=" * 60)
    print()
    print("Features:")
    print(
        f"  {'✅' if SENTIMENT_AVAILABLE else '⚠️ '} Sentiment Analysis (transformers)"
    )
    print(
        f"  {'✅' if SEMANTIC_AVAILABLE else '⚠️ '} Semantic Similarity (sentence-transformers)"
    )
    print(
        f"  {'✅' if github_token and REQUESTS_AVAILABLE else '⚠️ '} GitHub API Integration"
    )
    print()

    server_address = (resolved_host, resolved_port)
    # Use a threaded server so in-process tool calls (health/model status) do not block chat requests.
    try:
        httpd = ThreadingHTTPServer(server_address, RealBackendHandler)
    except Exception:
        httpd = HTTPServer(server_address, RealBackendHandler)
    print(f"🚀 Server running on http://{resolved_host}:{resolved_port}")
    print(f"💬 Chat: http://{resolved_host}:{resolved_port}/chat/send")
    print(f"🔍 GitHub: http://{resolved_host}:{resolved_port}/github/repos")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Start WebSocket Server
    start_websocket_server(resolved_host, 9209)

    # Background warmup so the first chat does not incur model load latency
    _start_llm_warmup()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        httpd.shutdown()


def main():
    """Entry point for the backend server."""
    run_server()


if __name__ == "__main__":
    main()
