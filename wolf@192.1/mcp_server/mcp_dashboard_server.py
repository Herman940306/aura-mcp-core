"""MCP Dashboard Backend Server
Provides REST API for the HTML dashboard

Project Creator: Herman Swanepoel
Version: 1.0
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

try:
    import psutil
    import requests
    from flask import Flask, jsonify, request
    from flask_cors import CORS
except ImportError:
    print("Installing required packages...")
    os.system("pip install flask flask-cors psutil requests")
    import psutil
    import requests
    from flask import Flask, jsonify, request
    from flask_cors import CORS
app = Flask(__name__)
CORS(app)  # Enable CORS for local HTML file access

# Configuration
BACKEND_URL = os.getenv("IDE_AGENTS_BACKEND_URL", "http://127.0.0.1:8001")
TELEMETRY_FILE = Path("logs/mcp_tool_spans.jsonl")
CONFIG_FILE = Path(".env")

# Settings storage
settings = {
    "ultra_enabled": True,
    "semantic_ranking": True,
    "predictions": True,
    "emotion_detection": True,
    "learning_analytics": True,
    "adaptive_personality": False,
}


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


@app.route("/api/mcp/status", methods=["GET"])
def mcp_status():
    """Get MCP server status"""
    try:
        start = time.time()
        response = requests.get(f"{BACKEND_URL}/health", timeout=3)
        duration = (time.time() - start) * 1000  # Convert to ms

        if response.status_code == 200:
            data = response.json()
            return jsonify(
                {
                    "status": "online",
                    "response_time": round(duration, 2),
                    "data": data,
                }
            )
        else:
            return (
                jsonify({"status": "error", "code": response.status_code}),
                500,
            )
    except requests.exceptions.ConnectionError:
        return (
            jsonify({"status": "offline", "error": "Connection refused"}),
            503,
        )
    except requests.exceptions.Timeout:
        return jsonify({"status": "timeout", "error": "Request timeout"}), 504
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/ai/status", methods=["GET"])
def ai_status():
    """Get AI intelligence system status"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/ai/intelligence/status", timeout=3
        )
        if response.status_code == 200:
            data = response.json()

            # Count active engines
            active_engines = 0
            total_engines = 5
            if "engines" in data:
                active_engines = sum(
                    1
                    for e in data["engines"].values()
                    if e.get("status") == "active"
                )

            return jsonify(
                {
                    "status": "operational",
                    "active_engines": active_engines,
                    "total_engines": total_engines,
                    "data": data,
                }
            )
        else:
            return (
                jsonify({"status": "error", "code": response.status_code}),
                500,
            )
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "unavailable",
                    "error": str(e),
                    "active_engines": 0,
                    "total_engines": 5,
                }
            ),
            503,
        )


@app.route("/api/system/resources", methods=["GET"])
def system_resources():
    """Get system resource usage"""
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory().percent

        # Get disk usage for the appropriate drive
        if os.name == "nt":
            disk = psutil.disk_usage("C:\\").percent
        else:
            disk = psutil.disk_usage("/").percent

        return jsonify(
            {
                "cpu": round(cpu, 1),
                "memory": round(memory, 1),
                "disk": round(disk, 1),
            }
        )
    except Exception as e:
        return (
            jsonify({"error": str(e), "cpu": 0, "memory": 0, "disk": 0}),
            500,
        )


@app.route("/api/telemetry/stats", methods=["GET"])
def telemetry_stats():
    """Get telemetry statistics"""
    if not TELEMETRY_FILE.exists():
        return jsonify(
            {
                "total": 0,
                "success": 0,
                "failed": 0,
                "success_rate": 0,
                "avg_duration": 0,
                "tools": [],
            }
        )

    try:
        stats = {"total": 0, "success": 0, "failed": 0, "tools": {}}

        total_duration = 0

        with open(TELEMETRY_FILE) as f:
            lines = f.readlines()

            # Process last 100 entries
            for line in lines[-100:]:
                try:
                    span = json.loads(line)
                    stats["total"] += 1

                    if span.get("success", False):
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1

                    tool_name = span.get("tool_name", "unknown")
                    if tool_name not in stats["tools"]:
                        stats["tools"][tool_name] = {
                            "count": 0,
                            "success": 0,
                            "failed": 0,
                        }

                    stats["tools"][tool_name]["count"] += 1
                    if span.get("success", False):
                        stats["tools"][tool_name]["success"] += 1
                    else:
                        stats["tools"][tool_name]["failed"] += 1

                    duration = span.get("duration_ms", 0)
                    total_duration += duration

                except json.JSONDecodeError:
                    continue

        # Calculate averages and rates
        success_rate = (
            (stats["success"] / stats["total"] * 100)
            if stats["total"] > 0
            else 0
        )
        avg_duration = (
            (total_duration / stats["total"]) if stats["total"] > 0 else 0
        )

        # Get top 5 tools
        top_tools = sorted(
            stats["tools"].items(), key=lambda x: x[1]["count"], reverse=True
        )[:5]

        return jsonify(
            {
                "total": stats["total"],
                "success": stats["success"],
                "failed": stats["failed"],
                "success_rate": round(success_rate, 1),
                "avg_duration": round(avg_duration, 2),
                "tools": [
                    {
                        "name": name,
                        "calls": data["count"],
                        "success": data["success"],
                        "failed": data["failed"],
                    }
                    for name, data in top_tools
                ],
            }
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "error": str(e),
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "success_rate": 0,
                    "avg_duration": 0,
                    "tools": [],
                }
            ),
            500,
        )


