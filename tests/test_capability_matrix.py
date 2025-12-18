import os

import httpx
import pytest
from httpx import ASGITransport

from aura_ia_mcp.main import create_app


def _set_env(safe: bool, autonomy: bool, training: bool, role_mut: bool):
    os.environ["AURA_SAFE_MODE"] = "true" if safe else "false"
    os.environ["ENABLE_AUTONOMY"] = "true" if autonomy else "false"
    os.environ["ENABLE_TRAINING"] = "true" if training else "false"
    os.environ["ENABLE_ROLE_MUTATION"] = "true" if role_mut else "false"


def _status(code: int):
    if code == 423:
        return "locked"
    if code == 403:
        return "forbidden"
    return "ok"


@pytest.mark.asyncio
async def test_capability_matrix_basic():
    combos = [
        (True, False, False, False),  # safe mode
        (False, True, True, True),  # everything enabled
        (False, True, False, True),  # autonomy only
        (False, False, True, False),  # training flag but autonomy off
    ]
    results = []
    for safe, autonomy, training, role_mut in combos:
        _set_env(safe, autonomy, training, role_mut)
        app = create_app()
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:  # type: ignore[arg-type]
            rm_resp = await client.post(
                "/roles/mutate", json={"approved": True}
            )
            tr_resp = await client.post(
                "/training/start", json={"episodes": 1}
            )
            results.append(
                {
                    "safe_mode": safe,
                    "autonomy": autonomy,
                    "training": training,
                    "role_mut": role_mut,
                    "role_mut_status": _status(rm_resp.status_code),
                    "training_status": _status(tr_resp.status_code),
                }
            )

    assert results[0]["role_mut_status"] == "locked"
    assert results[0]["training_status"] == "locked"
    assert results[1]["role_mut_status"] == "ok"
    assert results[1]["training_status"] == "ok"
    assert results[2]["role_mut_status"] == "ok"
    assert results[2]["training_status"] == "forbidden"
    assert results[3]["training_status"] == "forbidden"
    assert results[2]["training_status"] == "forbidden"
    assert results[3]["training_status"] == "forbidden"
