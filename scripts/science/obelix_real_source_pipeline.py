"""Reproducible, CPU-only 0127 -> 0128 -> 0129 real-source evidence run.

Input: clean exact Git checkout of publicly available OBELiX.
Output: hash-bound diagnostic artifacts only. No model, Kaggle or science GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from rhombus.qualification.obelix_benchmark_intake import (
    SOURCE_COMMIT,
    _json_bytes,
    build_obelix_benchmark_intake,
)
from rhombus.qualification.measurement_identity import review_measurement_identity
from rhombus.qualification.transport_scoreability import assess_transport_scoreability

SCHEMA = "rhombus-obelix-real-source-three-stage-run-v1"
_EXPECTED = {
    "records": 599,
    "train": 478,
    "test": 121,
    "cif": 321,
    "match": 260,
    "close_match": 61,
    "no_match": 278,
}
_OUTPUTS = (
    "0127/records.jsonl",
    "0127/summary.json",
    "0128/review_pairs.jsonl",
    "0128/summary.json",
    "0129/scoreability_records.jsonl",
    "0129/summary.json",
)


def _bytes(rows: list[dict]) -> bytes:
    return b"".join(_json_bytes(row) + b"\n" for row in rows)


def _write_json(destination: Path, obj: dict) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_json_bytes(obj) + b"\n")


def _write_rows(destination: Path, rows: list[dict]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_bytes(rows))


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def run_three_stage_obelix(
    checkout: Path,
    output_dir: Path,
    *,
    expected_commit: str = SOURCE_COMMIT,
    require_official_counts: bool = True,
) -> dict:
    """Run three science diagnostics as one immutable, attributed source bundle.

    For fixture-only unit tests, pass a fixture commit and explicitly set
    require_official_counts=False. The CLI never exposes that bypass.
    """
    root = Path(checkout).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("source checkout must be an existing directory")
    if require_official_counts and expected_commit != SOURCE_COMMIT:
        raise ValueError("official run requires frozen upstream source commit")
    output = Path(output_dir).resolve()
    if output == root or root in output.parents:
        raise ValueError("output cannot be inside the original source checkout")
    if output.exists():
        raise ValueError("output destination must not pre-exist")
    output.parent.mkdir(parents=True, exist_ok=True)

    # Do all scientific validation before creating a user-visible output.
    records, source = build_obelix_benchmark_intake(
        root, expected_commit=expected_commit,
    )
    if require_official_counts:
        observed = {
            "records": source["record_count"],
            "train": source["official_train_count"],
            "test": source["official_test_count"],
            "cif": source["available_cif_count"],
            "match": source["cif_category_counts"]["Match"],
            "close_match": source["cif_category_counts"]["Close Match"],
            "no_match": source["cif_category_counts"]["No Match"],
        }
        if observed != _EXPECTED:
            raise ValueError("frozen OBELiX source totals differ from approved version")
    pairs, review = review_measurement_identity(
        records, obelix_summary=source,
    )
    scoring, readiness = assess_transport_scoreability(
        records, obelix_summary=source,
        review_pairs=pairs, identity_summary=review,
    )
    if (
        source["record_count"] != len(records)
        or len(scoring) != len(records)
        or source["records_jsonl_sha256"] != _sha(_bytes(records))
        or review["review_pairs_sha256"] != _sha(_bytes(pairs))
        or readiness["scoreability_records_sha256"] != _sha(_bytes(scoring))
        or readiness["scientific_qualification_authorized"] is not False
        or readiness["independent_material_count"] is not None
        or readiness["independently_blinded_material_count"] != 0
    ):
        raise ValueError("inconsistent diagnostic provenance or science gate")

    stage_data = {
        "0127/records.jsonl": _bytes(records),
        "0127/summary.json": _json_bytes(source) + b"\n",
        "0128/review_pairs.jsonl": _bytes(pairs),
        "0128/summary.json": _json_bytes(review) + b"\n",
        "0129/scoreability_records.jsonl": _bytes(scoring),
        "0129/summary.json": _json_bytes(readiness) + b"\n",
    }
    if set(stage_data) != set(_OUTPUTS):
        raise AssertionError("unexpected pipeline output")
    manifest: dict = {
        "schema_version": SCHEMA,
        "scope": ("OFFICIAL_PUBLIC_DIAGNOSTIC" if require_official_counts
                  else "SYNTHETIC_FIXTURE_ONLY"),
        "upstream_repository": "NRC-Mila/OBELiX",
        "upstream_source_commit": source["source_commit"],
        "upstream_source_tree": source["source_tree"],
        "attribution": "NRC-Mila/OBELiX, CC-BY-4.0; source is openly published",
        "source_records": len(records),
        "official_train": source["official_train_count"],
        "official_test": source["official_test_count"],
        "linked_cif_files": source["available_cif_count"],
        "possible_overlap_pairs": len(pairs),
        "records_with_possible_collision": readiness[
            "records_with_possible_identity_collision"],
        "scoreability_preflight_status_counts": readiness[
            "scoreability_preflight_status_counts"],
        "files": {
            name: {"sha256": _sha(data), "size_bytes": len(data)}
            for name, data in sorted(stage_data.items())
        },
        "independent_material_count": None,
        "qualified_experimental_transport_count": None,
        "new_externally_blinded_count": 0,
        "scientific_verdict": "INDETERMINATE",
        "scientific_qualification_authorized": False,
        "model_training_membership_independently_verified": False,
        "experimental_source_truth_independently_adjudicated": False,
        "kaggle_gpu_submitted": False,
    }
    # Temp-directory commit avoids presenting half-complete provenance.
    staging = Path(tempfile.mkdtemp(prefix=".obelix-0130-", dir=output.parent))
    try:
        for name, data in stage_data.items():
            dst = staging / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            if _sha(dst.read_bytes()) != manifest["files"][name]["sha256"]:
                raise ValueError("persisted source evidence bytes mismatch")
        _write_json(staging / "manifest.json", manifest)
        if output.exists():
            raise ValueError("output destination changed during source run")
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obelix-checkout", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = run_three_stage_obelix(args.obelix_checkout, args.output_dir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(manifest, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
