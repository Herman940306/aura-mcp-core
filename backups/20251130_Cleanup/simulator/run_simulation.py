#!/usr/bin/env python3
import json
import os
import time

SIMDIR = "simulator"
os.makedirs(SIMDIR, exist_ok=True)


def run_case(case):
    # simple run: calls are_service simulate through local file
    path = os.path.join(SIMDIR, "case_" + str(int(time.time())) + ".json")
    open(path, "w").write(json.dumps(case))
    return {"ok": True, "case": path}


if __name__ == "__main__":
    print(run_case({"text": "sample scenario", "expected": "Coordinator"}))
