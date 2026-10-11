"""0136 source-bound Caltech scientific eligibility funnel (aggregate only).

Use the pinned original third-party CSV IN MEMORY, never serialize its
source rows, DOI strings, compound formulas, ICSD IDs, raw conductivity
numbers, or licensed structures. Source quality != independent truth.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path

from rhombus.qualification.measurement_identity import _json_bytes, _parse_json, _read_input, _records_from_jsonl
from scripts.science.public_transport_benchmark import inspect_caltech_original_csv, SCHEMA as BENCHMARK_SCHEMA
from scripts.science.public_transport_overlap import inspect_caltech_vs_obelix_train, _doi

SCHEMA = "rhombus-caltech-source-eligibility-funnel-0136-v1"
EXPECTED_HEADERS = (
    "compound",
    "icsd_collectioncode",
    "conductivity_doi",
    "conductivity_siemens_per_cm",
    "lowest_extrapolation_temperature_K",
)
CALTECH_OFFICIAL_SHA256 = "868c4bd793d7c31b929787dc69478691b27ced0440d19269075143c98ecd1545"
CALTECH_OFFICIAL_MD5 = "d1fcf7c9a7694c8f466932721b76b168"
MAX_CELL_CHARS = 1000
MAX_CONDUCTIVITY = Decimal("1e12")
MAX_TEMPERATURE_K = Decimal("10000")


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _positive_number(text: str, maximum: Decimal) -> bool:
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_CELL_CHARS:
        return False
    try:
        number = Decimal(text.strip())
    except InvalidOperation:
        return False
    return number.is_finite() and 0 < number <= maximum


def _normalize_formula_key(formula: str) -> str:
    # String key is a mere input collision signal: no chemistry parsing,
    # stoichiometric reduction, charge, vacancy or structural equivalence.
    if not isinstance(formula, str) or len(formula) > MAX_CELL_CHARS:
        raise ValueError("unbounded source formula field")
    return "".join(formula.split()).casefold()


def _normalize_icsd_key(code: str) -> str:
    # Source ICSD ID does NOT convey licence to the actual CIF structure.
    if not isinstance(code, str) or len(code) > MAX_CELL_CHARS:
        raise ValueError("unbounded source structure-code field")
    return code.strip().casefold()


def build_external_quality_funnel(
    original_caltech_csv: bytes,
    original_public_train_rows: list[dict],
    original_public_train_summary: dict,
    *,
    require_official: bool = True,
    expected_source_md5: str = CALTECH_OFFICIAL_MD5,
    expected_source_rows: int = 571,
) -> dict:
    """Build safe aggregate from two *verified* public sources.

    No per-row external outputs, train/test leakage, scoring authorization,
    exposure claims, chemistry-equivalence inference or fabricated samples.
    """
    audit = inspect_caltech_original_csv(
        original_caltech_csv,
        expected_md5=expected_source_md5,
        expected_rows=expected_source_rows,
    )
    if require_official and audit["official_file_sha256"] != CALTECH_OFFICIAL_SHA256:
        raise ValueError("upstream exact official source SHA256 changed")
    if tuple(audit["source_csv_header_columns"]) != EXPECTED_HEADERS:
        raise ValueError("Caltech five-column source contract changed")
    overlap = inspect_caltech_vs_obelix_train(
        original_caltech_csv,
        original_public_train_rows,
        original_public_train_summary,
        expected_caltech_md5=expected_source_md5,
        expected_caltech_rows=expected_source_rows,
    )
    if (original_public_train_summary.get("schema_version") != BENCHMARK_SCHEMA
            or original_public_train_summary["scientific_score_authorized"] is not False):
        raise ValueError("public source label promotion detected")
    obelix_train_dois: set[str] = set()
    for row in original_public_train_rows:
        for token in row["doi_source_tokens"]:
            doi = _doi(token)
            if doi.startswith("10."):
                obelix_train_dois.add(doi)
    counts: Counter[str] = Counter()
    raw_tuple_keys = set()
    distinct_formula = set()
    distinct_formula_icsd = set()
    distinct_formula_icsd_doi = set()
    doi_ids = set()
    reader = csv.DictReader(io.StringIO(original_caltech_csv.decode("utf-8-sig"), newline=""))
    for row in reader:
        if not isinstance(row, dict) or set(row) != set(EXPECTED_HEADERS):
            raise ValueError("Caltech original row missing required fields")
        if not all(isinstance(row[k], str) and len(row[k]) <= MAX_CELL_CHARS
                   for k in EXPECTED_HEADERS):
            raise ValueError("overlong or invalid Caltech source metadata")
        counts["original_records"] += 1
        formula = _normalize_formula_key(row["compound"])
        icsd = _normalize_icsd_key(row["icsd_collectioncode"])
        raw_doi = _doi(row["conductivity_doi"])
        if len(raw_doi) > MAX_CELL_CHARS:
            raise ValueError("overlong original source DOI")
        doi = raw_doi if raw_doi.startswith("10.") else ""
        sigma_ok = _positive_number(row["conductivity_siemens_per_cm"], MAX_CONDUCTIVITY)
        temperature_ok = _positive_number(row["lowest_extrapolation_temperature_K"], MAX_TEMPERATURE_K)
        in_train_doi = bool(doi and doi in obelix_train_dois)
        flags = (
            ("missing_formula" if not formula else ""),
            ("missing_icsd_identifier" if not icsd else ""),
            ("missing_usable_doi" if not doi else ""),
            ("unparseable_or_nonpositive_conductivity" if not sigma_ok else ""),
            ("extrapolation_temperature_missing_or_nonpositive" if not temperature_ok else ""),
            ("doi_overlap_with_public_obelix_train" if in_train_doi else ""),
        )
        for flag in flags:
            if flag:
                counts[flag] += 1
        if formula:
            distinct_formula.add(formula)
        if formula and icsd:
            distinct_formula_icsd.add((formula, icsd))
        if formula and icsd and doi:
            distinct_formula_icsd_doi.add((formula, icsd, doi))
        if doi:
            doi_ids.add(doi)
        if sigma_ok and formula and doi:
            counts["minimum_value_formula_doi_metadata"] += 1
        if sigma_ok and temperature_ok and formula and icsd and doi:
            counts["complete_five_field_metadata_review_candidates"] += 1
            if not in_train_doi:
                counts["complete_five_fields_no_exact_obelix_train_doi_signal"] += 1
        if sigma_ok:
            counts["positive_finite_original_source_conductivity"] += 1
        if temperature_ok:
            counts["positive_finite_lowest_extrapolation_K"] += 1
        if in_train_doi:
            counts["source_record_with_DOI_overlap"] += 1
        else:
            counts["source_record_without_exact_DOI_overlap"] += 1
        # Source-proxy collision detector, NOT a material identity judgement.
        # This does not separate different T samples or repeated original sources.
        key = (formula, icsd, doi)
        if key in raw_tuple_keys:
            counts["repeated_exact_formula_icsd_doi_proxy_rows"] += 1
        else:
            raw_tuple_keys.add(key)
    if (counts["original_records"] != expected_source_rows
            or len(doi_ids) != overlap["source_caltech_distinct_DOI_tokens"]
            or len(distinct_formula) != overlap["source_caltech_distinct_raw_formula_strings"]
            or counts["positive_finite_lowest_extrapolation_K"] != overlap[
                "number_of_source_temperature_metadata_numeric"]
            or counts["source_record_with_DOI_overlap"] != overlap[
                "caltech_rows_with_exact_obelix_train_DOI_signal"]
            or counts["source_record_without_exact_DOI_overlap"] != overlap[
                "caltech_rows_without_exact_obelix_train_DOI_signal"]):
        raise ValueError("0136 source cross-audit disagrees with 0135 independent parser")
    return {
        "schema_version": SCHEMA,
        "source_dataset": "MCHAFFIE_2025",
        "source_original_file_sha256": audit["official_file_sha256"],
        "source_original_published_md5": audit["official_file_md5"],
        "source_original_file_size_bytes": audit["file_size_bytes"],
        "source_original_schema": list(EXPECTED_HEADERS),
        "reference_original_obelix_train_sha256": overlap["source_obelix_public_train_sha256"],
        "source_original_records": counts["original_records"],
        "source_reported_formula_string_count": len(distinct_formula),
        "source_reported_DOI_token_count": len(doi_ids),
        "source_formula_icsd_proxy_key_count": len(distinct_formula_icsd),
        "source_formula_icsd_doi_proxy_key_count": len(distinct_formula_icsd_doi),
        "repeated_exact_formula_icsd_doi_proxy_rows": counts[
            "repeated_exact_formula_icsd_doi_proxy_rows"],
        "data_quality_counters": {
            "missing_formula": counts["missing_formula"],
            "missing_icsd_identifier": counts["missing_icsd_identifier"],
            "missing_usable_doi": counts["missing_usable_doi"],
            "unparseable_or_nonpositive_conductivity": counts[
                "unparseable_or_nonpositive_conductivity"],
            "extrapolation_temperature_missing_or_nonpositive": counts[
                "extrapolation_temperature_missing_or_nonpositive"],
            "doi_overlap_with_public_obelix_train": counts[
                "doi_overlap_with_public_obelix_train"],
            "source_record_without_exact_DOI_overlap": counts[
                "source_record_without_exact_DOI_overlap"],
            "positive_finite_original_source_conductivity": counts[
                "positive_finite_original_source_conductivity"],
            "positive_finite_lowest_extrapolation_K": counts[
                "positive_finite_lowest_extrapolation_K"],
            "minimum_value_formula_doi_metadata": counts[
                "minimum_value_formula_doi_metadata"],
            "complete_five_field_metadata_review_candidates": counts[
                "complete_five_field_metadata_review_candidates"],
            "complete_five_fields_no_exact_obelix_train_doi_signal": counts[
                "complete_five_fields_no_exact_obelix_train_doi_signal"],
        },
        "public_review_priority_policy": "ORIGINAL_METADATA_ONLY_NO_FINAL_EXPERIMENTAL_QUALIFICATION",
        "source_reuse_rights_verified": False,
        "external_original_rows_redistributed": False,
        "public_test_identity_and_truth_exposed": False,
        "independent_material_identity_count": None,
        "certified_exact_measurement_temperature_count": 0,
        "certified_sample_bound_crystal_structure_count": 0,
        "scientifically_qualified_independent_material_count": None,
        "new_scientifically_qualified_materials": 0,
        "new_external_blind_materials": 0,
        "scientific_score_authorized": False,
        "scientific_verdict": "INDETERMINATE",
        "limitations": [
            "SOURCE_METADATA_COMPLETENESS_NOT_SCIENTIFIC_TRUTH",
            "LOWEST_EXTRAPOLATION_T_K_NOT_EXACT_MEASUREMENT_T_K",
            "ICSD_IDENTIFIER_NOT_AUTHENTICATED_CIF_OR_REDISTRIBUTION_LICENSE",
            "FORMULA_ICSD_DOI_MATCH_NOT_INDEPENDENT_EXPERIMENTAL_SAMPLE",
            "EXACT_DOI_NONMATCH_NOT_UNSEEN_MATERIAL_OR_GENERALIZATION_PROOF",
            "ORIGINAL_RAW_RECORDS_AND_DOIS_NOT_PUBLISHED",
            "OBELIX_ORIGINAL_PUBLIC_TEST_NOT_USED_FOR_DEVELOPMENT",
            "MACE_EXACT_TRAINING_EXPOSURE_AND_EXTERNAL_SEALED_COHORT_UNATTESTED",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caltech-csv", required=True, type=Path)
    parser.add_argument("--obelix-benchmark-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        original_path = args.caltech_csv.resolve(strict=True)
        bench_path = args.obelix_benchmark_dir.resolve(strict=True)
        out = args.output_dir.resolve()
        if (out.exists() or out == original_path or out == bench_path
                or original_path in out.parents or bench_path in out.parents):
            raise ValueError("source audit output cannot replace input or source")
        with original_path.open("rb") as stream:
            original = stream.read(350001)
        rows = _records_from_jsonl(_read_input(bench_path / "public_train_diagnostic.jsonl"))
        summary = _parse_json(_read_input(bench_path / "summary.json"))
        report = build_external_quality_funnel(original, rows, summary)
        out.mkdir(parents=True, exist_ok=False)
        (out / "caltech_source_quality_aggregate.json").write_bytes(
            _json_bytes(report) + b"\n"
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