@app.route("/api/settings", methods=["GET"])
def get_settings():
    """Get current settings"""
    return jsonify(settings)


@app.route("/api/activities", methods=["GET"])
def get_activities():
    """Get recent MCP activities from telemetry"""
    if not TELEMETRY_FILE.exists():
        return jsonify([])

    try:
        activities = []
        with open(TELEMETRY_FILE) as f:
            lines = f.readlines()

            # Get last 20 entries
            for line in lines[-20:]:
                try:
                    span = json.loads(line)
                    activities.append(
                        {
                            "tool": span.get("tool_name", "unknown"),
                            "details": span.get("method", "Processing..."),
                            "status": (
                                "completed"
                                if span.get("success", False)
                                else "failed"
                            ),
                            "duration": span.get("duration_ms", 0),
                            "timestamp": span.get("timestamp_ms", 0),
                        }
                    )
                except json.JSONDecodeError:
                    continue

        return jsonify(activities)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/settings", methods=["POST"])
def update_settings():
    """Update settings"""
    global settings
    data = request.json

    # Update settings
    if "ultra_enabled" in data:
        settings["ultra_enabled"] = data["ultra_enabled"]
    if "semantic_ranking" in data:
        settings["semantic_ranking"] = data["semantic_ranking"]
    if "predictions" in data:
        settings["predictions"] = data["predictions"]
    if "emotion_detection" in data:
        settings["emotion_detection"] = data["emotion_detection"]
    if "learning_analytics" in data:
        settings["learning_analytics"] = data["learning_analytics"]
    if "adaptive_personality" in data:
        settings["adaptive_personality"] = data["adaptive_personality"]

    # Update environment variables
    try:
        update_env_file(settings)
    except Exception as e:
        print(f"Warning: Could not update .env file: {e}")

    return jsonify({"status": "success", "settings": settings})


def update_env_file(settings: dict):
    """Update .env file with new settings"""
    env_vars = {
        "IDE_AGENTS_ULTRA_ENABLED": (
            "true" if settings["ultra_enabled"] else "false"
        ),
        "IDE_AGENTS_SEMANTIC_RANKING": (
            "true" if settings["semantic_ranking"] else "false"
        ),
        "IDE_AGENTS_PREDICTIONS": (
            "true" if settings["predictions"] else "false"
        ),
        "IDE_AGENTS_EMOTION_DETECTION": (
            "true" if settings["emotion_detection"] else "false"
        ),
        "IDE_AGENTS_LEARNING_ANALYTICS": (
            "true" if settings["learning_analytics"] else "false"
        ),
        "IDE_AGENTS_ADAPTIVE_PERSONALITY": (
            "true" if settings["adaptive_personality"] else "false"
        ),
    }

    # Read existing .env
    existing_vars = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    existing_vars[key.strip()] = value.strip()

    # Update with new values
    existing_vars.update(env_vars)

    # Write back
    with open(CONFIG_FILE, "w") as f:
        for key, value in existing_vars.items():
            f.write(f"{key}={value}\n")


if __name__ == "__main__":
    print("=" * 80)
    print("  KIRO_MCP Dashboard Server")
    print("=" * 80)
    print(f"  Backend URL: {BACKEND_URL}")
    print("  Dashboard API: http://localhost:5000")
    print("  Open: mcp_monitor_dashboard.html in your browser")
    print("=" * 80)
    print()

    app.run(host="0.0.0.0", port=5000, debug=False)
