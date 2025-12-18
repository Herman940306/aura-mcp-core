from fastapi import Depends, HTTPException, status

from .config import Settings, get_settings

SAFE_MODE_LOCKED_DETAIL = "Operation gated by SAFE MODE"
CAPABILITY_DISABLED_DETAIL = "Capability flag disabled for this operation"


def require_safe_mode_off(settings: Settings = Depends(get_settings)):
    """Block when SAFE MODE is active."""
    if settings.AURA_SAFE_MODE:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=SAFE_MODE_LOCKED_DETAIL,
        )
    return True


def require_capability(capability: str):
    """Factory enforcing SAFE MODE off and a capability flag."""

    def _dep(settings: Settings = Depends(get_settings)):
        if settings.AURA_SAFE_MODE:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=SAFE_MODE_LOCKED_DETAIL,
            )
        enabled = getattr(settings, capability, False)
        if not enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=CAPABILITY_DISABLED_DETAIL,
            )
        return True

    return _dep
