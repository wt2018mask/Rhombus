"""0135 reproducible, conservative PUBLIC diagnostic benchmark and source audit.

Only OBELiX original TRAIN source records become a reproducible published
candidate worklist. The original public TEST is counted but never exported
into developer training/reference rows. All source numeric labels remain
experimentally UNQUALIFIED. External datasets are indexed separately and
only a source checksum/schema audit is allowed when redistribution rights
are unresolved.

No cross-source merge or material sample-count inference is authorized.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile

from rhombus.qualification.measurement_identity import _json_bytes, _parse_json, _read_input
from scripts.science.obelix_adjudication_queue import build_adjudication_queue
from scripts.science.obelix_censor_aware_policy import build_train_label_policy

SCHEMA = "rhombus-public-lithium-experimental-diagnostic-0135-v1"
REGISTRY_SCHEMA = "rhombus-public-lithium-transport-source-registry-0135-v1"
CALTECH_MD5 = "d1fcf7c9a7694c8f466932721b76b168"
CALTECH_FILENAME = "ionic_conductivity_database.csv"
CALTECH_EXPECTED_ROWS = 571
MAX_CSV_BYTES = 350_000
MAX_CSV_ROWS = 3000
MAX_COLUMNS = 100
ALLOWED_SOURCE_IDS = {
    "OBELIX", "MCHAFFIE_2025", "LIVERPOOL_2022", "LASKOWSKI_2023",
    "SHON_MIN_2024", "DDSE_2", "SPSE",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _lines(rows: list[dict]) -> bytes:
    return b"".join(_json_bytes(r) + b"\n" for r in rows)


def validate_registry(registry: dict) -> dict:
    if not isinstance(registry, dict) or set(registry) != {
        "schema_version", "as_of", "benchmark_definition", "sources",
        "no_unverified_sum_as_unique_materials", "no_external_cifs_without_license",
    } or registry["schema_version"] != REGISTRY_SCHEMA:
        raise ValueError("source registry schema invalid")
    if (registry["no_unverified_sum_as_unique_materials"] is not True
            or registry["no_external_cifs_without_license"] is not True):
        raise ValueError("unsafe registry scientific or structure licence permission")
    meta = registry["benchmark_definition"]
    if (not isinstance(meta, dict)
            or meta.get("quantity") != "EXPERIMENTAL_LITHIUM_IONIC_CONDUCTIVITY"
            or meta.get("admitted_scientifically_qualified_materials") != 0
            or meta.get("official_public_test_not_used_for_development") is not True
            or meta.get("source_censoring_must_be_retained") is not True):
        raise ValueError("source registry cannot promote scientific claims")
    sources = registry["sources"]
    if not isinstance(sources, list) or len(sources) != len(ALLOWED_SOURCE_IDS):
        raise ValueError("unexpected source catalogue")
    by_id = {}
    for item in sources:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("invalid source")
        sid = item["id"]
        if sid in by_id or sid not in ALLOWED_SOURCE_IDS:
            raise ValueError("unexpected/duplicated source")
        if not isinstance(item.get("rights"), str) or not item["rights"]:
            raise ValueError("missing licence provenance")
        if not isinstance(item.get("source_url"), str) or not item["source_url"].startswith("https://"):
            raise ValueError("unsafe non-HTTPS upstream reference")
        if type(item.get("published_record_count")) not in (type(None), int):
            raise ValueError("invalid source reported count")
        if item["published_record_count"] is not None and item["published_record_count"] <= 0:
            raise ValueError("nonpositive reported external count")
        if sid != "OBELIX" and item.get("local_reuse") not in (
            "CATALOG_ONLY", "LINKS_AND_DESCRIPTIVE_METADATA_ONLY",
            "METADATA_AUDIT_ONLY_NO_SOURCE_REPUBLICATION",
        ):
            raise ValueError("unauthorized external experimental dataset redistribution")
        by_id[sid] = item
    if set(by_id) != ALLOWED_SOURCE_IDS:
        raise ValueError("source catalogue incomplete")
    if (by_id["OBELIX"].get("phase") != "REAL_SOURCE_VALIDATED"
            or by_id["OBELIX"].get("local_reuse") != "TRAIN_ONLY_PUBLIC_DIAGNOSTIC"
            or by_id["OBELIX"].get("published_record_count") != 599):
        raise ValueError("canonical source licence or partition changed")
    if (by_id["MCHAFFIE_2025"].get("upstream_file_md5") != CALTECH_MD5
            or by_id["MCHAFFIE_2025"].get("published_record_count") != 571
            or by_id["MCHAFFIE_2025"].get("rights") != "REUSE_RIGHTS_NOT_EXPLICIT_ON_RECORD"):
        raise ValueError("external pinned Caltech source changed")
    return by_id


def build_public_benchmark(
    obelix_checkout: Path, evidence_dir: Path, raw_lineage_dir: Path,
    registry: dict, *, require_official: bool = True,
) -> tuple[list[dict], dict]:
    validate_registry(registry)
    train_policy, policy_report = build_train_label_policy(
        obelix_checkout, evidence_dir, raw_lineage_dir,
        require_official=require_official,
    )
    work, _, review_report = build_adjudication_queue(
        evidence_dir, require_official=require_official,
    )
    by_work = {r["source_entry_id"]: r for r in work}
    if len(by_work) != len(work):
        raise ValueError("duplicate source review records")
    if (review_report["official_train_records_in_review"]
            != policy_report["source_train_records"]
            or review_report["official_test_records_reserved"]
            != policy_report["original_test_reserved_aggregate"]):
        raise ValueError("original train/test partition no longer matches source")
    publish = []
    for r in train_policy:
        sid = r["source_entry_id"]
        original = by_work.get(sid)
        if (original is None or original["official_original_split"] != "TRAIN"
                or original["source_record_sha256"] != r["source_record_sha256"]
                or r["official_original_split"] != "TRAIN"
                or r["point_estimate_benchmark_scoring_permitted"] is not False
                or r["scientific_material_qualified"] is not False):
            raise ValueError("public benchmark input altered, leaks TEST or promotes science")
        publish.append({
            "schema_version": SCHEMA,
            "source_dataset": "OBELIX",
            "source_entry_id": sid,
            "original_record_sha256": r["source_record_sha256"],
            "source_original_raw_workbook_sha256": r["source_raw_workbook_sha256"],
            "partition": "DEVELOPMENT_TRAIN_ONLY_PUBLIC",
            "doi_source_tokens": original["original_reference_dois"],
            "cif_source_match_status": original["cif_match_status"],
            "possible_overlap_pair_count": original["possible_pair_count"],
            "material_independence_certified": False,
            "label_policy": r["raw_measurement_policy_kind"],
            "strict_upper_bound_s_per_cm": r["exclusive_upper_bound_s_per_cm"],
            "numeric_source_unverified_s_per_cm": r["source_numeric_metadata_s_per_cm"],
            "physical_quantity_status": r["measurement_quantity_status"],
            "experimental_phase_temperature_authenticated": False,
            "original_paper_table_authenticated": False,
            "exact_model_training_nonexposure_authenticated": False,
            "eligible_for_scientific_scoring": False,
        })
    publish.sort(key=lambda x: x["source_entry_id"])
    if len(publish) != policy_report["source_train_records"]:
        raise ValueError("source train records lost from publicly reproducible benchmark")
    raw = _lines(publish)
    summary = {
        "schema_version": SCHEMA,
        "scope": "PUBLIC_DEVELOPMENT_DIAGNOSTIC_NOT_BLINDED",
        "registry_sha256": _sha(_json_bytes(registry)),
        "public_train_records_sha256": _sha(raw),
        "upstream_original_source_commit": policy_report["source_commit"],
        "upstream_raw_workbook_sha256": policy_report["source_workbook_sha256"],
        "upstream_0134_policy_sha256": policy_report["train_label_policy_jsonl_sha256"],
        "registered_candidate_sources": len(registry["sources"]),
        "real_integrated_source_dataset_count": 1,
        "source_reported_total_rows_NOT_UNIQUE": 599,
        "development_public_train_records": len(publish),
        "development_original_upper_bound_records": sum(
            r["label_policy"] == "UPPER_BOUND_EXCLUSIVE" for r in publish),
        "development_unverified_numeric_records": sum(
            r["label_policy"] == "SOURCE_NUMERIC_UNVERIFIED" for r in publish),
        "public_original_test_records_reserved_aggregate": policy_report[
            "original_test_reserved_aggregate"],
        "original_test_censored_aggregate": policy_report[
            "original_test_censored_aggregate"],
        "source_duplicate_review_pairs": review_report["possible_record_overlap_pairs"],
        "independent_material_count": None,
        "scientifically_qualified_transport_records": 0,
        "new_independent_blind_cohort_materials": 0,
        "scientific_score_authorized": False,
        "public_benchmark_status": "DIAGNOSTIC_CATALOG_ONLY",
        "external_datasets_not_redistributed": True,
    }
    return publish, summary


def inspect_caltech_original_csv(raw: bytes, *, expected_md5: str = CALTECH_MD5,
                                 expected_rows: int = CALTECH_EXPECTED_ROWS) -> dict:
    """Checksum-verify original CSV; output aggregates/headers only, NEVER raw rows."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_CSV_BYTES:
        raise ValueError("Caltech source CSV absent or over input budget")
    md5 = hashlib.md5(raw, usedforsecurity=False).hexdigest()
    if not isinstance(expected_md5, str) or md5 != expected_md5:
        raise ValueError("Caltech original published file checksum mismatch")
    try:
        s = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Caltech source encoding invalid") from exc
    reader = csv.DictReader(io.StringIO(s, newline=""))
    headers = reader.fieldnames
    if (not headers or not 2 <= len(headers) <= MAX_COLUMNS
            or len(set(headers)) != len(headers)
            or any(not isinstance(h, str) or not h.strip() or len(h) > 150
                   for h in headers)):
        raise ValueError("Caltech original schema invalid")
    n = 0
    blank_counts = {k: 0 for k in headers}
    for row in reader:
        n += 1
        if n > MAX_CSV_ROWS or None in row:
            raise ValueError("Caltech row width/count over budget")
        if any(v is None for v in row.values()):
            raise ValueError("Caltech missing CSV cells")
        for k in headers:
            blank_counts[k] += int(not row[k].strip())
    if n != expected_rows:
        raise ValueError("Caltech CSV does not match published 571 rows")
    return {
        "schema_version": "rhombus-caltech-source-byte-audit-0135-v1",
        "dataset_id": "MCHAFFIE_2025",
        "official_published_file_md5_verified": True,
        "official_file_md5": md5,
        "official_file_sha256": _sha(raw),
        "file_size_bytes": len(raw),
        "source_csv_row_count": n,
        "source_csv_header_columns": headers,
        "null_cell_counts_by_source_column": blank_counts,
        "raw_source_republished": False,
        "source_licensing_unresolved": True,
        "source_independent_material_count": None,
        "source_scientific_qualified_material_count": 0,
        "source_integration_status": "PINNED_SOURCE_ACQUIRED_SCHEMA_AUDIT_ONLY",
        "scientific_score_authorized": False,
    }


