from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    action: str
    role: str | None = None
    risk_score: float = 0.0


class PolicyGateway:
    """Simple policy gateway stub.

    Rules:
    - ROLE_LOAD allowed.
    - ROLE_MUTATE needs approved=True and not SAFE MODE.
    - TRAIN_START needs autonomy enabled and not SAFE MODE.
    - Unknown actions denied.
    """

    def __init__(self, strict: bool = True):
        self.strict = strict

    def evaluate(self, action: str, context: Dict[str, Any]) -> PolicyDecision:
        role = context.get("role")
        safe_mode = context.get("safe_mode", False)
        autonomy_enabled = context.get("autonomy_enabled", False)
        approved = context.get("approved", False)

        if action == "ROLE_LOAD":
            return PolicyDecision(
                True,
                "Allowed: read-only role load",
                action,
                role,
                0.0,
            )

        if action == "ROLE_MUTATE":
            if safe_mode:
                return PolicyDecision(
                    False,
                    "Denied: SAFE MODE active",
                    action,
                    role,
                    1.0,
                )
            if not approved:
                return PolicyDecision(
                    False,
                    "Denied: mutation not approved",
                    action,
                    role,
                    0.7,
                )
            return PolicyDecision(
                True,
                "Allowed: approved mutation",
                action,
                role,
                0.3,
            )

        if action == "TRAIN_START":
            if safe_mode:
                return PolicyDecision(
                    False,
                    "Denied: SAFE MODE active",
                    action,
                    role,
                    1.0,
                )
            if not autonomy_enabled:
                return PolicyDecision(
                    False,
                    "Denied: autonomy disabled",
                    action,
                    role,
                    0.8,
                )
            return PolicyDecision(
                True,
                "Allowed: autonomy enabled",
                action,
                role,
                0.4,
            )

        return PolicyDecision(
            False,
            "Denied: unknown action",
            action,
            role,
            1.0,
        )


_gateway_singleton: PolicyGateway | None = None


def get_gateway() -> PolicyGateway:
    # simple memoization without 'global' mutation elsewhere
    if _gateway_singleton is None:
        # Create singleton instance (simple memoization)
        globals()["_gateway_singleton"] = PolicyGateway(strict=True)
    return _gateway_singleton  # type: ignore[return-value]


def evaluate(action: str, context: Dict[str, Any]) -> PolicyDecision:
    return get_gateway().evaluate(action, context)
