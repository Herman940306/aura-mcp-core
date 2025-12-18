def run(payload):
    role = payload.get("role", "undefined")
    # Stub decision logic
    return {"allowed": True, "risk_score": 5, "role": role}
