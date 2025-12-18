import argparse
import json
import os
import sys

REQUIRED_DIRS = [
    "aura_ia_mcp",
    "aura_ia_mcp/core",
    "aura_ia_mcp/services",
    "aura_ia_mcp/ops/role_engine",
    "aura_ia_mcp/ops/guards",
    "aura_ia_mcp/training",
    "SBOM",
    "logs",
]
REQUIRED_FILES = [
    "AURA_IA_MCP_PRD.md",
    "aura_ia_mcp/main.py",
    "aura_ia_mcp/core/config.py",
]
PORTS = [9200, 9201, 9202, 9203, 9204, 9205, 9206]


def check_dirs():
    missing = [d for d in REQUIRED_DIRS if not os.path.isdir(d)]
    return missing


def check_files():
    missing = [f for f in REQUIRED_FILES if not os.path.isfile(f)]
    return missing


def check_ports():
    # naive port presence check by grepping config file
    with open("aura_ia_mcp/core/config.py", encoding="utf-8") as f:
        text = f.read()
    absent = [p for p in PORTS if str(p) not in text]
    return absent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true")
    args = parser.parse_args()
    result = {
        "missing_dirs": check_dirs(),
        "missing_files": check_files(),
        "absent_ports": check_ports(),
    }
    ok = all(len(v) == 0 for v in result.values())
    print(json.dumps(result))
    if not ok:
        sys.exit(1 if args.ci else 0)


if __name__ == "__main__":
    main()
