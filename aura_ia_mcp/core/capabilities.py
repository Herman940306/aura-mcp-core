import os
from dataclasses import dataclass

from .audit import audit_capability_state, audit_safe_mode_transition
from .config import get_settings


@dataclass(frozen=True)
class CapabilityState:
    safe_mode: bool
    enable_autonomy: bool
    enable_training: bool
    enable_role_mutation: bool

    @property
    def effective_autonomy(self) -> bool:
        return (not self.safe_mode) and self.enable_autonomy

    @property
    def effective_training(self) -> bool:
        return (not self.safe_mode) and self.enable_training

    @property
    def effective_role_mutation(self) -> bool:
        return (not self.safe_mode) and self.enable_role_mutation

    def export(self) -> dict[str, bool]:
        return {
            "safe_mode": self.safe_mode,
            "ENABLE_AUTONOMY": self.enable_autonomy,
            "ENABLE_TRAINING": self.enable_training,
            "ENABLE_ROLE_MUTATION": self.enable_role_mutation,
        }


def _get_actor() -> str:
    # Derive actor (CI, local user, or process) for auditing
    return os.getenv("GITHUB_ACTOR") or os.getenv("USER") or "unknown"


def load_capabilities() -> CapabilityState:
    settings = get_settings()
    state = CapabilityState(
        safe_mode=settings.AURA_SAFE_MODE,
        enable_autonomy=settings.ENABLE_AUTONOMY,
        enable_training=settings.ENABLE_TRAINING,
        enable_role_mutation=settings.ENABLE_ROLE_MUTATION,
    )
    return state


_previous_state: CapabilityState | None = None


def initialize_capabilities() -> CapabilityState:
    global _previous_state
    current = load_capabilities()
    actor = _get_actor()
    if _previous_state is None:
        audit_safe_mode_transition(current.safe_mode, actor, current.export())
        audit_capability_state(
            actor,
            changed=current.export(),
            full_state=current.export(),
        )
    else:
        changed: dict[str, bool] = {}
        prev_map = _previous_state.export()
        curr_map = current.export()
        for k, v in curr_map.items():
            if prev_map.get(k) != v:
                changed[k] = v
        if changed:
            if "safe_mode" in changed:
                audit_safe_mode_transition(current.safe_mode, actor, curr_map)
            audit_capability_state(actor, changed=changed, full_state=curr_map)
    _previous_state = current
    return current


__all__ = ["CapabilityState", "initialize_capabilities", "load_capabilities"]
__all__ = ["CapabilityState", "initialize_capabilities", "load_capabilities"]
