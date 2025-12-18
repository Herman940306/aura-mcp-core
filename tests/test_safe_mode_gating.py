import os

from aura_ia_mcp.core import config
from aura_ia_mcp.main import create_app
from tests.testutils import make_sync_client


def reset_settings_env():
    # Clear settings cache so new env vars are read
    if hasattr(config.get_settings, "cache_clear"):
        config.get_settings.cache_clear()


def test_training_blocked_in_safe_mode():
    # Explicitly enable SAFE MODE to test blocking behavior
    os.environ["AURA_SAFE_MODE"] = "true"
    os.environ.pop("ENABLE_TRAINING", None)
    reset_settings_env()
    app = create_app()
    client = make_sync_client(app)
    r = client.post("/training/start")
    assert r.status_code == 423, r.text
    assert "SAFE MODE" in r.json()["detail"]


def test_training_allowed_when_safe_mode_off_and_flag_enabled():
    os.environ["AURA_SAFE_MODE"] = "false"
    os.environ["ENABLE_TRAINING"] = "true"
    os.environ["ENABLE_AUTONOMY"] = "true"
    reset_settings_env()
    app = create_app()
    client = make_sync_client(app)
    r = client.post("/training/start")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "started"


def test_role_mutation_blocked_without_flag():
    os.environ["AURA_SAFE_MODE"] = "false"
    os.environ["ENABLE_ROLE_MUTATION"] = "false"  # Explicitly disable
    reset_settings_env()
    app = create_app()
    client = make_sync_client(app)
    r = client.post("/roles/mutate", json={"approved": True})
    assert r.status_code == 403, r.text
    assert "Capability" in r.json()["detail"]


def test_role_mutation_blocked_in_safe_mode_even_with_flag():
    os.environ["AURA_SAFE_MODE"] = "true"
    os.environ["ENABLE_ROLE_MUTATION"] = "true"
    reset_settings_env()
    app = create_app()
    client = make_sync_client(app)
    r = client.post("/roles/mutate", json={"approved": True})
    assert r.status_code == 423, r.text
    assert "SAFE MODE" in r.json()["detail"]


def teardown_module():
    # Clean environment modifications
    for k in [
        "AURA_SAFE_MODE",
        "ENABLE_TRAINING",
        "ENABLE_ROLE_MUTATION",
        "ENABLE_AUTONOMY",
    ]:
        os.environ.pop(k, None)
    reset_settings_env()
