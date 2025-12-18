import argparse
import json
from pathlib import Path
from typing import Any

# Minimal ingestion stub: writes JSONL ready for external indexer to read.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir", help="Directory of .txt/.md/.json docs")
    ap.add_argument("output_file", help="Path to output JSONL")
    ap.add_argument(
        "--namespace", default="default", help="Namespace/collection name"
    )
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    out = Path(args.output_file)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with out.open("w", encoding="utf-8") as f:
        for p in input_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".txt", ".md", ".json"}:
                payload: dict[str, Any] = {
                    "text": p.read_text(encoding="utf-8", errors="ignore"),
                    "path": str(p),
                    "namespace": args.namespace,
                }
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                count += 1
    print(f"Wrote {count} records to {out}")


if __name__ == "__main__":
    main()
