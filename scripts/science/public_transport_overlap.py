"""0135 cross-source DOI *candidate* intersection, not sample deduplication.

Runs inside GitHub Actions after the original published Caltech 571-row CSV is
fetched and checksum-verified. Emits aggregate-only diagnostics and the
source SHA. No external raw record, DOI, formula, ICSD or conductivity value
is redistributed. Exact DOI equality is only a review signal.
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

from rhombus.qualification.measurement_identity import (
    _json_bytes, _parse_json, _read_input, _records_from_jsonl,
)
from scripts.science.public_transport_benchmark import (
    SCHEMA as PUBLIC_SCHEMA, inspect_caltech_original_csv,
)

SCHEMA = "rhombus-caltech-obelix-cross-source-doi-review-0135-v1"
_ORIGINAL_COLUMNS = (
    "compound", "icsd_collectioncode", "conductivity_doi",
    "conductivity_siemens_per_cm", "lowest_extrapolation_temperature_K",
)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _doi(value: str) -> str:
    """Conservative DOI comparison (not a trusted bibliographic resolver)."""
    if not isinstance(value, str):
        raise ValueError("invalid DOI source cell")
    d = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.strip()


def inspect_caltech_vs_obelix_train(
    caltech_source_csv: bytes,
    benchmark_rows: list[dict],
    benchmark_summary: dict,
    *,
    expected_caltech_md5: str = "d1fcf7c9a7694c8f466932721b76b168",
    expected_caltech_rows: int = 571,
) -> dict:
    external = inspect_caltech_original_csv(
        caltech_source_csv, expected_md5=expected_caltech_md5,
        expected_rows=expected_caltech_rows,
    )
    if tuple(external["source_csv_header_columns"]) != _ORIGINAL_COLUMNS:
        raise ValueError("unexpected original Caltech DOI/temperature/quantity field positions")
    if (not isinstance(benchmark_summary, dict)
            or benchmark_summary.get("schema_version") != PUBLIC_SCHEMA
            or benchmark_summary.get("scientific_score_authorized") is not False
            or benchmark_summary.get("independent_material_count") is not None
            or benchmark_summary.get("development_public_train_records") != len(benchmark_rows)
            or benchmark_summary.get("public_train_records_sha256") != _sha(
                b"".join(_json_bytes(x) + b"\n" for x in benchmark_rows))):
        raise ValueError("public original TRAIN benchmark content/hash not verified")
    original_dois = set()
    seen_ids = set()
    for r in benchmark_rows:
        if (r.get("schema_version") != PUBLIC_SCHEMA
                or r.get("partition") != "DEVELOPMENT_TRAIN_ONLY_PUBLIC"
                or r.get("source_dataset") != "OBELIX"
                or r.get("eligible_for_scientific_scoring") is not False):
            raise ValueError("public test contamination or unapproved scientific claim")
        rid = r.get("source_entry_id")
        if not isinstance(rid, str) or rid in seen_ids:
            raise ValueError("duplicate/invalid public TRAIN ID")
        seen_ids.add(rid)
        dois = r.get("doi_source_tokens")
        if not isinstance(dois, list):
            raise ValueError("nonlist source DOI evidence")
        for d in dois:
            if not isinstance(d, str):
                raise ValueError("nonstr original source DOI")
            if _doi(d).startswith("10."):
                original_dois.add(_doi(d))
    reader = csv.DictReader(io.StringIO(caltech_source_csv.decode("utf-8-sig"), newline=""))
    counts = Counter()
    external_dois = set()
    material_strings = set()
    temperatures = []
    for item in reader:
        counts["rows"] += 1
        canonical_doi = _doi(item["conductivity_doi"])
        if not canonical_doi:
            counts["without_usable_doi"] += 1
        else:
            external_dois.add(canonical_doi)
        if canonical_doi in original_dois:
            counts["external_rows_with_exact_train_DOI_signal"] += 1
        else:
            counts["external_rows_without_exact_train_DOI_signal"] += 1
        formula = "".join(item["compound"].split()).lower()
        if formula:
            material_strings.add(formula)
        original_T = item["lowest_extrapolation_temperature_K"].strip()
        try:
            val = Decimal(original_T)
        except InvalidOperation:
            counts["lowest_extrapolation_temperature_unparsed"] += 1
        else:
            if val.is_finite() and val > 0:
                temperatures.append(val)
            else:
                counts["lowest_extrapolation_temperature_unparsed"] += 1
    if counts["rows"] != external["source_csv_row_count"]:
        raise ValueError("Caltech reparse lost experimental source rows")
    report = {
        "schema_version": SCHEMA,
        "source_caltech_sha256": external["official_file_sha256"],
        "source_caltech_published_md5": external["official_file_md5"],
        "source_obelix_public_train_sha256": benchmark_summary[
            "public_train_records_sha256"],
        "source_obelix_original_train_doi_tokens": len(original_dois),
        "source_obelix_original_train_records": len(benchmark_rows),
        "source_caltech_original_rows": counts["rows"],
        "source_caltech_distinct_DOI_tokens": len(external_dois),
        "source_caltech_distinct_raw_formula_strings": len(material_strings),
        "caltech_rows_with_exact_obelix_train_DOI_signal": counts[
            "external_rows_with_exact_train_DOI_signal"],
        "caltech_rows_without_exact_obelix_train_DOI_signal": counts[
            "external_rows_without_exact_train_DOI_signal"],
        "number_of_exact_distinct_DOI_tokens_shared": len(
            external_dois & original_dois),
        "number_of_source_temperature_metadata_numeric": len(temperatures),
        "number_of_source_temperature_metadata_unparsed": counts[
            "lowest_extrapolation_temperature_unparsed"],
        "temperature_metadata_type": "LOWEST_EXTRAPOLATION_TEMPERATURE_NOT_EXACT_MEASUREMENT_T",
        "inferred_independent_new_materials": None,
        "inferred_new_authentic_solid_structures": None,
        "scientifically_qualified_materials_added": 0,
        "source_raw_records_redistributed": False,
        "source_DOI_tokens_disclosed": False,
        "source_licensing_unresolved": True,
        "scientific_score_authorized": False,
        "limitations": [
            "EXACT_DOI_MATCH_IS_ONLY_OVERLAP_REVIEW_SIGNAL",
            "DOI_NONMATCH_DOES_NOT_PROVE_MATERIAL_INDEPENDENCE",
            "CALTECH_SOURCE_ROWS_INCLUDE_POTENTIALLY_DERIVED_SAME_LITERATURE",
            "NO_TEST_OBELIX_SOURCE_ROWS_USED_FOR_DEVELOPER_OVERLAP",
            "NO_ICSD_CIF_OR_CALTECH_SOURCE_VALUES_REPUBLISHED",
            "ORIGINAL_TEMPERATURE_IS_LOWEST_EXTRAPOLATION_NOT_EXACT_MEASUREMENT",
            "NO_EXTERNAL_REUSE_RIGHTS_ADJUDICATED",
        ],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caltech-csv", required=True, type=Path)
    parser.add_argument("--obelix-benchmark-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        src = args.caltech_csv.resolve(strict=True)
        old = args.obelix_benchmark_dir.resolve(strict=True)
        out = args.output_dir.resolve()
        if out.exists() or out == src or out == old or src in out.parents or old in out.parents:
            raise ValueError("cross-source diagnostic cannot overwrite original data")
        with src.open("rb") as f:
            blob = f.read(350001)
        rows = _records_from_jsonl(_read_input(old / "public_train_diagnostic.jsonl"))
        summary = _parse_json(_read_input(old / "summary.json"))
        report = inspect_caltech_vs_obelix_train(blob, rows, summary)
        out.mkdir(parents=True)
        (out / "cross_source_doi_signal_summary.json").write_bytes(
            _json_bytes(report) + b"\n"
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
