"""
Negotiator: accepts multiple role opinions and decides:
 - Accept top if confidence > threshold
 - If tied/low confidence -> escalate to Coordinator / human
 - Supports weighted voting
"""

from typing import Any


def arbitrate(
    opinions: list[dict[str, Any]], threshold: float = 0.7
) -> dict[str, Any]:
    """
    Arbitrate between multiple role opinions.

    Args:
        opinions: List of dicts like [{"role":"X","confidence":0.8, "actor":"agent-A"},...]
        threshold: Confidence threshold for automatic acceptance

    Returns:
        Dict with decision result
    """
    if not opinions:
        return {"decision": "escalate", "reason": "no_opinions"}

    # Sort by confidence descending
    opinions_sorted = sorted(
        opinions, key=lambda x: x.get("confidence", 0.0), reverse=True
    )
    top = opinions_sorted[0]

    # If top confidence meets threshold, accept it
    if top.get("confidence", 0.0) >= threshold:
        return {
            "decision": "accept",
            "role": top.get("role"),
            "confidence": top.get("confidence"),
            "actor": top.get("actor"),
        }

    # Check weighted votes
    votes: dict[str, float] = {}
    for o in opinions:
        role = o.get("role", "unknown")
        conf = o.get("confidence", 0.0)
        votes[role] = votes.get(role, 0.0) + conf

    if not votes:
        return {"decision": "escalate", "reason": "no_valid_votes"}

    # Find winner by total weight
    winner_role, winner_weight = max(votes.items(), key=lambda x: x[1])

    # If winner weight strong enough (aggregate confidence)
    if winner_weight >= threshold:
        return {
            "decision": "voted",
            "role": winner_role,
            "weight": winner_weight,
            "votes": votes,
        }

    return {
        "decision": "escalate",
        "to": "Coordinator",
        "votes": votes,
        "reason": "low_confidence_consensus",
    }
