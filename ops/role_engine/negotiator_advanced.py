#!/usr/bin/env python3
"""
Negotiator: accepts multiple role opinions and decides:
 - Accept top if confidence > threshold
 - If tied/low confidence -> escalate to Coordinator / human
 - Supports weighted voting
"""


def arbitrate(opinions, threshold=0.7):
    # opinions: [{"role":"X","confidence":0.8, "actor":"agent-A"},...]
    opinions_sorted = sorted(
        opinions, key=lambda x: x["confidence"], reverse=True
    )
    top = opinions_sorted[0]
    if top["confidence"] >= threshold:
        return {
            "decision": "accept",
            "role": top["role"],
            "confidence": top["confidence"],
        }
    # check weighted votes
    votes = {}
    for o in opinions:
        votes[o["role"]] = votes.get(o["role"], 0.0) + o["confidence"]
    winner = max(votes.items(), key=lambda x: x[1])
    # if winner weight strong enough
    if winner[1] >= threshold:
        return {"decision": "voted", "role": winner[0], "weight": winner[1]}
    return {"decision": "escalate", "to": "Coordinator", "votes": votes}
