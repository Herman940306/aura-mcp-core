import os

from aura_ia_mcp.core import config
from aura_ia_mcp.main import create_app
from tests.testutils import make_sync_client


def reset_settings():
    if hasattr(config.get_settings, "cache_clear"):
        config.get_settings.cache_clear()


def test_role_load_allowed():
    os.environ["AURA_SAFE_MODE"] = "false"
    reset_settings()
    app = create_app()
    client = make_sync_client(app)
    r = client.get("/roles/load")
    assert r.status_code == 200, r.text
    assert r.json()["detail"].startswith("Allowed")


def test_role_mutate_denied_without_approval():
    os.environ["AURA_SAFE_MODE"] = "false"
    os.environ["ENABLE_ROLE_MUTATION"] = "true"
    reset_settings()
    app = create_app()
    client = make_sync_client(app)
    r = client.post("/roles/mutate", json={"approved": False})
    assert r.status_code == 403, r.text
    assert "mutation not approved" in r.json()["detail"]


def test_role_mutate_denied_in_safe_mode():
    os.environ["AURA_SAFE_MODE"] = "true"
    os.environ["ENABLE_ROLE_MUTATION"] = "true"
    reset_settings()
    app = create_app()
    client = make_sync_client(app)
    r = client.post("/roles/mutate", json={"approved": True})
    # SAFE MODE gating returns 423 before policy; adjust if ordering changes
    assert r.status_code in (423, 403)
    # Accept either detail from SAFE MODE or mutation not approved
    assert any(
        phrase in r.json()["detail"]
        for phrase in ("SAFE MODE", "mutation not approved")
    )


def teardown_module():
    for k in ["AURA_SAFE_MODE", "ENABLE_ROLE_MUTATION"]:
        os.environ.pop(k, None)
    reset_settings()
