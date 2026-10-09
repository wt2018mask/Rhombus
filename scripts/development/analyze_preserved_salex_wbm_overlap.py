"""Offline reanalysis of the archived sAlex->WBM source-overlap JSONL.

Reads the *existing* preserved 2026-10-08 Kaggle output. Does not run
Kaggle, contact Figshare, claim exact MACE-MPA-0 training frame lineage,
or admit WBM structures for generalization calibration.

Compressed and decompressed byte hashes, byte bounds, row count, sAlex
source summary, and source-only boolean fields must all validate before
any aggregate report is emitted.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys

EXPECTED_WBM_ROWS = 256_963
EXPECTED_COMPRESSED_SIZE = 369_521
EXPECTED_COMPRESSED_SHA256 = "5f9e0644ea1eb48ad661b2a62abe88269c962ab9af0daf7e0936c9925290bb44"
EXPECTED_RAW_SHA256 = "31784dcf17862e3bf925971d105e8f4b18a2d2d2a3da4b1eef42c87db5a11c71"
EXPECTED_SUMMARY_SHA256 = "f9928681ebf347de77a99611ae45fa75f34367204206bac7551be4149d0fdcad"
EXPECTED_WBM_SOURCE_SHA256 = "98d545172c1ea9060f03f40cace6f8173a4ac06f1ee875ccd963765211519b58"
EXPECTED_SALEX_SOURCE_SHA256 = "48eb3664d95331e7fd84bfe1f04f5e741600bffcfb1253334c82dae92cebf1ef"
MAX_DECOMPRESSED_BYTES = 384 * 1024 * 1024
MAX_LINE_BYTES = 1_048_576
MAX_SUMMARY_BYTES = 64 * 1024


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field in preserved evidence")
        result[key] = value
    return result


def _decode_dict(raw: bytes) -> dict:
    result = json.loads(raw, object_pairs_hook=_unique_keys,
                        parse_constant=lambda c: (_ for _ in ()).throw(
                            ValueError(f"nonfinite JSON constant {c}")))
    if not isinstance(result, dict):
        raise ValueError("preserved evidence must be a JSON object")
    return result


def _file_hash(path: Path, *, max_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("preserved evidence exceeds byte limit")
            digest.update(chunk)
    return digest.hexdigest(), total


def analyze_rows(stream, *, expected_rows: int, expected_raw_sha256: str,
                 max_raw_bytes: int = MAX_DECOMPRESSED_BYTES) -> dict:
    """One-pass bounded JSONL analysis; source-only flags, never training proof."""
    if type(expected_rows) is not int or expected_rows <= 0:
        raise ValueError("positive expected WBM row count required")
    digest = hashlib.sha256()
    size = 0
    count = 0
    previous_id = None
    flags = Counter()
    for raw in stream:
        if not isinstance(raw, bytes) or len(raw) > MAX_LINE_BYTES:
            raise ValueError("bounded UTF-8 JSONL bytes required")
        size += len(raw)
        if size > max_raw_bytes:
            raise ValueError("decompressed original archive exceeds byte limit")
        digest.update(raw)
        if not raw.strip():
            raise ValueError("blank JSONL row prohibited")
        row = _decode_dict(raw)
        if set(row) != {
            "material_id", "exact_training_match", "near_duplicate_match",
            "prototype_overlap", "audit_basis_ids"
        }:
            raise ValueError("unexpected or missing sAlex WBM overlap fields")
        material_id = row["material_id"]
        if not isinstance(material_id, str) or not material_id.strip():
            raise ValueError("invalid WBM material ID")
        if previous_id is not None and material_id <= previous_id:
            raise ValueError("duplicate or unordered WBM material ID")
        previous_id = material_id
        flag_values = [row["exact_training_match"], row["near_duplicate_match"],
                       row["prototype_overlap"]]
        if not all(type(v) is bool for v in flag_values):
            raise ValueError("source-only overlap flags must be booleans")
        if row["audit_basis_ids"] != [] or type(row["audit_basis_ids"]) is not list:
            raise ValueError("preserved sAlex audit basis must remain unresolved")
        exact, near, prototype = flag_values
        flags["exact"] += exact
        flags["near"] += near
        flags["prototype"] += prototype
        flags["exact_near"] += exact and near
        flags["exact_prototype"] += exact and prototype
        flags["near_prototype"] += near and prototype
        flags["triple"] += exact and near and prototype
        flags["union"] += exact or near or prototype
        flags["strict_only"] += exact and not near and not prototype
        flags["near_only"] += near and not exact and not prototype
        flags["prototype_only"] += prototype and not exact and not near
        count += 1
        if count > expected_rows:
            raise ValueError("too many WBM JSONL records")
    if count != expected_rows:
        raise ValueError(f"incomplete WBM JSONL: {count} of {expected_rows}")
    if digest.hexdigest() != expected_raw_sha256:
        raise ValueError("preserved overlap raw SHA256 mismatch")
    return {
        "wbm_rows_verified": count,
        "overlap_jsonl_raw_sha256": digest.hexdigest(),
        "overlap_jsonl_raw_bytes": size,
        "exact_source_matches": flags["exact"],
        "near_source_matches": flags["near"],
        "prototype_source_matches": flags["prototype"],
        "exact_and_near": flags["exact_near"],
        "exact_and_prototype": flags["exact_prototype"],
        "near_and_prototype": flags["near_prototype"],
        "all_three": flags["triple"],
        "positive_source_overlap_union": flags["union"],
        "strict_only": flags["strict_only"],
        "near_only": flags["near_only"],
        "prototype_only": flags["prototype_only"],
        "no_detected_salex_source_overlap_but_training_unresolved": (
            count - flags["union"]
        ),
    }


def validate_preserved_summary(summary: dict, analysis: dict) -> None:
    if (summary.get("schema_version") != "rhombus-v2-salex-wbm-production-overlap-v1"
            or summary.get("mode") != "PRODUCTION_COMPLETE_SOURCE_STREAM"
            or summary.get("wbm_target_count") != analysis["wbm_rows_verified"]
            or summary.get("wbm_source_sha256") != EXPECTED_WBM_SOURCE_SHA256
            or summary.get("salex_source_sha256") != EXPECTED_SALEX_SOURCE_SHA256
            or summary.get("salex_membership_row_count") != 10_447_765
            or summary.get("overlap_jsonl_sha256") != analysis["overlap_jsonl_raw_sha256"]
            or summary.get("full_training_lineage_resolved") is not False
            or summary.get("unseen_generalization_claim_authorized") is not False
            or summary.get("remaining_blocker") != "MPTRJ_TRAINING_REPRESENTATION_UNATTESTED"):
        raise ValueError("preserved sAlex source summary identity/scientific scope mismatch")
    audit = summary.get("audit_summary")
    if not isinstance(audit, dict) or any(
        type(audit.get(field)) is not int or audit[field] != expected
        for field, expected in (
            ("material_count", analysis["wbm_rows_verified"]),
            ("exact_match_count", analysis["exact_source_matches"]),
            ("near_duplicate_count", analysis["near_source_matches"]),
            ("prototype_overlap_count", analysis["prototype_source_matches"]),
            ("unresolved_count", analysis["wbm_rows_verified"]),
            ("unseen_generalization_eligible_count", 0),
        )
    ):
        raise ValueError("preserved sAlex source summary aggregates disagree with rows")


def analyze_preserved_artifacts(
    compressed_path: Path, summary_path: Path, *,
    expected_compressed_sha256: str = EXPECTED_COMPRESSED_SHA256,
    expected_compressed_size: int = EXPECTED_COMPRESSED_SIZE,
    expected_raw_sha256: str = EXPECTED_RAW_SHA256,
    expected_summary_sha256: str = EXPECTED_SUMMARY_SHA256,
    expected_rows: int = EXPECTED_WBM_ROWS,
) -> dict:
    compressed_sha, compressed_size = _file_hash(
        compressed_path, max_bytes=expected_compressed_size
    )
    if compressed_size != expected_compressed_size or compressed_sha != expected_compressed_sha256:
        raise ValueError("preserved compressed overlap byte identity mismatch")
    summary_sha, _ = _file_hash(summary_path, max_bytes=MAX_SUMMARY_BYTES)
    if summary_sha != expected_summary_sha256:
        raise ValueError("preserved sAlex summary SHA256 mismatch")
    summary = _decode_dict(summary_path.read_bytes())
    try:
        import zstandard as zstd
    except ImportError as exc:
        raise ValueError("install zstandard for preserved archive verification") from exc
    with compressed_path.open("rb") as encoded:
        with zstd.ZstdDecompressor().stream_reader(encoded) as decoded:
            analysis = analyze_rows(
                io.BufferedReader(decoded), expected_rows=expected_rows,
                expected_raw_sha256=expected_raw_sha256,
            )
    validate_preserved_summary(summary, analysis)
    return {
        "schema_version": "rhombus-phase3-salex-wbm-preserved-source-overlap-triage-v1",
        "status": "SOURCE_ONLY_SALEX_COMPONENT_VERIFIED_TRAINING_LINEAGE_UNRESOLVED",
        "source_commit": "643b8a260b6fcff78bb02f3a63f348c29fd91317",
        "archive_sha256": compressed_sha,
        "verified_summary_sha256": summary_sha,
        "wbm_source_sha256": EXPECTED_WBM_SOURCE_SHA256,
        "salex_source_sha256": EXPECTED_SALEX_SOURCE_SHA256,
        "scope": "sAlex original-source comparison component only",
        # Byte-verified historical v1 results remain genuine detected
        # positives, but the legacy site-count bucket can omit near
        # matches across primitive/supercell representations. No v2
        # whole-source recomputation or training-set attestation occurred.
        "historic_candidate_fingerprint_protocol_id": (
            "rhombus-composition-site-count-candidate-fingerprint-v1"
        ),
        "exhaustive_near_overlap_attested": False,
        "full_training_lineage_resolved": False,
        "mace_mpa0_training_frame_membership_attested": False,
        "unseen_generalization_eligible_count": 0,
        "empirical_calibration_authorized": False,
        **analysis,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compressed-overlap", type=Path, required=True)
    parser.add_argument("--preserved-summary", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True, help="new output only")
    args = parser.parse_args(argv)
    try:
        if args.report.is_symlink() or args.report.exists():
            raise ValueError("report must be a new non-symlink destination")
        if args.report.resolve() in (
            args.compressed_overlap.resolve(), args.preserved_summary.resolve()
        ):
            raise ValueError("input/output path collision")
        result = analyze_preserved_artifacts(args.compressed_overlap,
                                             args.preserved_summary)
        with args.report.open("x", encoding="utf-8") as output:
            json.dump(result, output, sort_keys=True, indent=2, allow_nan=False)
            output.write("\n")
        print("SALEX_WBM_PRESERVED_SOURCE_TRIAGE_SUCCESS_NO_UNSEEN_CLAIM")
        return 0
    except (OSError, ValueError) as exc:
        print(f"SALEX_WBM_PRESERVED_SOURCE_TRIAGE_FAIL_CLOSED: {exc}",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
