"""Offline material-level transport scoreability preflight, not scientific approval.

Consumes hash-bound OBELiX 0127 and exact 0128 duplicate-review products.
An external declaration may identify missing evidence, but an untrusted SHA
or reviewer assertion is not authenticated experiment provenance.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .measurement_identity import (
    _json_bytes, _parse_json, _read_input, _records_from_jsonl, _validated,
    review_measurement_identity,
)

SCHEMA = "rhombus-transport-scoreability-preflight-v1"
REVIEW_SCHEMA = "rhombus-transport-reference-review-declaration-v1"
MAX_RECORDS = 50_000
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_REVIEW_FIELDS = frozenset({
    "schema_version", "source_entry_id", "source_record_sha256",
    "evidence_artifact_sha256", "measurement_quantity",
    "measurement_temperature_K", "phase_assessment",
    "experimental_value_assessment", "independent_material_assessment",
    "training_exposure_assessment",
})
_QUANTITIES = frozenset({
    "TOTAL_IONIC_CONDUCTIVITY_S_PER_CM",
    "BULK_IONIC_CONDUCTIVITY_S_PER_CM",
})
_PHASES = frozenset({
    "EXACT_EXPERIMENTAL_PHASE_DECLARED", "DIFFERENT_PHASE", "UNKNOWN",
})
_VALUES = frozenset({
    "POINT_MEASUREMENT_REVIEWED", "CENSORED_OR_UPPER_BOUND", "UNKNOWN",
})
_IDENTITIES = frozenset({
    "DISTINCT_MATERIAL_DECLARED", "DUPLICATE_OR_REPLICATE", "UNKNOWN",
})
_EXPOSURES = frozenset({
    "NOT_IN_TRAINING_DECLARED", "IN_TRAINING", "UNKNOWN",
})


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ValueError(name + " must be lowercase SHA256")
    return value


def _temperature(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("review temperature must be an exact Kelvin text value")
    try:
        t = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid review temperature") from exc
    if not t.is_finite() or not Decimal("1") <= t <= Decimal("5000"):
        raise ValueError("review temperature outside finite Kelvin range")
    return str(t.normalize())


def _reviews(rows: Any, source: dict[str, dict]) -> dict[str, dict]:
    if not isinstance(rows, list) or len(rows) > MAX_RECORDS:
        raise ValueError("review declaration count exceeds budget")
    out: dict[str, dict] = {}
    for r in rows:
        if not isinstance(r, dict) or set(r) != _REVIEW_FIELDS:
            raise ValueError("unexpected curation declaration fields")
        if r["schema_version"] != REVIEW_SCHEMA:
            raise ValueError("unknown curation declaration schema")
        rid = r["source_entry_id"]
        if not isinstance(rid, str) or rid not in source or rid in out:
            raise ValueError("duplicate or unknown source review ID")
        if (
            _sha(r["source_record_sha256"], "source record identity")
            != hashlib.sha256(_json_bytes(source[rid])).hexdigest()
        ):
            raise ValueError("curation source record SHA256 mismatch")
        _sha(r["evidence_artifact_sha256"], "external evidence artifact")
        if r["measurement_quantity"] not in _QUANTITIES:
            raise ValueError("experimental conductivity cannot be relabelled as diffusion")
        _temperature(r["measurement_temperature_K"])
        if r["phase_assessment"] not in _PHASES:
            raise ValueError("invalid experimental phase evidence category")
        if r["experimental_value_assessment"] not in _VALUES:
            raise ValueError("invalid experimental value category")
        if r["independent_material_assessment"] not in _IDENTITIES:
            raise ValueError("invalid independence review category")
        if r["training_exposure_assessment"] not in _EXPOSURES:
            raise ValueError("invalid training-exposure review category")
        if (source[rid]["measurement_kind"] == "UPPER_BOUND"
                and r["experimental_value_assessment"] == "POINT_MEASUREMENT_REVIEWED"):
            raise ValueError("censored source may not become a point measurement by declaration")
        if (source[rid]["source_cif_match_status"] != "Match"
                and r["phase_assessment"] == "EXACT_EXPERIMENTAL_PHASE_DECLARED"):
            raise ValueError("nonexact CIF cannot claim exact experimental phase")
        out[rid] = r
    return out


def assess_transport_scoreability(
    obelix_records: list[dict], *,
    obelix_summary: Mapping[str, Any],
    review_pairs: list[dict],
    identity_summary: Mapping[str, Any],
    review_declarations: list[dict] | None = None,
) -> tuple[list[dict], dict]:
    """Preserve EVERY material and disclose unverified scientific conditions."""
    if not isinstance(obelix_records, list) or not isinstance(review_pairs, list):
        raise ValueError("source records and review pairs must be arrays")
    if not isinstance(identity_summary, Mapping):
        raise ValueError("identity report summary required")
    if len(obelix_records) > MAX_RECORDS:
        raise ValueError("OBELiX source record budget exceeded")
    # Reproduce and verify both entire predecessor outputs, not just totals.
    canonical_pairs, canonical_summary = review_measurement_identity(
        obelix_records, obelix_summary=obelix_summary
    )
    if (review_pairs != canonical_pairs or dict(identity_summary) != canonical_summary):
        raise ValueError("0128 identity records, source binding or summary differ")
    source = {row["source_entry_id"]: row for row in obelix_records}
    if len(source) != len(obelix_records):
        raise ValueError("duplicate source IDs")
    declared = _reviews([] if review_declarations is None
                        else review_declarations, source)
    by_record: dict[str, list[dict]] = defaultdict(list)
    for pair in review_pairs:
        left = pair["left_source_identity"]
        right = pair["right_source_identity"]
        if not left.startswith("OBELiX:") or not right.startswith("OBELiX:"):
            raise ValueError("only source-preserved OBELiX identity review accepted")
        by_record[left[7:]].append(pair)
        by_record[right[7:]].append(pair)

    rows: list[dict] = []
    counts: Counter[str] = Counter()
    for row in sorted(obelix_records, key=lambda r: r["source_entry_id"]):
        rid = row["source_entry_id"]
        matches = by_record[rid]
        review = declared.get(rid)
        gaps: list[str] = []
        cif = row["source_cif_match_status"]
        if cif == "No Match":
            gaps.append("NO_SOURCE_CIF_FOR_MODEL_STRUCTURE")
        elif cif == "Close Match":
            gaps.append("SOURCE_CIF_CLOSE_MATCH_NOT_EXACT_PHASE")
        if not row["reference_dois"]:
            gaps.append("EXPERIMENTAL_REFERENCE_DOI_MISSING")
        if row["measurement_kind"] == "UPPER_BOUND":
            gaps.append("CENSORED_VALUE_NOT_POINT_GROUND_TRUTH")
        if matches:
            gaps.append("POSSIBLE_SAME_MATERIAL_OR_MEASUREMENT_REQUIRES_REVIEW")
        if any(p["review_class"] == "PUBLIC_OFFICIAL_SPLIT_POTENTIAL_LEAKAGE"
               for p in matches):
            gaps.append("CROSS_OFFICIAL_SPLIT_POTENTIAL_LEAKAGE")
        if review is None:
            gaps.extend([
                "INDEPENDENT_EXPERIMENTAL_QUANTITY_REVIEW_MISSING",
                "EXACT_MEASUREMENT_TEMPERATURE_K_UNATTESTED",
                "EXPERIMENTAL_PHASE_RELATION_UNATTESTED",
                "ORIGINAL_MEASUREMENT_VALUE_REVIEW_MISSING",
                "INDEPENDENT_MATERIAL_IDENTITY_UNRESOLVED",
                "MODEL_TRAINING_EXPOSURE_UNATTESTED",
            ])
        else:
            if review["phase_assessment"] != "EXACT_EXPERIMENTAL_PHASE_DECLARED":
                gaps.append("PHASE_RELATION_UNRESOLVED_OR_MISMATCHED")
            if review["experimental_value_assessment"] != "POINT_MEASUREMENT_REVIEWED":
                gaps.append("ORIGINAL_MEASUREMENT_NOT_REVIEWED_AS_POINT")
            if review["independent_material_assessment"] != "DISTINCT_MATERIAL_DECLARED":
                gaps.append("MATERIAL_INDEPENDENCE_NOT_DECLARED")
            if review["training_exposure_assessment"] != "NOT_IN_TRAINING_DECLARED":
                gaps.append("MODEL_EXPOSURE_NOT_EXCLUDED")
            # A reviewer-supplied hash is NOT a verified copy, signature, or
            # scientific judgement from an independently authorized steward.
            gaps.append("CURATION_DECLARATION_NOT_INDEPENDENTLY_AUTHENTICATED")
        gaps.append("NEW_EXTERNAL_BLIND_COHORT_NOT_ESTABLISHED")
        if matches:
            status = "POTENTIAL_IDENTITY_CONFLICT_REQUIRES_REVIEW"
        elif review is not None and all(g not in gaps for g in (
            "NO_SOURCE_CIF_FOR_MODEL_STRUCTURE",
            "SOURCE_CIF_CLOSE_MATCH_NOT_EXACT_PHASE",
            "EXPERIMENTAL_REFERENCE_DOI_MISSING",
            "CENSORED_VALUE_NOT_POINT_GROUND_TRUTH",
            "PHASE_RELATION_UNRESOLVED_OR_MISMATCHED",
            "ORIGINAL_MEASUREMENT_NOT_REVIEWED_AS_POINT",
            "MATERIAL_INDEPENDENCE_NOT_DECLARED",
            "MODEL_EXPOSURE_NOT_EXCLUDED",
        )):
            status = "DECLARATION_COMPLETE_INDEPENDENT_AUTHENTICATION_REQUIRED"
        else:
            status = "EVIDENCE_GAPS"
        counts[status] += 1
        counts["ALL_RECORDS"] += 1
        counts["OFFICIAL_" + row["official_split"]] += 1
        counts["CIF_" + cif.replace(" ", "_").upper()] += 1
        if row["measurement_kind"] == "PROCESSED_REPORTED_POINT":
            counts["SOURCE_PROCESSED_NUMERIC_POINT"] += 1
        if matches:
            counts["HAS_POSSIBLE_IDENTITY_COLLISION"] += 1
        rows.append({
            "schema_version": SCHEMA,
            "source_dataset": "OBELiX",
            "source_entry_id": rid,
            "original_official_split": row["official_split"],
            "source_record_sha256": hashlib.sha256(_json_bytes(row)).hexdigest(),
            "source_cif_match_status": cif,
            "structure_preflight": (
                "SOURCE_CIF_ABSENT" if cif == "No Match"
                else "SOURCE_CIF_AVAILABLE_PHASE_UNVERIFIED"
            ),
            "reported_measurement_kind": row["measurement_kind"],
            "temperature_scope": row["reported_temperature_scope"],
            "possible_identity_review_pair_count": len(matches),
            "review_declaration_present": review is not None,
            "scoreability_preflight_status": status,
            "missing_or_unverified_requirements": sorted(set(gaps)),
            "independent_transport_truth_qualified": False,
            "new_external_blind_material": False,
        })
    blob = b"".join(_json_bytes(r) + b"\n" for r in rows)
    summary = {
        "schema_version": SCHEMA,
        "source_records_sha256": obelix_summary["records_jsonl_sha256"],
        "identity_review_pairs_sha256": canonical_summary["review_pairs_sha256"],
        "scoreability_records_sha256": hashlib.sha256(blob).hexdigest(),
        "records_inspected": counts["ALL_RECORDS"],
        "official_train_records": counts["OFFICIAL_TRAIN"],
        "official_test_records": counts["OFFICIAL_TEST"],
        "source_cif_exact_match_records": counts["CIF_MATCH"],
        "source_cif_close_match_records": counts["CIF_CLOSE_MATCH"],
        "source_cif_absent_records": counts["CIF_NO_MATCH"],
        "source_processed_point_records": counts["SOURCE_PROCESSED_NUMERIC_POINT"],
        "records_with_possible_identity_collision": counts["HAS_POSSIBLE_IDENTITY_COLLISION"],
        "independently_unauthenticated_curated_declarations": len(declared),
        "declaration_complete_but_unattested_records": counts[
            "DECLARATION_COMPLETE_INDEPENDENT_AUTHENTICATION_REQUIRED"
        ],
        "scoreability_preflight_status_counts": {
            key: counts[key] for key in (
                "EVIDENCE_GAPS",
                "POTENTIAL_IDENTITY_CONFLICT_REQUIRES_REVIEW",
                "DECLARATION_COMPLETE_INDEPENDENT_AUTHENTICATION_REQUIRED",
            )
        },
        "independent_material_count": None,
        "independent_transport_qualified_material_count": None,
        "independently_blinded_material_count": 0,
        "scientific_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "limitations": [
            "NO_INDEPENDENT_TRUST_ANCHORS_OR_EXPERIMENTAL_REVIEW_ATTESTATION",
            "OBELIX_PROCESSED_ROOM_TEMPERATURE_HAS_NO_EXACT_PER_ROW_K",
            "PUBLIC_OFFICIAL_TEST_IS_NOT_SECRET_BLINDED_TEST",
            "NO_TRANSPORT_OR_SELF_DIFFUSION_EQUIVALENCE_ASSUMPTION",
            "NO_INDEPENDENT_TRAINING_LINEAGE_OR_GENERALIZATION_VALIDATION",
            "POTENTIAL_DUPLICATE_SIGNALS_NOT_SCIENTIFICALLY_ADJUDICATED",
        ],
    }
    return rows, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obelix-records-jsonl", required=True, type=Path)
    parser.add_argument("--obelix-summary-json", required=True, type=Path)
    parser.add_argument("--review-pairs-jsonl", required=True, type=Path)
    parser.add_argument("--identity-summary-json", required=True, type=Path)
    parser.add_argument("--curation-declarations-json", type=Path,
                        help="Optional UNTRUSTED external curation assertions")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    inputs = (args.obelix_records_jsonl, args.obelix_summary_json,
              args.review_pairs_jsonl, args.identity_summary_json)
    try:
        records = _records_from_jsonl(_read_input(inputs[0]))
        summary = _parse_json(_read_input(inputs[1]))
        pairs = _records_from_jsonl(_read_input(inputs[2]))
        identity_summary = _parse_json(_read_input(inputs[3]))
        declared = None
        if args.curation_declarations_json is not None:
            declared = _parse_json(_read_input(args.curation_declarations_json))
        result, report = assess_transport_scoreability(
            records, obelix_summary=summary, review_pairs=pairs,
            identity_summary=identity_summary, review_declarations=declared,
        )
        output = args.output_dir.resolve()
        all_inputs = (*inputs, *(
            (args.curation_declarations_json,)
            if args.curation_declarations_json is not None else ()
        ))
        if any(p.resolve() == output or output in p.resolve().parents for p in all_inputs):
            raise ValueError("output may not overwrite a scientific source")
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError("output directory must be empty")
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    output.mkdir(parents=True, exist_ok=True)
    (output / "scoreability_records.jsonl").write_bytes(
        b"".join(_json_bytes(r) + b"\n" for r in result)
    )
    (output / "summary.json").write_bytes(_json_bytes(report) + b"\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
