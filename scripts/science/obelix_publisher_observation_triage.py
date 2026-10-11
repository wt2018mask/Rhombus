"""0132 offline, source-bound publisher-page triage of original OBELiX TRAIN rows.

Publisher-abstract observations are useful evidence leads, NOT independently
reviewed numeric figure/table values or authoritative scientific attestations.
The tool cannot qualify materials or unlock public TEST for model development.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from rhombus.qualification.measurement_identity import (
    _json_bytes, _parse_json, _read_input, _records_from_jsonl,
)
from scripts.science.obelix_adjudication_queue import build_adjudication_queue
from scripts.science.obelix_real_source_pipeline import SOURCE_COMMIT

SCHEMA = "rhombus-publisher-observation-triage-0132-v1"
INPUT_SCHEMA = "rhombus-0132-publisher-abstract-observation-v1"
MAX_OBSERVATIONS = 250
_FIELDS = {
    "source_entry_id", "source_record_sha256", "reference_doi",
    "publisher_url", "publisher_visible_scope", "publisher_visible_summary",
    "unresolved_review_flags", "evidence_excerpt_level",
}
_SCOPES = {
    "EXPLICIT_300_C_EXCERPT",
    "ROOM_TEMPERATURE_BULK_CONDUCTIVITY_SERIES",
    "APPROX_ROOM_TEMPERATURE_AND_HIGH_T_PHASE_TRANSITION",
}
_FLAGS = {
    "TEMPERATURE_PROVENANCE_REQUIRES_ORIGINAL_TABLE",
    "EXTRAPOLATION_OR_OTHER_ROOM_TEMPERATURE_SOURCE_UNRESOLVED",
    "MULTICOMPOUND_MEASUREMENT_BINDING_UNRESOLVED",
    "MEASUREMENT_COMPONENT_BULK_TOTAL_UNRESOLVED",
    "NUMERIC_DATASET_PAPER_MAPPING_REQUIRES_ORIGINAL_TABLE",
    "EXACT_ROOM_TEMPERATURE_K_UNATTESTED",
    "PHASE_TRANSITION_AND_STRUCTURE_BINDING_REQUIRES_ORIGINAL_TABLE",
}
_LEVELS = {"PUBLISHER_ARTICLE_ABSTRACT", "PUBLISHER_VISIBLE_ARTICLE_TEXT"}


def _canonical_rows(rows: list[dict]) -> bytes:
    return b"".join(_json_bytes(row) + b"\n" for row in rows)


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _publisher_link(doi: str, url: str) -> bool:
    if not isinstance(url, str) or len(url) > 300:
        return False
    p = urlparse(url)
    if p.scheme != "https" or p.query or p.fragment or p.username or p.password or p.port:
        return False
    if p.hostname == "pubs.acs.org":
        return doi.startswith("10.1021/") and p.path.lower().rstrip("/").endswith(doi)
    if p.hostname == "pubs.rsc.org":
        return (doi.startswith("10.1039/")
                and p.path.lower().rstrip("/").endswith(doi.split("/")[-1]))
    return False


def triage_publisher_observations(
    evidence_dir: Path,
    observations: dict,
    *,
    require_official: bool = True,
) -> tuple[list[dict], dict]:
    work, papers, queue_summary = build_adjudication_queue(
        evidence_dir, require_official=require_official,
    )
    if not isinstance(observations, dict) or set(observations) != {
        "schema_version", "review_scope", "observation_date_utc",
        "original_source_commit", "declarations",
        "all_observations_independently_authenticated",
        "original_tables_or_figures_independently_checked",
        "newly_qualified_materials", "source_records_are_public_training_only",
    }:
        raise ValueError("publisher observation bundle has unknown or missing fields")
    if (observations["schema_version"] != INPUT_SCHEMA
            or observations["review_scope"] !=
            "AUTHOR_READ_PUBLISHER_VISIBLE_WEB_PAGE_METADATA_NOT_ORIGINAL_NUMERIC_TABLE_ADJUDICATION"
            or observations["original_source_commit"] != queue_summary["upstream_source_commit"]
            or observations["all_observations_independently_authenticated"] is not False
            or observations["original_tables_or_figures_independently_checked"] is not False
            or type(observations["newly_qualified_materials"]) is not int
            or observations["newly_qualified_materials"] != 0
            or observations["source_records_are_public_training_only"] is not True):
        raise ValueError("unsafe paper observation science qualification claim")
    if require_official and observations["original_source_commit"] != SOURCE_COMMIT:
        raise ValueError("published source commit mismatch")
    declarations = observations["declarations"]
    if not isinstance(declarations, list) or not 1 <= len(declarations) <= MAX_OBSERVATIONS:
        raise ValueError("publisher evidence observation budget exceeded or empty")
    if observations["observation_date_utc"] != "2026-10-11":
        raise ValueError("unexpected source observation review date")
    indexed = {r["source_entry_id"]: r for r in work}
    if len(indexed) != len(work):
        raise ValueError("duplicate source queue IDs")
    paper_lookup: dict[str, set[str]] = {}
    for paper in papers:
        paper_lookup.setdefault(paper["reference_doi_or_missing_id"], set()).update(
            paper["official_train_record_ids"]
        )
    seen = set()
    output = []
    counts: Counter[str] = Counter()
    for item in declarations:
        if not isinstance(item, dict) or set(item) != _FIELDS:
            raise ValueError("invalid publisher observation item schema")
        source_id, doi = item["source_entry_id"], item["reference_doi"]
        if not isinstance(source_id, str) or source_id not in indexed or source_id in seen:
            raise ValueError("unknown or duplicate paper observation material ID")
        seen.add(source_id)
        original = indexed[source_id]
        if (original["official_original_split"] != "TRAIN"
                or original["access_policy"] != "TRAIN_SOURCE_CURATION_ONLY_NO_MODEL_SCIENCE_PASS"):
            raise ValueError("public official TEST observation forbidden in development")
        if item["source_record_sha256"] != original["source_record_sha256"]:
            raise ValueError("source record SHA256 does not match original 0131")
        if (not isinstance(doi, str) or doi not in original["original_reference_dois"]
                or source_id not in paper_lookup.get(doi, set())):
            raise ValueError("DOI not linked to original source row and paper queue")
        if not _publisher_link(doi, item["publisher_url"]):
            raise ValueError("nonpublisher or DOI-inconsistent source URL")
        if item["publisher_visible_scope"] not in _SCOPES:
            raise ValueError("publisher observation scope unrecognized")
        if item["evidence_excerpt_level"] not in _LEVELS:
            raise ValueError("publisher source level unrecognized")
        summary = item["publisher_visible_summary"]
        if not isinstance(summary, str) or not 30 <= len(summary) <= 900:
            raise ValueError("publisher observation note absent or over limit")
        flags = item["unresolved_review_flags"]
        if (not isinstance(flags, list) or not 1 <= len(flags) <= 12
                or not all(isinstance(f, str) and f in _FLAGS for f in flags)
                or len(flags) != len(set(flags))):
            raise ValueError("paper temperature/quantity/phase review flags invalid")
        if (item["publisher_visible_scope"] == "EXPLICIT_300_C_EXCERPT"
                and "TEMPERATURE_PROVENANCE_REQUIRES_ORIGINAL_TABLE" not in flags):
            raise ValueError("high-temperature abstract cannot certify room-temperature value")
        counts[item["publisher_visible_scope"]] += 1
        counts["TRAIN_SOURCE_OBSERVATION"] += 1
        output.append({
            "schema_version": SCHEMA,
            "source_entry_id": source_id,
            "source_record_sha256": item["source_record_sha256"],
            "original_official_split": "TRAIN",
            "source_curation_lane": original["curation_lane"],
            "reference_doi": doi,
            "publisher_url": item["publisher_url"],
            "publisher_visible_scope": item["publisher_visible_scope"],
            "publisher_visible_summary": summary,
            "unresolved_review_flags": sorted(flags),
            "evidence_excerpt_level": item["evidence_excerpt_level"],
            "source_scientific_truth_review_status": "ORIGINAL_TABLE_AND_SAMPLE_BINDING_REQUIRED",
            "paper_page_observation_independently_authenticated": False,
            "material_independence_verified": False,
            "exact_temperature_and_extrapolation_verified": False,
            "correct_comparable_transport_quantity_verified": False,
            "original_phase_sample_structure_verified": False,
            "exact_MACE_model_training_exposure_verified": False,
            "scientific_qualification_authorized": False,
        })
    output.sort(key=lambda x: x["source_entry_id"])
    blob = _canonical_rows(output)
    report = {
        "schema_version": SCHEMA,
        "source_commit": queue_summary["upstream_source_commit"],
        "source_original_records_sha256": queue_summary["upstream_records_jsonl_sha256"],
        "source_queue_records_sha256": queue_summary["record_worklist_sha256"],
        "source_paper_queue_sha256": queue_summary["study_worklist_sha256"],
        "publisher_observations_input_sha256": _sha(_json_bytes(observations)),
        "review_rows_jsonl_sha256": _sha(blob),
        "publisher_page_observations": len(output),
        "publisher_page_observations_in_train": len(output),
        "official_train_record_count": queue_summary["official_train_records_in_review"],
        "official_test_record_count_reserved": queue_summary["official_test_records_reserved"],
        "observation_scope_counts": {s: counts[s] for s in sorted(_SCOPES)},
        "independently_verified_original_paper_tables": 0,
        "verified_independent_material_count": None,
        "scientifically_qualified_transport_count": None,
        "new_external_blind_materials": 0,
        "scientific_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "limitations": [
            "PUBLISHER_ABSTRACT_FACT_IS_NOT_ROW_LEVEL_EXPERIMENTAL_TRUTH",
            "HIGH_T_MEASUREMENT_DOES_NOT_INVALIDATE_DERIVED_RT_VALUE_WITHOUT_ORIGINAL_FIGURE",
            "AUTHOR_OBSERVED_WEB_PAGE_NOT_INDEPENDENT_AUTHENTICATION",
            "NO_TEST_DATA_USED_FOR_DEVELOPMENT",
            "DOI_IS_NOT_INDEPENDENT_SAMPLE_IDENTITY",
            "NO_MACE_SELECTED_FRAME_TRAINING_EXCLUSION_PROOF",
        ],
    }
    return output, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--observations-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        out = args.output_dir.resolve()
        source = args.evidence_dir.resolve(strict=True)
        observation_file = args.observations_json.resolve(strict=True)
        if out == source or source in out.parents or out == observation_file:
            raise ValueError("output must not overwrite source evidence")
        if out.exists():
            raise ValueError("output destination must not pre-exist")
        observed = _parse_json(_read_input(observation_file))
        rows, report = triage_publisher_observations(source, observed)
        out.mkdir(parents=True, exist_ok=False)
        (out / "publisher_observation_review.jsonl").write_bytes(_canonical_rows(rows))
        (out / "summary.json").write_bytes(_json_bytes(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
