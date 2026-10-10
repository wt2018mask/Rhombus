"""Offline bulk OBELiX benchmark intake: preserve experimental measurement scope.

Reads a clean, source-commit-pinned upstream checkout; preserves its OFFICIAL
train/test IDs. Source rows and experimental conductivity are not automatically
qualified benchmarks. Never runs MLIP, MD, Kaggle, or model inference.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import io
import csv
import json
import os
from pathlib import Path
import re

from rudeus.generation.candidate_supply_obelix_adapter import (
    build_candidate_supply_v2_obelix_adapter,
)

SOURCE_COMMIT = "4eaac889809dd489e3bae468c45d5c0e02b9147a"
SCHEMA = "rhombus-bulk-obelix-benchmark-intake-v1"
MAX_CSV_BYTES = 8 * 1024 * 1024
MAX_SPLIT_BYTES = 1024 * 1024
MAX_RECORDS = 50000
MAX_CIF_FILES = 50000
MAX_CIF_BYTES = 16 * 1024 * 1024
CONDUCTIVITY_COLUMN = "Ionic conductivity (S cm-1)"
REQUIRED_COLUMNS = ("ID", "Composition", CONDUCTIVITY_COLUMN, "DOI", "CIF")
_ALLOWED_CIF = frozenset(("Match", "Close Match", "No Match"))
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _read_bounded(path: Path, limit: int) -> bytes:
    if path.is_symlink():
        raise ValueError("source data symlinks are unsupported")
    with path.open("rb") as source:
        blob = source.read(limit + 1)
    if len(blob) > limit:
        raise ValueError("source data exceeds intake byte budget")
    return blob


def _official_split(blob: bytes, *, name: str) -> list[str]:
    try:
        reader = csv.DictReader(io.StringIO(blob.decode("utf-8-sig"), newline=""))
        if reader.fieldnames != ["ID"]:
            raise ValueError("official " + name + " split must contain only ID")
        ids = []
        for row in reader:
            if None in row or not isinstance(row["ID"], str):
                raise ValueError("malformed official split row")
            value = row["ID"]
            if not value or value.strip() != value:
                raise ValueError("invalid split identity")
            ids.append(value)
        if len(ids) != len(set(ids)) or not ids:
            raise ValueError("duplicate/empty official " + name + " split")
        return ids
    except UnicodeDecodeError as exc:
        raise ValueError("official split must be UTF-8") from exc


def _conductivity(raw: str) -> tuple[str, str | None]:
    if not isinstance(raw, str):
        raise ValueError("missing experimental conductivity")
    value = raw.strip()
    is_censored = value.startswith("<")
    normalized = value[1:].strip() if is_censored else value
    try:
        parsed = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("unparseable experimental conductivity") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("experimental conductivity must be positive and finite")
    if not is_censored and (value.startswith(">") or value.startswith("=")):
        raise ValueError("unsupported conductivity measurement qualifier")
    return ("UPPER_BOUND" if is_censored else "PROCESSED_REPORTED_POINT"), value


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def build_obelix_benchmark_intake(
    checkout: Path, *, expected_commit: str = SOURCE_COMMIT,
) -> tuple[list[dict], dict]:
    """Build a source-pinned, split-preserving catalog, not a scientific PASS."""
    if not isinstance(expected_commit, str) or _SHA.fullmatch(expected_commit) is None:
        raise ValueError("expected source commit must be an exact lowercase Git SHA")
    root = Path(checkout).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("upstream checkout is not a directory")
    csv_path = root / "data" / "processed.csv"
    train_path = root / "data" / "train_idx.csv"
    test_path = root / "data" / "test_idx.csv"
    cif_root = root / "data" / "randomized_cifs"
    for path, cap in ((csv_path, MAX_CSV_BYTES), (train_path, MAX_SPLIT_BYTES),
                      (test_path, MAX_SPLIT_BYTES)):
        _read_bounded(path, cap)
    cif_paths = list(cif_root.rglob("*.cif"))
    if len(cif_paths) > MAX_CIF_FILES:
        raise ValueError("too many source CIF files")
    for path in cif_paths:
        if path.is_symlink() or path.stat().st_size > MAX_CIF_BYTES:
            raise ValueError("unsafe or over-budget CIF source")
    config_fields = {
        "source_name": "OBELiX",
        "source_namespace": "obelix",
        "source_schema_version": "obelix-processed-csv-as-reported-v1",
        "source_artifact_id": "NRC-Mila/OBELiX@" + expected_commit,
        "processed_csv_relative_path": "data/processed.csv",
        "cif_dir_relative_path": "data/randomized_cifs",
        "id_column": "ID",
        "required_selection_columns": list(REQUIRED_COLUMNS),
    }
    adapter_config = {
        **config_fields,
        "adapter_config_identity": {
            "schema_version": "rhombus-obelix-benchmark-intake-config-v1",
            "content_sha256": hashlib.sha256(_json_bytes(config_fields)).hexdigest(),
        },
    }

    def never_parse_cif(_path):
        raise AssertionError("intake must never simulate or parse source CIF")

    source = build_candidate_supply_v2_obelix_adapter(
        root, adapter_config=adapter_config, parser=never_parse_cif,
    )
    snapshot = source.source_snapshot
    if snapshot["source_repository_commit"] != expected_commit:
        raise ValueError("source checkout does not match pinned exact commit")
    train_blob = _read_bounded(train_path, MAX_SPLIT_BYTES)
    test_blob = _read_bounded(test_path, MAX_SPLIT_BYTES)
    train = set(_official_split(train_blob, name="train"))
    test = set(_official_split(test_blob, name="test"))
    ids = {row["source_id"] for row in source.source_rows}
    if (train & test) or train | test != ids:
        raise ValueError("official OBELiX split overlaps or does not cover every record")
    if len(ids) > MAX_RECORDS:
        raise ValueError("source entry count exceeds budget")
    available = {
        item["source_id"]: item for item in source.cif_inventory
        if item["source_row_present"]
    }
    if source.adapter_provenance["orphan_cif_source_ids"]:
        raise ValueError("CIF directory contains unreferenced source IDs")

    entries = []
    doi_by_split: dict[str, set[str]] = defaultdict(set)
    formulas_by_split: dict[str, set[str]] = defaultdict(set)
    counts = Counter()
    raw_compositions = Counter()
    for row in source.source_rows:
        source_id = row["source_id"]
        split = "TRAIN" if source_id in train else "TEST"
        reported_composition = row["Composition"].strip()
        if not reported_composition:
            raise ValueError("empty reported composition")
        measurement_kind, measured_value = _conductivity(row[CONDUCTIVITY_COLUMN])
        declared_cif = row["CIF"].strip()
        if declared_cif not in _ALLOWED_CIF:
            raise ValueError("unsupported source CIF match category")
        cif = available[source_id]
        has_cif = cif["cif_present"]
        if has_cif != (declared_cif != "No Match"):
            raise ValueError("source CIF match category differs from actual inventory")
        dois = [item.strip().lower() for item in row["DOI"].split("|") if item.strip()]
        if len(dois) != len(set(dois)):
            raise ValueError("duplicate DOI for source row")
        for doi in dois:
            if not doi.startswith("10.") or any(c.isspace() for c in doi):
                raise ValueError("malformed source DOI")
        doi_by_split[split].update(dois)
        formulas_by_split[split].add(reported_composition)
        raw_compositions[reported_composition] += 1
        counts[split] += 1
        counts[measurement_kind] += 1
        counts["CIF_" + declared_cif.replace(" ", "_").upper()] += 1
        if not dois:
            counts["DOI_MISSING"] += 1
        entries.append({
            "schema_version": SCHEMA,
            "source_dataset": "OBELiX",
            "source_entry_id": source_id,
            "source_snapshot_commit": expected_commit,
            "official_split": split,
            "reported_composition": reported_composition,
            "reported_ionic_conductivity_text": measured_value,
            "reported_ionic_conductivity_unit": "S/cm",
            "measurement_kind": measurement_kind,
            "reported_temperature_scope": "ROOM_TEMPERATURE_EXACT_K_UNSPECIFIED",
            "reference_dois": dois,
            "source_cif_match_status": declared_cif,
            "cif_relative_path": cif["relative_path"],
            "cif_content_sha256": cif["content_sha256"],
            "source_structure_has_verified_phase_identity": False,
            "source_material_independence_verified": False,
            "source_training_exposure_verified": False,
            "qualified_transport_truth": False,
            "independently_blinded": False,
        })
    entries.sort(key=lambda x: x["source_entry_id"])
    records_blob = b"".join(_json_bytes(row) + b"\n" for row in entries)
    summary = {
        "schema_version": SCHEMA,
        "source_kind": "PINNED_OFFICIAL_OBELIX_PROCESSED_CSV",
        "source_commit": expected_commit,
        "source_tree": snapshot["source_repository_tree"],
        "processed_csv_sha256": snapshot["source_data_identity"]["processed_csv_sha256"],
        "cif_inventory_sha256": snapshot["source_data_identity"]["cif_inventory_sha256"],
        "train_idx_sha256": hashlib.sha256(train_blob).hexdigest(),
        "test_idx_sha256": hashlib.sha256(test_blob).hexdigest(),
        "records_jsonl_sha256": hashlib.sha256(records_blob).hexdigest(),
        "record_count": len(entries),
        "official_train_count": counts["TRAIN"],
        "official_test_count": counts["TEST"],
        "available_cif_count": sum(item["cif_relative_path"] is not None for item in entries),
        "cif_category_counts": {name: counts["CIF_" + name.replace(" ", "_").upper()]
                                for name in sorted(_ALLOWED_CIF)},
        "reported_measurement_kind_counts": {
            name: counts[name] for name in ("PROCESSED_REPORTED_POINT", "UPPER_BOUND")
        },
        "missing_doi_count": counts["DOI_MISSING"],
        "distinct_reported_composition_strings": len(raw_compositions),
        "repeated_reported_composition_strings": sum(n > 1 for n in raw_compositions.values()),
        "official_train_test_direct_composition_overlap": len(
            formulas_by_split["TRAIN"] & formulas_by_split["TEST"]
        ),
        "official_train_test_doi_overlap": len(
            doi_by_split["TRAIN"] & doi_by_split["TEST"]
        ),
        "independent_material_count": None,
        "qualified_benchmark_material_count": 0,
        "external_blind_material_count": 0,
        "operational_status": "SUCCEEDED",
        "scientific_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "limitations": [
            "SOURCE_PROCESSED_VALUES_NOT_INDEPENDENT_EXPERIMENTAL_REASSESSMENT",
            "PROCESSED_CSV_MAY_HAVE_FLATTENED_ORIGINAL_CENSORING",
            "RECORDED_ROOM_TEMPERATURE_HAS_NO_PER_ROW_EXACT_K",
            "CIF_MATCH_OR_CLOSE_MATCH_DOES_NOT_AUTHENTICATE_PHASE",
            "IDENTICAL_COMPOSITION_STRING_NOT_AN_INDEPENDENT_MATERIAL_IDENTITY",
            "CROSS_DATASET_AND_MODEL_TRAINING_EXPOSURE_UNVERIFIED",
            "OFFICIAL_TRAIN_TEST_SPLIT_PRESERVED_NOT_REPARTITIONED",
            "PUBLIC_OBELIX_TEST_IS_NOT_NEW_SECRET_BLINDED_QUALIFICATION",
        ],
    }
    return entries, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obelix-checkout", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-commit", default=SOURCE_COMMIT)
    args = parser.parse_args(argv)
    records, summary = build_obelix_benchmark_intake(
        args.obelix_checkout, expected_commit=args.expected_commit,
    )
    out = args.output_dir.resolve()
    checkout = args.obelix_checkout.resolve(strict=True)
    if out == checkout or checkout in out.parents:
        parser.error("output directory must not modify clean source checkout")
    if out.exists() and any(out.iterdir()):
        parser.error("output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)
    data = b"".join(_json_bytes(row) + b"\n" for row in records)
    (out / "records.jsonl").write_bytes(data)
    (out / "summary.json").write_bytes(_json_bytes(summary) + b"\n")
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
