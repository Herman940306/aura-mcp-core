from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aura_ia_mcp.core.audit import audit_policy_decision
from aura_ia_mcp.core.safe_mode import require_capability
from aura_ia_mcp.ops.role_engine.policy_gateway import (
    evaluate as policy_evaluate,
)


class MutationRequest(BaseModel):
    approved: bool = False


role_mutation_router = APIRouter(prefix="/roles", tags=["roles"])


@role_mutation_router.post("/mutate")
def mutate_role(
    payload: MutationRequest,
    _cap=Depends(require_capability("ENABLE_ROLE_MUTATION")),
):
    decision = policy_evaluate(
        action="ROLE_MUTATE",
        context={
            "role": "example",
            "safe_mode": False,
            "approved": payload.approved,
        },
    )
    audit_policy_decision(
        decision,
        {"payload": payload.model_dump()},
        route="/roles/mutate",
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    return {
        "status": "mutated",
        "detail": decision.reason,
        "risk_score": decision.risk_score,
    }


@role_mutation_router.get("/load")
def load_role():
    decision = policy_evaluate(
        "ROLE_LOAD",
        {"role": "example", "safe_mode": False},
    )
    audit_policy_decision(
        decision,
        {"payload": {}},
        route="/roles/load",
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)
    return {
        "role": decision.role or "example",
        "detail": decision.reason,
        "risk_score": decision.risk_score,
    }
