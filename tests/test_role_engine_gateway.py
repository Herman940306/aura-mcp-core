from aura_ia_mcp.ops.role_engine.policy_gateway import evaluate


def test_policy_gateway_allows_default_action():
    assert evaluate("default", "execute") is True
