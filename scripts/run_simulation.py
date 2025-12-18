#!/usr/bin/env python3
import json
import os
import time
import uuid
from typing import Any

SIMDIR = "data/simulations"
os.makedirs(SIMDIR, exist_ok=True)


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    """
    Run a simulation case for the Role Engine.

    Args:
        case: Dictionary containing simulation parameters
              e.g. {"text": "sample scenario", "expected": "Coordinator"}

    Returns:
        Dict with result status and path to case file
    """
    sim_id = str(uuid.uuid4())
    timestamp = int(time.time())
    filename = f"case_{timestamp}_{sim_id[:8]}.json"
    path = os.path.join(SIMDIR, filename)

    simulation_record = {
        "id": sim_id,
        "timestamp": timestamp,
        "case": case,
        "status": "pending",
    }

    with open(path, "w") as f:
        json.dump(simulation_record, f, indent=2)

    return {"ok": True, "case_path": path, "sim_id": sim_id}


if __name__ == "__main__":
    # Example usage
    result = run_case({"text": "sample scenario", "expected": "Coordinator"})
    print(json.dumps(result, indent=2))
