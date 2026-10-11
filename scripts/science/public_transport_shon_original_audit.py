"""0137: acquire and audit an actual third-party primary data source, without redistribution.

Shon/Min's primary text-mining repository exports a 7MB JSON original.
Availability, original Git byte identity, JSON validity and source layout are
different from (and are not evidence for) independent Li-solid conductivity
measurement truth. Original raw records and source labels must NEVER be
emitted in a public audit artifact.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from rhombus.qualification.measurement_identity import _json_bytes

SCHEMA = "rhombus-shon-min-original-source-byte-audit-0137-v1"
SOURCE_ID = "SHON_MIN_2024"
OFFICIAL_SOURCE_COMMIT = "bec7ffb07b3dde33191eba6aceda1fbfd3b03ea3"
OFFICIAL_GIT_BLOB_SHA1 = "b0e8a20c8806aec337e3547fbd0101094cd4f624"
OFFICIAL_BYTES = 7063926
MAX_BYTES = 8000000
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 200000
MAX_LIST_DICT_ENTRIES = 200000
MAX_STRING_CHARS = 1000000


def _git_blob_sha(data: bytes) -> str:
    # git hash-object byte identity, not a checksum of an inferred JSON export
    prefix = b"blob " + str(len(data)).encode("ascii") + b"\x00"
    return hashlib.sha1(prefix + data, usedforsecurity=False).hexdigest()


def _reject_constant(token: str):
    raise ValueError("non-JSON numeric constant prohibited")


def inspect_shon_primary_json(
    original: bytes,
    *,
    exact_blob_sha1: str = OFFICIAL_GIT_BLOB_SHA1,
    expected_size: int = OFFICIAL_BYTES,
) -> dict:
    if not isinstance(original, bytes) or not 1 <= len(original) <= MAX_BYTES:
        raise ValueError("Shon source original must be bounded bytes")
    if len(original) != expected_size:
        raise ValueError("original Shon source byte size drift")
    blob_sha = _git_blob_sha(original)
    if blob_sha != exact_blob_sha1:
        raise ValueError("original Shon Git blob SHA mismatch")
    try:
        data = json.loads(original.decode("utf-8-sig"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Shon original JSON malformed") from exc
    if not isinstance(data, (dict, list)):
        raise ValueError("Shon original JSON top-level must be object or list")
    root_type = "OBJECT" if isinstance(data, dict) else "ARRAY"
    root_entries = len(data)
    if not 1 <= root_entries <= MAX_LIST_DICT_ENTRIES:
        raise ValueError("unexpected Shon top-level data size")
    stack = [(data, 0)]
    types = Counter()
    count = 0
    max_depth = 0
    while stack:
        value, depth = stack.pop()
        count += 1
        max_depth = max(depth, max_depth)
        if count > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
            raise ValueError("Shon nested JSON resource budget exceeded")
        if isinstance(value, dict):
            types["objects"] += 1
            if len(value) > MAX_LIST_DICT_ENTRIES:
                raise ValueError("too many Shon original JSON object members")
            for k, v in value.items():
                if not isinstance(k, str) or len(k) > MAX_STRING_CHARS:
                    raise ValueError("unsafe or oversized original JSON key")
                stack.append((v, depth + 1))
        elif isinstance(value, list):
            types["arrays"] += 1
            if len(value) > MAX_LIST_DICT_ENTRIES:
                raise ValueError("too many Shon original JSON array elements")
            stack.extend((v, depth + 1) for v in value)
        elif isinstance(value, str):
            if len(value) > MAX_STRING_CHARS:
                raise ValueError("too long original JSON value")
            types["strings"] += 1
        elif isinstance(value, bool):
            types["booleans"] += 1
        elif value is None:
            types["nulls"] += 1
        elif isinstance(value, (int, float)):
            types["numbers"] += 1
        else:
            raise ValueError("unexpected JSON value type")
    return {
        "schema_version": SCHEMA,
        "source_id": SOURCE_ID,
        "upstream_repository": "shonyeajin/Ionical_conductivity_database",
        "upstream_git_commit": OFFICIAL_SOURCE_COMMIT,
        "upstream_file": "database/IonicalConductivityDatabase.json",
        "original_git_blob_sha1_verified": blob_sha,
        "original_file_sha256": hashlib.sha256(original).hexdigest(),
        "original_file_size_bytes": len(original),
        "original_json_top_level_type": root_type,
        "original_json_top_level_entry_count_NOT_MEASUREMENT_COUNT": root_entries,
        "original_json_total_value_nodes": count,
        "original_json_max_depth": max_depth,
        "original_json_type_counts": {k: types[k] for k in (
            "objects", "arrays", "strings", "numbers", "booleans", "nulls")},
        "original_published_literature_claim_4032_measurements_unverified_against_file": True,
        "confirmed_experimental_Li_solid_state_measurements": None,
        "actual_measurement_temperature_verified_count": 0,
        "identical_to_obelix_sample_overlap_count": None,
        "actual_structure_sample_identity_verified_count": 0,
        "data_license_permission_to_republish_verified": False,
        "original_source_rows_republished": False,
        "original_source_keys_values_republished": False,
        "newly_qualified_independent_materials": 0,
        "official_scientific_benchmark_scoring_authorized": False,
        "next_validation": "Confirm stable source record-level schema and Li-only / measured-vs-extracted distinctions before deriving rights-gated cohort aggregates.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-json", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        inp = args.original_json.resolve(strict=True)
        out = args.output_dir.resolve()
        if out.exists() or out == inp or inp in out.parents:
            raise ValueError("audit output must not replace upstream original file")
        with inp.open("rb") as src:
            raw = src.read(MAX_BYTES + 1)
        report = inspect_shon_primary_json(raw)
        out.mkdir(parents=True, exist_ok=False)
        (out / "shon_original_source_audit.json").write_bytes(_json_bytes(report) + b"\n")
    except (ValueError, OSError, TypeError) as exc:
        p.error(str(exc))
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
