"""0138: source-bound Shon original metadata indicators, never measurements."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from rhombus.qualification.measurement_identity import _json_bytes
from scripts.science.public_transport_shon_original_audit import (
    MAX_BYTES, OFFICIAL_BYTES, OFFICIAL_GIT_BLOB_SHA1,
    inspect_shon_primary_json, _reject_constant,
)

SCHEMA = "rhombus-shon-original-source-schema-0138-v1"
# Names are controlled labels only; never publish original source keys/values.
INDICATORS = {
    "chemistry": {"formula", "chemicalformula", "compound", "composition", "material"},
    "conductivity": {"conductivity", "ionicconductivity", "sigma", "conductivityscm"},
    "temperature": {"temperature", "temp", "temperaturek", "measurementtemperature"},
    "literature": {"doi", "reference", "references", "paper", "citation"},
    "structure": {"cif", "icsd", "structure", "crystalstructure", "spacegroup"},
    "method": {"method", "experiment", "measurementmethod", "experimentalmethod"},
}


def audit_shon_schema(original: bytes, *, exact_blob_sha1: str = OFFICIAL_GIT_BLOB_SHA1,
                      expected_size: int = OFFICIAL_BYTES) -> dict:
    pinned = inspect_shon_primary_json(
        original, exact_blob_sha1=exact_blob_sha1, expected_size=expected_size)
    rows = json.loads(original.decode("utf-8-sig"), parse_constant=_reject_constant)
    if not isinstance(rows, list):
        raise ValueError("0138 original JSON must have verified ARRAY root")
    presence = Counter()
    shapes = Counter()
    for entry in rows:
        shapes["object" if isinstance(entry, dict) else
               "array" if isinstance(entry, list) else "scalar_or_null"] += 1
        seen = set()
        stack = [entry]
        while stack:
            part = stack.pop()
            if isinstance(part, dict):
                for field, value in part.items():
                    norm = re.sub(r"[^a-z0-9]", "", field.casefold())
                    seen.update(name for name, keys in INDICATORS.items() if norm in keys)
                    if isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(part, list):
                stack.extend(part)
        for name in seen:
            presence[name] += 1
        if len(seen) == len(INDICATORS):
            presence["all_six"] += 1
        if not seen:
            presence["none"] += 1
    return {
        "schema_version": SCHEMA,
        "source_git_blob_sha1": pinned["original_git_blob_sha1_verified"],
        "original_source_sha256": pinned["original_file_sha256"],
        "root_entries_NOT_material_or_measurement_count": len(rows),
        "root_entry_shapes": dict(sorted(shapes.items())),
        "field_name_indicator_presence_NOT_validated_values": {
            name: presence[name] for name in INDICATORS},
        "all_six_indicators_NOT_qualified": presence["all_six"],
        "no_recognized_indicators": presence["none"],
        "confirmed_experimental_Li_measurements": None,
        "confirmed_independent_material_samples": None,
        "newly_scientifically_qualified_materials": 0,
        "exact_MACE_training_frames_authenticated": False,
        "new_external_blind_cohort_qualified": False,
        "source_data_rights_to_republish_verified": False,
        "original_rows_keys_and_values_republished": False,
        "scientific_score_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-json", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args(argv)
    try:
        source = a.original_json.resolve(strict=True)
        output = a.output_dir.resolve()
        if output.exists() or output == source or source in output.parents:
            raise ValueError("source and output must remain separate; output must be new")
        with source.open("rb") as inp:
            report = audit_shon_schema(inp.read(MAX_BYTES + 1))
        output.mkdir(parents=True, exist_ok=False)
        (output / "shon_schema_aggregate.json").write_bytes(_json_bytes(report) + b"\n")
    except (ValueError, OSError, TypeError) as e:
        p.error(str(e))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