def _publish_files(output: Path, content: dict[str, bytes]) -> None:
    if output.exists():
        raise ValueError("output destination must not pre-exist")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".public-benchmark-", dir=output.parent))
    try:
        for name, raw in content.items():
            (stage / name).write_bytes(raw)
        if output.exists():
            raise ValueError("output destination changed before final commit")
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build-obelix-public-train")
    p.add_argument("--obelix-checkout", required=True, type=Path)
    p.add_argument("--evidence-dir", required=True, type=Path)
    p.add_argument("--raw-lineage-dir", required=True, type=Path)
    p.add_argument("--registry-json", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    c = sub.add_parser("audit-caltech-file")
    c.add_argument("--input-csv", required=True, type=Path)
    c.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        output = args.output_dir.resolve()
        if args.command == "build-obelix-public-train":
            source, provenance, raw = (
                args.obelix_checkout.resolve(strict=True),
                args.evidence_dir.resolve(strict=True),
                args.raw_lineage_dir.resolve(strict=True))
            if any(i == output or i in output.parents for i in (source, provenance, raw)):
                raise ValueError("cannot write to original source and evidence directory")
            registry_path = args.registry_json.resolve(strict=True)
            if output == registry_path:
                raise ValueError("cannot overwrite source registry")
            registry = _parse_json(_read_input(registry_path))
            records, result = build_public_benchmark(source, provenance, raw, registry)
            _publish_files(output, {
                "public_train_diagnostic.jsonl": _lines(records),
                "summary.json": _json_bytes(result) + b"\n",
            })
        else:
            source_path = args.input_csv.resolve(strict=True)
            if source_path == output or source_path in output.parents:
                raise ValueError("cannot publish original external CSV via diagnostic")
            with source_path.open("rb") as f:
                raw = f.read(MAX_CSV_BYTES + 1)
            result = inspect_caltech_original_csv(raw)
            _publish_files(output, {"source_schema_audit.json": _json_bytes(result) + b"\n"})
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
