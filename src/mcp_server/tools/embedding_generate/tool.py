def run(payload):
    text = payload.get("text", "")
    # Simple stub vector (length only)
    return {"vector": [len(text)], "dim": 1}
