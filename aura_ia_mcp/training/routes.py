import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from aura_ia_mcp.ops.role_engine.policy_gateway import (
    evaluate as policy_evaluate,
)

from ..core.audit import audit_policy_decision
from ..core.config import get_settings
from ..core.safe_mode import require_capability
from .episode_logger import get_episode_logger
from .pr_orchestrator import PROrchestrator

training_router = APIRouter(prefix="/training", tags=["training"])


class TrainingStartRequest(BaseModel):
    run_id: str | None = None
    episodes: int = Field(1, ge=1)
    dry_run: bool = False
    task_description: str = Field(
        "", description="Description of the training task"
    )


class PRProposeRequest(BaseModel):
    run_id: str
    title: str = Field(..., description="PR title")
    description: str = Field("", description="PR description")
    changes: list[dict[str, Any]] = Field(
        ..., description="List of code changes"
    )
    dry_run: bool = Field(
        False, description="Simulate without creating actual PR"
    )
    repo_owner: str = Field("", description="GitHub repository owner")
    repo_name: str = Field("", description="GitHub repository name")
    base_branch: str = Field("main", description="Target branch")


@training_router.post("/start")
def start_training(
    payload: TrainingStartRequest | None = None,
    _=Depends(require_capability("ENABLE_TRAINING")),
):
    """Start a new SICD training run."""
    settings = get_settings()
    decision = policy_evaluate(
        action="TRAIN_START",
        context={
            "role": None,
            "safe_mode": settings.AURA_SAFE_MODE,
            "autonomy_enabled": settings.ENABLE_AUTONOMY,
        },
    )
    params = payload.dict() if payload else {}
    audit_policy_decision(
        decision,
        {"params": params},
        route="/training/start",
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)

    # Generate run_id if not provided
    run_id = (
        payload.run_id if payload and payload.run_id else str(uuid.uuid4())[:8]
    )

    # Start first episode
    logger = get_episode_logger()
    episode = logger.start_episode(
        run_id=run_id,
        episode_number=1,
        task_description=payload.task_description if payload else "",
        context={"total_episodes": payload.episodes if payload else 1},
    )

    return {
        "status": "started",
        "detail": decision.reason,
        "risk_score": decision.risk_score,
        "run_id": run_id,
        "episode_id": episode.episode_id,
        "episodes": payload.episodes if payload else 1,
        "dry_run": payload.dry_run if payload else False,
    }


@training_router.post("/propose-pr")
async def propose_pr(
    payload: PRProposeRequest,
    _=Depends(require_capability("ENABLE_TRAINING")),
):
    """Generate and optionally create a GitHub PR with proposed changes."""
    settings = get_settings()
    decision = policy_evaluate(
        action="PR_PROPOSE",
        context={
            "role": None,
            "safe_mode": settings.AURA_SAFE_MODE,
            "autonomy_enabled": settings.ENABLE_AUTONOMY,
            "change_count": len(payload.changes),
        },
    )

    audit_policy_decision(
        decision,
        {"run_id": payload.run_id, "changes": len(payload.changes)},
        route="/training/propose-pr",
    )

    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason)

    # Create orchestrator and generate proposal
    orchestrator = PROrchestrator(
        repo_owner=payload.repo_owner,
        repo_name=payload.repo_name,
    )

    proposal = orchestrator.generate_proposal(
        changes=payload.changes,
        title=payload.title,
        description=payload.description,
        run_id=payload.run_id,
    )

    # Log the PR proposal action
    logger = get_episode_logger()
    logger.log_action(
        "pr_proposal",
        {
            "proposal_id": proposal.proposal_id,
            "title": proposal.title,
            "changes": len(proposal.changes),
            "dry_run": payload.dry_run,
        },
    )

    # Create actual PR if not dry run
    result = await orchestrator.create_github_pr(
        proposal=proposal,
        base_branch=payload.base_branch,
        dry_run=payload.dry_run,
    )

    # Log outcome
    logger.log_outcome(
        "pr_created" if result["status"] == "created" else "pr_failed",
        result,
    )

    logger.update_metrics(changes_proposed=len(payload.changes))

    return {
        "proposal_id": proposal.proposal_id,
        "branch": proposal.branch_name,
        "result": result,
        "risk_score": decision.risk_score,
    }


@training_router.get("/episodes/{run_id}")
def list_episodes(
    run_id: str, _=Depends(require_capability("ENABLE_TRAINING"))
):
    """List all episodes for a training run."""
    logger = get_episode_logger()
    episode_ids = logger.list_episodes(run_id=run_id)

    return {
        "run_id": run_id,
        "episode_count": len(episode_ids),
        "episodes": episode_ids,
    }


@training_router.get("/episodes/{run_id}/{episode_id}")
def get_episode(
    run_id: str,
    episode_id: str,
    _=Depends(require_capability("ENABLE_TRAINING")),
):
    """Get detailed episode information."""
    logger = get_episode_logger()
    episode = logger.load_episode(episode_id)

    if not episode:
        raise HTTPException(
            status_code=404, detail=f"Episode {episode_id} not found"
        )

    if episode.run_id != run_id:
        raise HTTPException(
            status_code=400,
            detail="Episode does not belong to specified run_id",
        )

    # Convert to dict for response
    from dataclasses import asdict

    return asdict(episode)


@training_router.get("/runs/{run_id}/summary")
def get_run_summary(
    run_id: str, _=Depends(require_capability("ENABLE_TRAINING"))
):
    """Get summary statistics for a training run."""
    logger = get_episode_logger()
    summary = logger.get_run_summary(run_id)

    return summary
