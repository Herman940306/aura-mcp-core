"""API endpoints for policy management."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .policy_migrator import PolicyMigrator
from .policy_version_manager import PolicyVersionManager

router = APIRouter(prefix="/admin/policies", tags=["Policy Management"])

# Initialize managers
version_manager = PolicyVersionManager()
migrator = PolicyMigrator(version_manager)


class CreateVersionRequest(BaseModel):
    version: str
    description: str
    policy_content: str
    created_by: str = "api"
    migration_script: str | None = None


class MigrateRequest(BaseModel):
    to_version: str
    dry_run: bool = False


@router.post("/versions")
def create_policy_version(request: CreateVersionRequest):
    """Create a new policy version."""
    # Validate policy first
    validation = version_manager.validate_policy(request.policy_content)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid policy: {', '.join(validation['errors'])}",
        )

    try:
        policy_version = version_manager.create_version(
            version=request.version,
            description=request.description,
            policy_content=request.policy_content,
            created_by=request.created_by,
            migration_script=request.migration_script,
        )
        return {"status": "created", "version": policy_version.version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions")
def list_policy_versions():
    """List all policy versions."""
    versions = version_manager.list_versions()
    return {
        "current_version": version_manager.get_current_version(),
        "versions": [
            {
                "version": v.version,
                "description": v.description,
                "created_at": v.created_at,
                "created_by": v.created_by,
            }
            for v in versions
        ],
    }


@router.get("/versions/{version}")
def get_policy_version(version: str):
    """Get details of a specific version."""
    policy_version = version_manager.get_version(version)
    if not policy_version:
        raise HTTPException(status_code=404, detail="Version not found")

    policy_content = version_manager.get_policy_content(version)

    return {**policy_version.__dict__, "policy_content": policy_content}


@router.post("/migrate")
def migrate_policy(request: MigrateRequest):
    """Migrate to a new policy version."""
    # Validate migration
    validation = migrator.validate_migration(
        version_manager.get_current_version() or "none", request.to_version
    )

    if not validation["can_migrate"] and not request.dry_run:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot migrate: {', '.join(validation['issues'])}",
        )

    # Perform migration
    record = migrator.migrate(
        to_version=request.to_version, dry_run=request.dry_run
    )

    if record.status == "failed":
        raise HTTPException(status_code=500, detail=record.error)

    return {
        "migration_id": record.migration_id,
        "status": record.status,
        "from_version": record.from_version,
        "to_version": record.to_version,
        "backup_path": record.backup_path if not request.dry_run else None,
    }


@router.post("/rollback/{migration_id}")
def rollback_migration(migration_id: str):
    """Rollback a migration."""
    success = migrator.rollback(migration_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Rollback failed. Migration not found or not completed.",
        )

    return {"status": "rolled_back", "migration_id": migration_id}


@router.get("/migrations")
def get_migration_history():
    """Get migration history."""
    history = migrator.get_migration_history()
    return {
        "migrations": [
            {
                "migration_id": m.migration_id,
                "from_version": m.from_version,
                "to_version": m.to_version,
                "timestamp": m.timestamp,
                "status": m.status,
                "error": m.error,
            }
            for m in history
        ]
    }


def register_policy_routes(app):
    """Register policy management routes."""
    app.include_router(router)
