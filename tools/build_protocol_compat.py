#!/usr/bin/env python3
"""Build a lossless compatibility view of the two Pirate Force registries."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path


WIRE_ID_RE = re.compile(r"^0x[0-9A-Fa-f]{4}$")
PROTOCOL_REQUIRED_COLUMNS = {
    "name",
    "name_va",
    "reg_site_va",
    "id_global_va",
    "getter_va",
    "vtable_va",
    "serializer_va",
    "handler_va",
    "file_off_reg",
    "file_off_name",
    "file_off_getter",
    "file_off_vtable",
    "file_off_serializer_ptr",
    "file_off_handler_ptr",
    "source",
}


def wire_id(name: str) -> str:
    value = sum((index + 1) * ord(char) for index, char in enumerate(name)) & 0xFFFF
    return f"0x{value:04X}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_legacy(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) != 2:
            raise ValueError(f"{path}:{line_number}: expected 2 tab-separated fields")
        row_id, name = parts
        if not WIRE_ID_RE.fullmatch(row_id):
            raise ValueError(f"{path}:{line_number}: invalid wire id {row_id!r}")
        calculated = wire_id(name)
        normalized_row_id = f"0x{row_id[2:].upper()}"
        if calculated != normalized_row_id:
            raise ValueError(
                f"{path}:{line_number}: {name}: stored {row_id}, calculated {calculated}"
            )
        if name in rows:
            raise ValueError(f"{path}:{line_number}: duplicate name {name!r}")
        rows[name] = calculated
    return rows


def load_protocol(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fieldnames = reader.fieldnames or []
        missing = PROTOCOL_REQUIRED_COLUMNS.difference(fieldnames)
        if missing:
            raise ValueError(f"{path}: missing required columns: {sorted(missing)}")
        rows: dict[str, dict[str, str]] = {}
        for line_number, row in enumerate(reader, 2):
            name = row["name"]
            if not name:
                raise ValueError(f"{path}:{line_number}: empty name")
            if name in rows:
                raise ValueError(f"{path}:{line_number}: duplicate name {name!r}")
            rows[name] = row
    return fieldnames, rows


def build(legacy_path: Path, protocol_path: Path, output_path: Path) -> dict[str, object]:
    legacy = load_legacy(legacy_path)
    protocol_fields, protocol = load_protocol(protocol_path)
    legacy_names = set(legacy)
    protocol_names = set(protocol)
    all_names = legacy_names | protocol_names

    output_fields = [
        "wire_id",
        "name",
        "in_legacy_registry",
        "in_protocol_registry",
        *[field for field in protocol_fields if field != "name"],
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=output_fields,
            delimiter="\t",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        for name in sorted(all_names, key=lambda item: (int(wire_id(item), 16), item)):
            source = protocol.get(name, {})
            writer.writerow(
                {
                    "wire_id": wire_id(name),
                    "name": name,
                    "in_legacy_registry": "1" if name in legacy else "0",
                    "in_protocol_registry": "1" if name in protocol else "0",
                    **{field: source.get(field, "") for field in protocol_fields if field != "name"},
                }
            )

    summary: dict[str, object] = {
        "legacy_rows": len(legacy_names),
        "protocol_rows": len(protocol_names),
        "shared_rows": len(legacy_names & protocol_names),
        "legacy_only_rows": len(legacy_names - protocol_names),
        "protocol_only_rows": len(protocol_names - legacy_names),
        "union_rows": len(all_names),
        "legacy_only_names": sorted(legacy_names - protocol_names),
        "legacy_sha256": sha256(legacy_path),
        "protocol_sha256": sha256(protocol_path),
        "output_sha256": sha256(output_path),
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--verify-pilot-snapshot",
        action="store_true",
        help="Fail unless the two inputs match the audited 2026-08-26 pilot snapshot.",
    )
    args = parser.parse_args()
    summary = build(args.legacy, args.protocol, args.output)
    if args.verify_pilot_snapshot:
        expected = {
            "legacy_rows": 327,
            "protocol_rows": 519,
            "shared_rows": 310,
            "legacy_only_rows": 17,
            "protocol_only_rows": 209,
            "union_rows": 536,
            "legacy_sha256": "60d5beb91804942ef1866ac406354596727a24f9d247d13489075cc3972de869",
            "protocol_sha256": "27daac0c6fbbc45d88281c31b98e3a8b56f421bd1e8bc16f970fdff5716cfb4d",
        }
        mismatches = {
            key: {"expected": value, "actual": summary[key]}
            for key, value in expected.items()
            if summary[key] != value
        }
        if mismatches:
            raise SystemExit(f"pilot snapshot mismatch: {json.dumps(mismatches, sort_keys=True)}")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
