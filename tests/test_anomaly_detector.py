import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from mcp_server.security import anomaly_detector, audit_logger

# Seed some events
for i in range(12):
    audit_logger.rate_limited(f"tool{i%3}")
for i in range(5):
    audit_logger.approval_requested("ide_agents_command", f"action{i}")

summary = anomaly_detector.analyze(3600)
print(json.dumps(summary, indent=2))
assert "events" in summary
assert isinstance(summary.get("anomalies"), list)
