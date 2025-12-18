#!/usr/bin/env python3
"""
Decode a base64-encoded zip file (ignoring whitespace) and extract its contents.

Usage examples:
  python scripts/decode_unzip_b64.py -i readmes.zip.b64 -o .
  python scripts/decode_unzip_b64.py --input path/to/file.b64 --out out_dir

By default, writes a sibling .zip next to the input and extracts to the output directory.
"""
from __future__ import annotations

import argparse
import base64
import re
import sys
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def _strip_whitespace_b64(text: str) -> str:
    # Remove all whitespace characters which can break base64 decoding
    return re.sub(r"\s+", "", text)


def _filter_base64_chars(text: str) -> str:
    # Keep only standard base64 charset characters
    # This drops any heredoc markers or shell lines accidentally included
    parts = re.findall(r"[A-Za-z0-9+/=]+", text)
    return "".join(parts)


def _base64_run_candidates(raw_text: str) -> list[str]:
    # Preserve order, but remove whitespace first for run detection
    no_ws = _strip_whitespace_b64(raw_text)
    # Find contiguous runs of only base64 chars
    runs = re.findall(r"[A-Za-z0-9+/=]+", no_ws)
    # Sort by length desc to try the most promising first
    runs.sort(key=len, reverse=True)
    # Deduplicate while preserving order
    seen = set()
    uniq: list[str] = []
    for r in runs:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


def _looks_like_zip(data: bytes) -> bool:
    return len(data) >= 4 and data[:4] == b"PK\x03\x04"


def decode_b64_to_bytes(b64_text: str) -> bytes:
    candidates = _base64_run_candidates(b64_text)
    last_err: Exception | None = None
    for cand in candidates:
        if len(cand) < 64:
            # too small to be a real zip typically; skip
            continue
        for decoder in (base64.b64decode, base64.urlsafe_b64decode):
            try:
                data = (
                    decoder(cand, validate=False)
                    if decoder is base64.b64decode
                    else decoder(cand)
                )
            except Exception as ex:
                last_err = ex
                continue
            if not _looks_like_zip(data):
                # Not a zip file header
                continue
            # Quick try opening as zip to validate
            try:
                with ZipFile(BytesIO(data)):
                    pass
                return data
            except Exception as ex:
                last_err = ex
                # We'll try salvage in extraction phase, but still prefer a candidate that opens
                continue
    # Fallback: try decoding entire filtered text
    filtered = _filter_base64_chars(_strip_whitespace_b64(b64_text))
    try:
        data = base64.b64decode(filtered, validate=False)
        if _looks_like_zip(data):
            return data
    except Exception as ex:
        last_err = ex
    raise ValueError(f"Failed to decode a valid ZIP from base64: {last_err}")


def extract_zip_bytes(zip_bytes: bytes, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with ZipFile(BytesIO(zip_bytes)) as zf:
            zf.extractall(dest_dir)
    except BadZipFile as ex:
        # Try to salvage by trimming to proper ZIP boundaries
        trimmed = _try_salvage_zip(zip_bytes)
        if trimmed is None:
            raise ValueError(f"Decoded data is not a valid zip: {ex}") from ex
        with ZipFile(BytesIO(trimmed)) as zf:
            zf.extractall(dest_dir)


def _try_salvage_zip(data: bytes) -> bytes | None:
    # Look for start (local file header) and end (EOCD) signatures
    start = data.find(b"PK\x03\x04")
    endsig = b"PK\x05\x06"  # EOCD signature
    end = data.rfind(endsig)
    if start == -1 or end == -1:
        return None
    if end + 22 > len(data):
        return None
    # EOCD comment length is 2 bytes little-endian at offset +20
    try:
        comment_len = int.from_bytes(data[end + 20 : end + 22], "little")
    except Exception:
        return None
    eocd_end = end + 22 + comment_len
    if eocd_end > len(data):
        return None
    return data[start:eocd_end]


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decode a base64 zip and extract it."
    )
    parser.add_argument(
        "-i", "--input", required=True, help="Path to .b64 file"
    )
    parser.add_argument(
        "-o",
        "--out",
        default=".",
        help="Directory to extract into (default: current dir)",
    )
    parser.add_argument(
        "--zip-out",
        default=None,
        help="Optional path to write the decoded .zip file",
    )
    parser.add_argument(
        "--no-write-zip",
        action="store_true",
        help="Do not write the intermediate .zip file",
    )

    args = parser.parse_args(argv)

    in_path = Path(args.input)
    out_dir = Path(args.out)

    if not in_path.exists():
        print(f"Input file not found: {in_path}", file=sys.stderr)
        return 1

    try:
        b64_text = in_path.read_text(encoding="utf-8", errors="ignore")
        zip_bytes = decode_b64_to_bytes(b64_text)
    except Exception as ex:
        print(f"Error decoding base64: {ex}", file=sys.stderr)
        return 2

    # Optionally write the zip file
    if not args.no_write_zip:
        if args.zip_out:
            zip_path = Path(args.zip_out)
        elif in_path.name.lower().endswith(".zip.b64"):
            # Preserve original .zip name
            zip_path = in_path.with_name(
                in_path.name[:-4]
            )  # drop only the trailing .b64
        elif in_path.suffix.lower() == ".b64":
            zip_path = in_path.with_suffix(".zip")
        else:
            zip_path = in_path.with_name(in_path.name + ".zip")
        try:
            write_bytes(zip_path, zip_bytes)
            print(f"Wrote zip: {zip_path}")
        except Exception as ex:
            print(f"Failed writing zip '{zip_path}': {ex}", file=sys.stderr)
            return 3

    # Extract
    try:
        extract_zip_bytes(zip_bytes, out_dir)
        print(f"Extracted to: {out_dir.resolve()}")
    except Exception as ex:
        # Diagnostics: show first few bytes and length
        head = zip_bytes[:8]
        sig = " ".join(f"{b:02X}" for b in head)
        print(
            f"Error extracting zip: {ex} (len={len(zip_bytes)}, head={sig})",
            file=sys.stderr,
        )
        return 4

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
