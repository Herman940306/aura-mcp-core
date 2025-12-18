import os


def test_registry_exists():
    assert os.path.exists("ops/role_engine/role_registry_v2.json")


def test_schema_exists():
    assert os.path.exists("ops/role_engine/role_schema.json")


def test_selector_stub_runs():
    import subprocess

    p = subprocess.run(
        ["python3", "mcp/roles/selector_advanced.py", "run", "unit", "tests"],
        capture_output=True, check=False,
    )
    assert p.returncode == 0
