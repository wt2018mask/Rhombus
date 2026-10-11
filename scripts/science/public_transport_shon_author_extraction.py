"""0139: original-author Shon extraction triage; never benchmark admission.

This is an aggregate census of text-mined source-export properties. A JSON row
is not a distinct physical sample, and an extracted scalar is not experimental
conductivity truth. The source author's database.py duplicates relationships
when multiple compound names / values are extracted from a paper.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

from rhombus.qualification.measurement_identity import _json_bytes
from scripts.science.public_transport_shon_original_audit import (
    MAX_BYTES, OFFICIAL_BYTES, OFFICIAL_GIT_BLOB_SHA1,
    inspect_shon_primary_json, _reject_constant,
)

SCHEMA = "rhombus-shon-author-extraction-triage-0139-v1"
DOI_TOKEN = re.compile(r"^10\.\d{4,9}/\S+$", re.ASCII)


def _scalar_category(value: object) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) in (int, float):
        try:
            if not math.isfinite(value):
                return "nonfinite"
        except OverflowError:
            return "nonfinite"
        return "finite_positive" if value > 0 else "finite_nonpositive"
    if type(value) is str:
        return "unparsed_text"
    return "container_or_other"


def audit_shon_author_extractions(
    original: bytes, *, exact_blob_sha1: str = OFFICIAL_GIT_BLOB_SHA1,
    expected_size: int = OFFICIAL_BYTES,
) -> dict:
    # Strict source-byte authenticity, bounded size and JSON nesting apply first.
    verified = inspect_shon_primary_json(
        original, exact_blob_sha1=exact_blob_sha1, expected_size=expected_size)
    rows = json.loads(original.decode("utf-8-sig"), parse_constant=_reject_constant)
    if not isinstance(rows, list):
        raise ValueError("0139 author-extraction source must be verified ARRAY root")
    counters: Counter[str] = Counter()
    value_types: Counter[str] = Counter()
    for entry in rows:
        if not isinstance(entry, dict):
            counters["non_object_root_entries"] += 1
            continue
        counters["object_root_entries"] += 1
        extraction = entry.get("BatteryConductivity")
        if "BatteryConductivity" not in entry:
            counters["author_container_missing"] += 1
            continue
        if not isinstance(extraction, dict):
            counters["author_container_not_object"] += 1
            continue
        counters["author_container_object"] += 1

        category = ("missing" if "value" not in extraction else
                    _scalar_category(extraction["value"]))
        value_types[category] += 1
        valid_extracted_scalar = category == "finite_positive"
        if valid_extracted_scalar:
            counters["positive_extracted_numeric_scalar_NOT_MEASURED_TRUTH"] += 1

        # A human-readable extracted chemical name is not a verified formula,
        # crystal structure, physical specimen, lithium carrier, or unique ID.
        names = extraction.get("names")
        name_signal = type(names) is str and bool(names.strip())
        if name_signal:
            counters["nonempty_author_extracted_name"] += 1

        # DOI is a paper-level citation token, NOT physical sample uniqueness.
        meta = entry.get("metadata")
        if "metadata" in entry:
            counters["metadata_field_present"] += 1
        doi = meta.get("doi") if isinstance(meta, dict) else None
        doi_signal = (
            type(doi) is str and len(doi) <= 256
            and bool(DOI_TOKEN.fullmatch(doi.strip()))
        )
        if doi_signal:
            counters["syntactically_plausible_paper_DOI"] += 1
        if "units" in extraction:
            counters["unverified_extraction_unit_field_present"] += 1
        if "warning" in entry:
            counters["original_author_warning_field_present"] += 1
        if valid_extracted_scalar and name_signal and doi_signal:
            counters["three_signal_manual_literature_review_candidates_NOT_SAMPLES"] += 1

    total = len(rows)
    assert sum(counters[x] for x in (
        "non_object_root_entries", "object_root_entries")) == total
    assert sum(counters[x] for x in (
        "author_container_missing", "author_container_not_object",
        "author_container_object")) == counters["object_root_entries"]
    assert sum(value_types.values()) == counters["author_container_object"]
    return {
        "schema_version": SCHEMA,
        "source_git_blob_sha1": verified["original_git_blob_sha1_verified"],
        "source_original_sha256": verified["original_file_sha256"],
        "original_root_entries_NOT_independent_samples": total,
        "author_schema_shape_counts": {
            key: counters[key] for key in (
                "object_root_entries", "non_object_root_entries",
                "author_container_missing", "author_container_not_object",
                "author_container_object",
            )
        },
        "author_extracted_value_type_counts": {
            key: value_types[key] for key in (
                "missing", "null", "boolean", "finite_positive",
                "finite_nonpositive", "nonfinite", "unparsed_text",
                "container_or_other",
            )
        },
        "author_metadata_presence_counts_NOT_scientific_confirmation": {
            key: counters[key] for key in (
                "positive_extracted_numeric_scalar_NOT_MEASURED_TRUTH",
                "nonempty_author_extracted_name",
                "metadata_field_present",
                "syntactically_plausible_paper_DOI",
                "unverified_extraction_unit_field_present",
                "original_author_warning_field_present",
                "three_signal_manual_literature_review_candidates_NOT_SAMPLES",
            )
        },
        "author_code_may_expand_name_value_combinations": True,
        "source_text_mining_extractions_NOT_validated_experiments": True,
        "exact_experimental_temperature_attested": 0,
        "actual_crystal_structure_or_phase_attested": 0,
        "physical_experiment_specimen_identity_attested": 0,
        "independent_material_count": None,
        "newly_scientifically_qualified_materials": 0,
        "original_source_republication_rights_verified": False,
        "original_source_rows_keys_DOIs_values_republished": False,
        "selected_MACE_training_frames_authenticated": False,
        "external_new_sealed_blind_cohort_qualified": False,
        "original_OBELiX_public_TEST_excluded": True,
        "scientific_score_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        source = args.original_json.resolve(strict=True)
        output = args.output_dir.resolve()
        if output.exists() or output == source or source in output.parents:
            raise ValueError("output must be new and separate from original")
        with source.open("rb") as stream:
            report = audit_shon_author_extractions(stream.read(MAX_BYTES + 1))
        output.mkdir(parents=True, exist_ok=False)
        (output / "shon_author_extraction_aggregate.json").write_bytes(
            _json_bytes(report) + b"\n")
    except (ValueError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
