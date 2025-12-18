#!/usr/bin/env python3
"""
Advanced role selector:
 - loads registry
 - uses heuristics + placeholder ML model
 - returns roles with confidence and explanation
"""
import json
import math

REG = "ops/role_engine/role_registry_v2.json"
MODEL_STUB = "training/roles/selector_model.stub"


def load_registry():
    return json.load(open(REG))["roles"]


def pseudo_model_score(text, role_spec):
    # placeholder: TF-like scoring: keyword overlap / length normalization
    score = 0.0
    txt = (
        role_spec.get("purpose", "")
        + " "
        + " ".join(role_spec.get("responsibilities", []))
    ).lower()
    for tok in set(text.lower().split()):
        if len(tok) > 3 and tok in txt:
            score += 1.0
    # scale by priority
    p = role_spec.get("scoring_profile", {}).get("priority", 5)
    return score * (p / 10.0)


def calibrate_confidence(raw_score):
    # simple sigmoid to [0,1]
    return 1.0 / (1.0 + math.exp(-raw_score + 1.0))


def select_roles(task_text, topk=3):
    reg = load_registry()
    cand = []
    for name, spec in reg.items():
        raw = pseudo_model_score(task_text, spec)
        conf = calibrate_confidence(raw)
        cand.append(
            {
                "role": name,
                "raw_score": raw,
                "confidence": conf,
                "explain": [
                    f"raw:{raw:.2f}",
                    "priority:{spec.get('scoring_profile',{}).get('priority',5)}",
                ],
            }
        )
    cand = sorted(cand, key=lambda x: x["confidence"], reverse=True)
    return cand[:topk]


if __name__ == "__main__":
    import json
    import sys

    t = " ".join(sys.argv[1:]) or "run unit tests and propose patch"
    print(json.dumps(select_roles(t, 3), indent=2))
