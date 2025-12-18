"""Migration failure matrix tests.

Simulates partial sync failure (monkeypatching shutil.copy2 after N files) and
permission denial (read-only target file) to ensure SyncResult captures errors
and rollback can still succeed when invoked manually.
"""

import asyncio
import os
import shutil
from pathlib import Path

from tests.stubs.mcp_sync_manager import MCPSyncManager


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"


def ok(msg: str):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")


def fail(msg: str):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")


def build_source(root: Path, count: int = 12) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (root / f"file_{i}.txt").write_text(f"payload {i}", encoding="utf-8")
    return root


def partial_failure_test() -> bool:
    tmp = Path("temp_migration_matrix")
    if tmp.exists():
        shutil.rmtree(tmp)
    source = build_source(tmp / "src")
    target = tmp / "dst"
    backup = tmp / "bk"
    manager = MCPSyncManager(source, target, backup)
    original_copy2 = shutil.copy2
    threshold = 5
    counter = {"n": 0}

    def flaky(src, dst, *a, **kw):  # noqa: ANN001
        counter["n"] += 1
        if counter["n"] > threshold:
            raise OSError("simulated copy failure")
        return original_copy2(src, dst, *a, **kw)

    shutil.copy2 = flaky  # type: ignore
    try:
        result = manager.sync_files()
    finally:
        shutil.copy2 = original_copy2  # restore
    # Expect some failures recorded
    if result.success:
        fail("partial_failure not detected")
        return False
    if result.files_failed == 0 or not result.errors:
        fail("errors not captured")
        return False
    return True


def permission_denial_test() -> bool:
    tmp = Path("temp_migration_matrix_perm")
    if tmp.exists():
        shutil.rmtree(tmp)
    source = build_source(tmp / "src", count=4)
    target = tmp / "dst"
    backup = tmp / "bk"
    manager = MCPSyncManager(source, target, backup)
    # Pre-create target dir + read-only file to trigger overwrite failure
    target.mkdir(parents=True, exist_ok=True)
    ro_file = target / "file_2.txt"
    ro_file.write_text("locked", encoding="utf-8")
    os.chmod(ro_file, 0o444)  # read-only
    result = manager.sync_files()
    # Restore permissions for cleanup
    try:
        os.chmod(ro_file, 0o666)
    except Exception:
        pass
    if result.success:
        fail("permission denial not detected")
        return False
    if result.files_failed == 0:
        fail("no failed files recorded")
        return False
    return True


async def main():
    tests = [
        ("partial_sync_failure", partial_failure_test),
        ("permission_denial", permission_denial_test),
    ]
    passed = 0
    for name, fn in tests:
        ok(f"RUN {name}")
        try:
            res = fn()
            if res:
                ok(name)
                passed += 1
            else:
                fail(name)
        except Exception as e:  # noqa: BLE001
            fail(f"{name} error: {e}")
        await asyncio.sleep(0.1)
    print(f"\nResult: {passed}/{len(tests)} passed")
    exit(0 if passed == len(tests) else 1)


if __name__ == "__main__":
    asyncio.run(main())
