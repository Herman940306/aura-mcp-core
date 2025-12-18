"""Docker compose stack health verification.

Checks:
1. docker-compose.yml structure (expected services & ports)
2. Local port reachability & HTTP status for each service
3. Minimal response sanity (content length > 0)

Exit codes:
0 = all good
1 = structural mismatch
2 = network / HTTP failures

Designed to be dependency‑light (uses stdlib only).
"""

from __future__ import annotations

import json
import pathlib
import socket
import sys
import time
from typing import Any, TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # Fallback: simple manual parse for our limited keys

COMPOSE_PATH = pathlib.Path("docker-compose.yml")


class ServiceSpec(TypedDict):
    container_name: str
    ports: list[tuple[int, int]]
    checks: list[str]


EXPECTED: dict[str, ServiceSpec] = {
    "aura-ia-ml": {
        "container_name": "aura_ia_ml",
        "ports": [(9201, 8001)],
        "checks": ["http://localhost:9201/health"],
    },
    "aura-ia-gateway": {
        "container_name": "aura_ia_gateway",
        "ports": [(9200, 8000)],
        "checks": [
            "http://localhost:9200/readyz",
            "http://localhost:9200/performance",
        ],
    },
    "aura-ia-dashboard": {
        "container_name": "aura_ia_dashboard",
        "ports": [(9205, 80)],
        "checks": ["http://localhost:9205/"],
    },
}


def load_compose() -> dict[str, Any]:
    if not COMPOSE_PATH.exists():
        raise FileNotFoundError(
            "docker-compose.yml not found at repository root"
        )
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    if yaml:
        data_loaded = yaml.safe_load(text)
        if isinstance(data_loaded, dict):
            return data_loaded
        return {"root": data_loaded}
    # Fallback parser for 'services:' blocks with 'ports:' lines.
    data: dict[str, dict[str, Any]] = {"services": {}}
    current = None
    for line in text.splitlines():
        if (
            line.startswith("  ")
            and not line.startswith("    ")
            and ":" in line
        ):
            current = line.strip().rstrip(":")
            data["services"].setdefault(current, {})
            continue
        if current is None:
            continue
        if "ports:" in line:
            data["services"][current]["ports"] = []
            continue
        if '- "' in line and "ports" in data["services"].get(current, {}):
            port_map = line.split('"')[1]
            host, container = port_map.split(":")
            data["services"][current]["ports"].append(f"{host}:{container}")
    return data


def verify_structure(compose: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    services = compose.get("services", {})
    for svc, spec in EXPECTED.items():
        if svc not in services:
            errors.append(f"Missing service: {svc}")
            continue
        declared = services[svc]
        # Ports
        declared_ports = declared.get("ports", [])
        normalized = []
        for p in declared_ports:
            if isinstance(p, str):
                normalized.append(p)
            elif isinstance(p, dict):
                # docker compose can allow long syntax
                host = p.get("published") or p.get("host")
                target = p.get("target") or p.get("container")
                if host and target:
                    normalized.append(f"{host}:{target}")
        ports_list: list[tuple[int, int]] = spec.get("ports", [])
        expected_port_strs = [f"{h}:{c}" for (h, c) in ports_list]
        for ep in expected_port_strs:
            if ep not in normalized:
                errors.append(
                    f"Port mapping mismatch for {svc}: expected {ep} not found"
                )
        cname = declared.get("container_name")
        if cname != spec["container_name"]:
            expected_cname = spec.get("container_name", "")
            msg = (
                "Container name mismatch for "
                f"{svc}: expected {expected_cname}; "
                f"got {cname[:32]}"
            )
            errors.append(msg)
    return (len(errors) == 0, errors)


def port_open(
    port: int,
    host: str = "127.0.0.1",
    timeout: float = 1.0,
) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except OSError:
            return False


def http_check(url: str, timeout: float = 2.5) -> tuple[bool, str]:
    req = Request(url, headers={"User-Agent": "mcp-stack-verifier/1"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = resp.status
            content = resp.read(256)
            if status >= 200 and status < 400 and len(content) > 0:
                return True, f"HTTP {status} OK len={len(content)}"
            msg = f"Unexpected status (status={status}, len={len(content)})"
            return False, msg
    except HTTPError as e:
        return False, f"HTTPError status={e.code}"
    except URLError as e:
        return False, f"URLError {e.reason}"
    except (OSError, ValueError) as e:  # pragma: no cover
        return False, f"Error: {e}"


def main() -> int:
    start = time.time()
    try:
        compose = load_compose()
    except (FileNotFoundError, OSError, ValueError) as e:
        print(
            json.dumps(
                {
                    "status": "error",
                    "stage": "load_compose",
                    "error": str(e),
                }
            )
        )
        return 1

    ok_struct, struct_errors = verify_structure(compose)
    if not ok_struct:
        print(
            json.dumps(
                {
                    "status": "error",
                    "stage": "structure",
                    "errors": struct_errors,
                },
                indent=2,
            )
        )
        return 1

    http_failures: list[dict[str, str]] = []
    for svc, spec in EXPECTED.items():
        ports_list = spec.get("ports", [])
        checks_list = spec.get("checks", [])
        for host_port, _container_port in ports_list:
            if not port_open(int(host_port)):
                http_failures.append(
                    {
                        "service": svc,
                        "port": str(host_port),
                        "error": "port closed",
                    }
                )
        for check_url in checks_list:
            ok, detail = http_check(str(check_url))
            if not ok:
                http_failures.append(
                    {"service": svc, "url": check_url, "error": detail}
                )

    duration_ms = int((time.time() - start) * 1000)
    if http_failures:
        print(
            json.dumps(
                {
                    "status": "error",
                    "stage": "http_checks",
                    "failures": http_failures,
                    "duration_ms": duration_ms,
                },
                indent=2,
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": "ok",
                "services_verified": list(EXPECTED.keys()),
                "duration_ms": duration_ms,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    code = main()
    sys.exit(code)
