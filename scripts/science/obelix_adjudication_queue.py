"""Science 0131: bounded, evidence-bound source-paper adjudication queue.

Uses ONLY the original public OBELiX records and the 0127-0130 diagnostic
chain. It does not fetch papers, consume public TEST truth for development,
merge samples, certify material identity, or produce model scores.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from rhombus.qualification.measurement_identity import (
    _json_bytes, _parse_json, _read_input, _records_from_jsonl,
)
from rhombus.qualification.transport_scoreability import assess_transport_scoreability
from scripts.science.obelix_real_source_pipeline import (
    SCHEMA as INPUT_SCHEMA, SOURCE_COMMIT, _EXPECTED, _OUTPUTS,
)

SCHEMA = "rhombus-obelix-source-adjudication-queue-v1"
LEVELS = (
    "TRAIN_A_EXACT_CIF_NO_SIGNAL",
    "TRAIN_B_EXACT_CIF_REVIEW_OVERLAP",
    "TRAIN_C_EXPERIMENTAL_PHASE_REVIEW",
    "TRAIN_D_STRUCTURE_ACQUISITION",
    "TRAIN_E_SOURCE_VALUE_REVIEW",
    "TEST_RESERVED_AUDIT_ONLY",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _jsonl(data: list[dict]) -> bytes:
    return b"".join(_json_bytes(row) + b"\n" for row in data)


def _source_bundle(root: Path, *, official: bool) -> tuple[dict, list, list, list]:
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("0130 evidence root is not a directory")
    manifest = _parse_json(_read_input(root / "manifest.json"))
    if (not isinstance(manifest, dict)
            or manifest.get("schema_version") != INPUT_SCHEMA
            or manifest.get("scientific_qualification_authorized") is not False
            or manifest.get("independent_material_count") is not None
            or manifest.get("qualified_experimental_transport_count") is not None
            or manifest.get("new_externally_blinded_count") != 0
            or manifest.get("scientific_verdict") != "INDETERMINATE"):
        raise ValueError("0130 manifest not a scientific diagnostic input")
    scope = ("OFFICIAL_PUBLIC_DIAGNOSTIC" if official else "SYNTHETIC_FIXTURE_ONLY")
    if manifest.get("scope") != scope:
        raise ValueError("0130 source has the wrong evidence scope")
    if official and manifest.get("upstream_source_commit") != SOURCE_COMMIT:
        raise ValueError("0130 original public checkout commit mismatch")
    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != set(_OUTPUTS):
        raise ValueError("0130 missing/extra expected pipeline files")
    buffers = {}
    for name in _OUTPUTS:
        path = root / name
        raw = _read_input(path)
        meta = files[name]
        if (not isinstance(meta, dict) or set(meta) != {"sha256", "size_bytes"}
                or meta["sha256"] != _sha(raw)
                or type(meta["size_bytes"]) is not int
                or meta["size_bytes"] != len(raw)):
            raise ValueError("0130 evidence artifact digest/length mismatch: " + name)
        buffers[name] = raw

    records = _records_from_jsonl(buffers["0127/records.jsonl"])
    pair_rows = _records_from_jsonl(buffers["0128/review_pairs.jsonl"])
    score_rows = _records_from_jsonl(buffers["0129/scoreability_records.jsonl"])
    src_summary = _parse_json(buffers["0127/summary.json"])
    overlap_summary = _parse_json(buffers["0128/summary.json"])
    score_summary = _parse_json(buffers["0129/summary.json"])
    # Recalculate the full 0128 pair list and 0129 scoreability evidence.
    checked_rows, checked_summary = assess_transport_scoreability(
        records, obelix_summary=src_summary,
        review_pairs=pair_rows, identity_summary=overlap_summary,
    )
    if score_rows != checked_rows or score_summary != checked_summary:
        raise ValueError("0130 scoreability rows/summary disagree with recomputed science")
    if (manifest.get("source_records") != len(records)
            or manifest.get("official_train") != src_summary["official_train_count"]
            or manifest.get("official_test") != src_summary["official_test_count"]
            or manifest.get("possible_overlap_pairs") != len(pair_rows)
            or manifest.get("records_with_possible_collision")
            != score_summary["records_with_possible_identity_collision"]
            or manifest.get("scoreability_preflight_status_counts")
            != score_summary["scoreability_preflight_status_counts"]):
        raise ValueError("0130 aggregate claims disagree with source evidence")
    if official and (
        manifest["source_records"] != _EXPECTED["records"]
        or manifest["official_train"] != _EXPECTED["train"]
        or manifest["official_test"] != _EXPECTED["test"]
        or manifest.get("linked_cif_files") != _EXPECTED["cif"]
    ):
        raise ValueError("unexpected pinned original OBELiX record total")
    return manifest, records, pair_rows, score_rows


def build_adjudication_queue(
    evidence_root: Path, *, require_official: bool = True,
) -> tuple[list[dict], list[dict], dict]:
    """Emit one record work item and independent DOI-index entries; no merge."""
    manifest, records, pairs, scoreability = _source_bundle(
        evidence_root, official=require_official,
    )
    by_score = {r["source_entry_id"]: r for r in scoreability}
    if len(by_score) != len(records):
        raise ValueError("duplicate scoreability identities")
    conflict = Counter()
    cross_split = set()
    for p in pairs:
        a = p["left_source_identity"].removeprefix("OBELiX:")
        b = p["right_source_identity"].removeprefix("OBELiX:")
        conflict[a] += 1
        conflict[b] += 1
        if p["review_class"] == "PUBLIC_OFFICIAL_SPLIT_POTENTIAL_LEAKAGE":
            cross_split.update((a, b))

    work: list[dict] = []
    studies: dict[str, set[str]] = defaultdict(set)
    counts = Counter()
    for r in records:
        sid = r["source_entry_id"]
        s = by_score[sid]
        if r["official_split"] != s["original_official_split"]:
            raise ValueError("original official train/test identity changed")
        if conflict[sid] != s["possible_identity_review_pair_count"]:
            raise ValueError("0128 overlap pair attribution does not match scoreability")
        if r["official_split"] == "TEST":
            lane = "TEST_RESERVED_AUDIT_ONLY"
            access = "AUDIT_ONLY_NO_DEVELOPMENT_TUNING"
        else:
            access = "TRAIN_SOURCE_CURATION_ONLY_NO_MODEL_SCIENCE_PASS"
            if (r["source_cif_match_status"] == "Match"
                    and r["measurement_kind"] == "PROCESSED_REPORTED_POINT"
                    and r["reference_dois"] and not conflict[sid]):
                lane = "TRAIN_A_EXACT_CIF_NO_SIGNAL"
            elif r["source_cif_match_status"] == "Match" and conflict[sid]:
                lane = "TRAIN_B_EXACT_CIF_REVIEW_OVERLAP"
            elif r["source_cif_match_status"] == "Close Match":
                lane = "TRAIN_C_EXPERIMENTAL_PHASE_REVIEW"
            elif r["source_cif_match_status"] == "No Match":
                lane = "TRAIN_D_STRUCTURE_ACQUISITION"
            else:
                lane = "TRAIN_E_SOURCE_VALUE_REVIEW"
            for doi in r["reference_dois"]:
                studies[doi].add(sid)
            if not r["reference_dois"]:
                studies["MISSING_DOI_RECORD:" + sid].add(sid)
        counts[lane] += 1
        work.append({
            "schema_version": SCHEMA,
            "source_entry_id": sid,
            "source_record_sha256": s["source_record_sha256"],
            "official_original_split": r["official_split"],
            "curation_lane": lane,
            "access_policy": access,
            "original_reference_dois": r["reference_dois"],
            "cif_match_status": r["source_cif_match_status"],
            "possible_pair_count": conflict[sid],
            "cross_official_split_overlap_signal": sid in cross_split,
            "missing_or_unverified_requirements": s[
                "missing_or_unverified_requirements"],
            "experimental_record_independently_adjudicated": False,
            "material_identity_independently_authenticated": False,
            "source_qualified_as_scientific_truth": False,
            "new_externally_blinded_material": False,
        })
    if set(counts) - set(LEVELS):
        raise ValueError("unknown source review priority")
    work.sort(key=lambda x: (LEVELS.index(x["curation_lane"]), x["source_entry_id"]))
    rank = {r["source_entry_id"]: i for i, r in enumerate(work)}
    indexed = []
    for doi, ids in studies.items():
        ordered = sorted(ids, key=lambda sid: (rank[sid], sid))
        indexed.append({
            "reference_doi_or_missing_id": doi,
            "official_train_record_ids": ordered,
            "distinct_source_record_count": len(ordered),
            "first_curation_lane": work[rank[ordered[0]]]["curation_lane"],
            "independent_study_identity_verified": False,
            "original_paper_evidence_verified": False,
            "independent_material_count": None,
        })
    indexed.sort(key=lambda x: (
        LEVELS.index(x["first_curation_lane"]),
        x["reference_doi_or_missing_id"],
    ))
    # Do not include test record identities in curation study worklist.
    if any(r["official_original_split"] == "TEST" and
           r["curation_lane"] != "TEST_RESERVED_AUDIT_ONLY" for r in work):
        raise ValueError("official public test leakage into training curation")
    if len(work) != manifest["source_records"]:
        raise ValueError("source record dropped from work queue")
    work_blob, study_blob = _jsonl(work), _jsonl(indexed)
    summary = {
        "schema_version": SCHEMA,
        "source_bundle_scope": manifest["scope"],
        "upstream_source_commit": manifest["upstream_source_commit"],
        "upstream_source_tree": manifest["upstream_source_tree"],
        "upstream_records_jsonl_sha256": manifest["files"]["0127/records.jsonl"]["sha256"],
        "upstream_overlap_jsonl_sha256": manifest["files"]["0128/review_pairs.jsonl"]["sha256"],
        "upstream_scoreability_jsonl_sha256": manifest["files"][
            "0129/scoreability_records.jsonl"]["sha256"],
        "record_worklist_sha256": _sha(work_blob),
        "study_worklist_sha256": _sha(study_blob),
        "record_count": len(work),
        "official_train_records_in_review": sum(
            r["official_original_split"] == "TRAIN" for r in work),
        "official_test_records_reserved": counts["TEST_RESERVED_AUDIT_ONLY"],
        "source_paper_review_groups": len(indexed),
        "source_paper_groups_independently_verified": 0,
        "all_lanes": {key: counts[key] for key in LEVELS},
        "possible_record_overlap_pairs": len(pairs),
        "new_independently_adjudicated_materials": 0,
        "independent_material_count": None,
        "qualified_experimental_conductivity_count": None,
        "new_external_blinded_materials": 0,
        "scientific_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "limitations": [
            "WORKLIST_PRIORITY_ONLY_NOT_SCIENTIFIC_QUALITY_RANKING",
            "NO_OVERLAP_SIGNAL_DOES_NOT_PROVE_INDEPENDENCE",
            "DOI_GROUP_IS_NOT_AN_INDEPENDENT_EXPERIMENTAL_STUDY",
            "PUBLIC_TEST_RECORDS_RESERVED_FROM_DEVELOPMENT",
            "RAW_EXPERIMENTAL_TEMPERATURE_AND_PHASE_NOT_REVIEWED",
            "MACE_EXACT_TRAINING_MEMBERSHIP_UNATTESTED",
            "NO_NEW_INDEPENDENT_BLIND_COHORT",
        ],
    }
    return work, indexed, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        source = args.evidence_dir.resolve(strict=True)
        out = args.output_dir.resolve()
        if out == source or source in out.parents or out in source.parents:
            raise ValueError("output must be separate from source evidence bundle")
        if out.exists():
            raise ValueError("destination must not pre-exist")
        work, studies, result = build_adjudication_queue(source)
        out.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".obelix-0131-", dir=out.parent))
        try:
            (staging / "record_review_queue.jsonl").write_bytes(_jsonl(work))
            (staging / "paper_review_queue.jsonl").write_bytes(_jsonl(studies))
            (staging / "summary.json").write_bytes(_json_bytes(result) + b"\n")
            if out.exists():
                raise ValueError("destination changed before commit")
            staging.rename(out)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
