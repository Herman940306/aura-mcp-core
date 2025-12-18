import os

from aura_ia_mcp.core import config
from aura_ia_mcp.main import create_app
from tests.testutils import make_sync_client


def reset():
    if hasattr(config.get_settings, "cache_clear"):
        config.get_settings.cache_clear()


def test_training_denied_without_autonomy():
    os.environ["AURA_SAFE_MODE"] = "false"
    os.environ["ENABLE_TRAINING"] = "true"
    os.environ["ENABLE_AUTONOMY"] = "false"  # Explicitly disable
    reset()
    app = create_app()
    client = make_sync_client(app)
    r = client.post("/training/start")
    assert r.status_code == 403
    assert "autonomy disabled" in r.json()["detail"]


def test_training_allowed_with_autonomy():
    os.environ["AURA_SAFE_MODE"] = "false"
    os.environ["ENABLE_TRAINING"] = "true"
    os.environ["ENABLE_AUTONOMY"] = "true"
    reset()
    app = create_app()
    client = make_sync_client(app)
    r = client.post("/training/start")
    assert r.status_code == 200
    assert r.json()["risk_score"] >= 0


def test_training_denied_in_safe_mode_even_with_autonomy():
    os.environ["AURA_SAFE_MODE"] = "true"
    os.environ["ENABLE_TRAINING"] = "true"
    os.environ["ENABLE_AUTONOMY"] = "true"
    reset()
    app = create_app()
    client = make_sync_client(app)
    r = client.post("/training/start")
    assert r.status_code in (423, 403)
    assert any(
        phrase in r.json()["detail"] for phrase in ("SAFE MODE", "autonomy")
    )


def teardown_module():
    for k in ["AURA_SAFE_MODE", "ENABLE_TRAINING", "ENABLE_AUTONOMY"]:
        os.environ.pop(k, None)
    reset()
