import time


def run(payload):
    start = time.time()
    q = payload.get("query", "")
    # Stub: return empty results
    latency_ms = int((time.time() - start) * 1000)
    return {"results": [], "latency_ms": latency_ms, "query": q}
