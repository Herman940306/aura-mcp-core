"""Role Engine Service with policy evaluation and guard integration."""

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roles", tags=["role_engine"])


class RoleEvaluationRequest(BaseModel):
    """Request to evaluate role permissions."""

    role: str = Field(..., description="Role name")
    action: str = Field(..., description="Action to evaluate")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )


class GuardCheckRequest(BaseModel):
    """Request to run guards on content."""

    text: str = Field(..., description="Text to check")
    guards: list[str] = Field(
        default=["hallucination", "honesty"],
        description="Guards to run",
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context"
    )


@router.get("/active")
async def active_roles():
    """Get list of active roles."""
    try:
        from ..ops.role_engine.loader import get_registry

        registry = get_registry()
        roles = registry.list_roles()

        return {
            "roles": roles,
            "count": len(roles),
            "version": registry.version,
            "loaded_at": registry.loaded_at,
        }
    except Exception as e:
        logger.exception("Error fetching active roles")
        return {"roles": ["default"], "count": 1, "error": str(e)}


@router.get("/roles/{role_name}")
async def get_role(role_name: str):
    """Get details for a specific role."""
    try:
        from ..ops.role_engine.loader import get_registry

        registry = get_registry()
        role = registry.get_role(role_name)

        if not role:
            raise HTTPException(
                status_code=404, detail=f"Role '{role_name}' not found"
            )

        from dataclasses import asdict

        return asdict(role)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error fetching role '{role_name}'")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_role(request: RoleEvaluationRequest):
    """Evaluate role permissions for an action."""
    try:
        from ..ops.role_engine.loader import get_registry

        registry = get_registry()
        role = registry.get_role(request.role)

        if not role:
            return {
                "role": request.role,
                "action": request.action,
                "allowed": False,
                "reason": f"Role '{request.role}' not found",
                "risk_score": 1.0,
            }

        # Check if role has required capability
        # Map actions to capabilities (simplified)
        action_capability_map = {
            "code": "code",
            "merge": "merge",
            "deploy": "orchestrate",
            "query": "query",
            "approve": "approve_security",
        }

        required_capability = action_capability_map.get(request.action)

        if required_capability and required_capability in role.capabilities:
            allowed = True
            reason = (
                f"Role '{role.name}' has capability '{required_capability}'"
            )
        else:
            allowed = False
            reason = f"Role '{role.name}' lacks required capability"

        # Calculate risk score from role profile
        risk_score = role.scoring_profile.risk_factor

        return {
            "role": request.role,
            "action": request.action,
            "allowed": allowed,
            "reason": reason,
            "risk_score": risk_score,
            "confidence_weight": role.scoring_profile.confidence_weight,
            "priority": role.scoring_profile.priority,
        }

    except Exception as e:
        logger.exception("Error evaluating role")
        return {
            "role": request.role,
            "action": request.action,
            "allowed": False,
            "reason": f"Evaluation error: {str(e)}",
            "risk_score": 1.0,
        }


@router.post("/guards/check")
async def check_guards(request: GuardCheckRequest):
    """Run guards on content."""
    results = {}

    try:
        # Run hallucination checker
        if "hallucination" in request.guards:
            from ..ops.guards.hallucination_checker import get_checker

            checker = get_checker()
            hallucination_result = checker.check_text(
                request.text, request.context
            )

            from dataclasses import asdict

            results["hallucination"] = asdict(hallucination_result)

        # Run honesty policy
        if "honesty" in request.guards:
            from ..ops.guards.honesty_policy import get_policy

            policy = get_policy()
            honesty_result = policy.analyze_text(request.text)

            from dataclasses import asdict

            results["honesty"] = asdict(honesty_result)

        # Run schema validator (if schema provided in context)
        if "schema" in request.guards and "schema" in request.context:
            from ..ops.guards.schema_validator import get_validator

            validator = get_validator()

            # Assume text can be parsed as JSON
            try:
                import json

                data = json.loads(request.text)
                validation_result = validator.validate_data(
                    data, schema=request.context["schema"]
                )

                from dataclasses import asdict

                results["schema"] = asdict(validation_result)
            except json.JSONDecodeError:
                results["schema"] = {
                    "valid": False,
                    "errors": ["Invalid JSON"],
                }

        # Calculate overall pass/fail
        all_passed = True
        for guard_name, guard_result in results.items():
            if (
                guard_name == "hallucination"
                and guard_result.get("hallucination_detected")
                or guard_name == "honesty"
                and not guard_result.get("compliant")
                or guard_name == "schema"
                and not guard_result.get("valid")
            ):
                all_passed = False

        return {
            "passed": all_passed,
            "guards": results,
            "text_length": len(request.text),
        }

    except Exception as e:
        logger.exception("Error running guards")
        return {"passed": False, "error": str(e), "guards": results}


@router.get("/health")
async def health():
    """Health check for role engine service."""
    try:
        from ..ops.role_engine.loader import get_registry

        registry = get_registry()
        role_count = len(registry.roles)

        return {
            "status": "healthy",
            "roles_loaded": role_count,
            "version": registry.version,
        }
    except Exception as e:
        logger.exception("Health check failed")
        return {"status": "unhealthy", "error": str(e)}


def register(app: FastAPI, settings) -> None:
    """Register role engine service.

    Args:
        app: FastAPI application
        settings: Application settings
    """
    app.include_router(router)
    logger.info("Role Engine service registered")
