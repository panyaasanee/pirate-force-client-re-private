#!/usr/bin/env python3
"""Verify the pinned pilot binary and emit bounded PE metadata."""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_SIZE = 14_759_424
EXPECTED_SHA256 = "C528BF43070E2789170F41B6E3E28CCEC6B57BDC594EE73DFA061188A5D1E4BD"

def analyze(path: Path) -> dict[str, int | str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest().upper()
    if len(raw) != EXPECTED_SIZE:
        raise SystemExit(f"size mismatch: expected {EXPECTED_SIZE}, got {len(raw)}")
    if digest != EXPECTED_SHA256:
        raise SystemExit(f"sha256 mismatch: expected {EXPECTED_SHA256}, got {digest}")
    if raw[:2] != b"MZ":
        raise SystemExit("missing DOS MZ signature")
    pe_offset = struct.unpack_from("<I", raw, 0x3C)[0]
    if raw[pe_offset:pe_offset + 4] != b"PE\0\0":
        raise SystemExit("missing PE signature")
    machine, sections, timestamp = struct.unpack_from("<HHI", raw, pe_offset + 4)
    optional_magic = struct.unpack_from("<H", raw, pe_offset + 24)[0]
    return {
        "path": path.as_posix(),
        "size_bytes": len(raw),
        "sha256": digest,
        "pe_offset": pe_offset,
        "machine": machine,
        "section_count": sections,
        "coff_timestamp": timestamp,
        "optional_header_magic": optional_magic,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", nargs="?", default="client/GameClient.bin")
    args = parser.parse_args()
    print(json.dumps(analyze(Path(args.binary)), indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
