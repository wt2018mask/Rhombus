"""Offline verification of the bound MPTrj/WBM source-only evidence pair.

Checks a completed, original-source-gated aggregate JSON plus its positive-only
material-level JSONL file. No network, original source download, or MACE-MPA-0
training-membership attestation can follow from this diagnostic.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

from rhombus.domain.mptrj_source_overlap import WBM_COUNT, WBM_SHA256
from rhombus.domain.structure_protocols import (
    CANDIDATE_FINGERPRINT_PROTOCOL_ID,
    PROTOTYPE_GROUP_PROTOCOL_ID,
)

SHA = re.compile(r"[a-f0-9]{64}\Z")
MAX_SUMMARY_BYTES = 65536
MAX_ROW_BYTES = 8192
MAX_TARGET_BYTES = 256 * 1024 * 1024
CLASS_KEYS = {
    "strict_original_source_structure_match": (
        "strict_source_frame_locator", "wbm_structures_strict_mptrj_source_match"),
    "near_original_source_structure_match": (
        "near_source_frame_locator", "wbm_structures_near_mptrj_source_match"),
    "original_source_prototype_overlap": (
        "prototype_source_frame_locator", "wbm_structures_prototype_mptrj_source_overlap"),
}
ROW_KEYS = {
    "record_type", "material_id", "mptrj_source_sha256",
    "wbm_initial_source_sha256", "model_training_membership_attested",
    "unseen_generalization_claim", *CLASS_KEYS,
    *(loc for loc, _ in CLASS_KEYS.values()),
}


class SourceTargetPairError(ValueError):
    """Incomplete, inconsistent, tampered or claim-promoting source-only output."""


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SourceTargetPairError("duplicate field in source-only evidence JSON")
        result[key] = value
    return result


def _object(raw: bytes) -> dict:
    result = json.loads(
        raw, object_pairs_hook=_no_duplicate_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(
            SourceTargetPairError("nonfinite JSON in source-only evidence")),
    )
    if not isinstance(result, dict):
        raise SourceTargetPairError("expected evidence object")
    return result


def verify_pair(
    summary_path: Path, matched_path: Path, *,
    expected_wbm_sha256: str = WBM_SHA256,
    expected_wbm_count: int = WBM_COUNT,
) -> dict:
    """Prove archived JSONL bytes match source-gated summary, source-only."""
    if (summary_path.is_symlink() or matched_path.is_symlink()
            or not summary_path.is_file() or not matched_path.is_file()
            or summary_path.resolve() == matched_path.resolve()):
        raise SourceTargetPairError("two distinct existing regular evidence files required")
    if not 1 <= summary_path.stat().st_size <= MAX_SUMMARY_BYTES:
        raise SourceTargetPairError("invalid bounded aggregate report")
    if matched_path.stat().st_size > MAX_TARGET_BYTES:
        raise SourceTargetPairError("matched JSONL exceeds source-only byte budget")
    summary = _object(summary_path.read_bytes())
    if (summary.get("status") != "SOURCE_ONLY_NOT_MACE_MPA0_TRAINING_SET"
            or summary.get("schema_version") != "rhombus-mptrj-wbm-original-source-overlap-v1"
            or summary.get("wbm_initial_source_sha256") != expected_wbm_sha256
            or summary.get("fingerprint_protocol_id") != CANDIDATE_FINGERPRINT_PROTOCOL_ID
            or summary.get("prototype_protocol_id") != PROTOTYPE_GROUP_PROTOCOL_ID
            or type(summary.get("wbm_initial_structure_count")) is not int
            or summary["wbm_initial_structure_count"] != expected_wbm_count
            or type(summary.get("mptrj_complete_frames")) is not int
            or summary["mptrj_complete_frames"] <= 0
            or any(summary.get(key) is not False for key in (
                "exact_mace_mpa0_training_membership_attested",
                "execute_training_exposure_audit", "unseen_generalization_claim",
                "empirical_calibration_use"
            ))):
        raise SourceTargetPairError("source identity, row count or scientific scope invalid")
    source_sha = summary.get("mptrj_canonical_source_sha256")
    expected_jsonl_sha = summary.get("source_only_matched_wbm_jsonl_sha256")
    expected_rows = summary.get("source_only_matched_wbm_rows_exported")
    if (not isinstance(source_sha, str) or SHA.fullmatch(source_sha) is None
            or not isinstance(expected_jsonl_sha, str)
            or SHA.fullmatch(expected_jsonl_sha) is None
            or type(expected_rows) is not int
            or not 0 <= expected_rows <= expected_wbm_count):
        raise SourceTargetPairError("source/JSONL digest or expected material count invalid")
    counts = Counter()
    total = 0
    previous_id = None
    sha = hashlib.sha256()
    with matched_path.open("rb") as handle:
        while line := handle.readline(MAX_ROW_BYTES + 1):
            if len(line) > MAX_ROW_BYTES:
                raise SourceTargetPairError("matched material row exceeds bound")
            sha.update(line)
            if not line.endswith(b"\n"):
                raise SourceTargetPairError("matched JSONL row lacks newline")
            row = _object(line)
            if set(row) != ROW_KEYS or row.get("record_type") != "WBM_ORIGINAL_MPTRJ_SOURCE_MATCH":
                raise SourceTargetPairError("unknown source-only matched material schema")
            material_id = row.get("material_id")
            if (not isinstance(material_id, str) or not material_id.strip()
                    or len(material_id) > 512
                    or (previous_id is not None and material_id <= previous_id)):
                raise SourceTargetPairError("duplicate/unordered or invalid WBM material ID")
            previous_id = material_id
            if (row.get("mptrj_source_sha256") != source_sha
                    or row.get("wbm_initial_source_sha256") != expected_wbm_sha256
                    or row.get("model_training_membership_attested") is not False
                    or row.get("unseen_generalization_claim") is not False):
                raise SourceTargetPairError("source-only row identity or scientific scope mismatch")
            any_positive = False
            for flag, (witness_key, _) in CLASS_KEYS.items():
                value = row[flag]
                witness = row[witness_key]
                if type(value) is not bool:
                    raise SourceTargetPairError("overlap flags must be bool")
                if value:
                    any_positive = True
                    if (not isinstance(witness, str) or not witness.startswith("/")
                            or len(witness) > 4096):
                        raise SourceTargetPairError("positive source overlap lacks frame witness")
                    counts[flag] += 1
                elif witness is not None:
                    raise SourceTargetPairError("negative source overlap must not carry witness")
            if not any_positive:
                raise SourceTargetPairError("matched-target export cannot contain negatives")
            total += 1
            if total > expected_rows:
                raise SourceTargetPairError("more matched targets than verified summary")
    if total != expected_rows or sha.hexdigest() != expected_jsonl_sha:
        raise SourceTargetPairError("source-only JSONL count/SHA256 differs from aggregate")
    for flag, (_, report_key) in CLASS_KEYS.items():
        if (type(summary.get(report_key)) is not int
                or summary[report_key] != counts[flag]):
            raise SourceTargetPairError("per-class source overlap count differs from summary")
    return {
        "status": "VERIFIED_MPTRJ_SOURCE_ONLY_REPORT_AND_JSONL_PAIR",
        "matched_rows": total,
        "mptrj_canonical_source_sha256": source_sha,
        "matched_targets_jsonl_sha256": sha.hexdigest(),
        "wbm_initial_source_sha256": expected_wbm_sha256,
        "model_training_membership_attested": False,
        "unseen_generalization_claim": False,
        "empirical_calibration_use": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--aggregate-report", type=Path, required=True)
    p.add_argument("--matched-targets-jsonl", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = verify_pair(args.aggregate_report, args.matched_targets_jsonl)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, TypeError, UnicodeError) as exc:
        print(f"MPTRJ_WBM_SOURCE_TARGET_PAIR_FAIL_CLOSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
