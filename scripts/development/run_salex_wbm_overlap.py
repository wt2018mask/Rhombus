from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
import urllib.request

from rhombus.domain import (
    SalexSourceIdentity,
    WBMStreamingOverlapAuditor,
    build_salex_membership_index_with_frozen_protocols,
    build_wbm_target_index,
    iter_salex_membership_records,
    iter_wbm_initial_structure_jsonl,
    matbench_prototype_group,
    structure_candidate_fingerprint_sha256,
)

SALEX_URL = "https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241018/sAlex/train.tar.gz"
SALEX_SIZE = 8071921954
SALEX_MD5 = "8ad69db0c2261541530ae8bc772c5b6d"
SALEX_SHA256 = "48eb3664d95331e7fd84bfe1f04f5e741600bffcfb1253334c82dae92cebf1ef"
SALEX_RECORD_COUNT = 10447765
WBM_SHA256 = "98d545172c1ea9060f03f40cace6f8173a4ac06f1ee875ccd963765211519b58"
WBM_RECORD_COUNT = 256963


def salex_identity() -> SalexSourceIdentity:
    return SalexSourceIdentity(
        size_bytes=SALEX_SIZE,
        md5=SALEX_MD5,
        sha256=SALEX_SHA256,
    )


def open_salex_source():
    request = urllib.request.Request(
        SALEX_URL,
        headers={"User-Agent": "Rhombus-phase3-overlap/1"},
    )
    return urllib.request.urlopen(request, timeout=120)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()


def run_pilot(max_records: int, output_json: Path) -> None:
    if max_records <= 0:
        raise ValueError("pilot max_records must be positive")
    started = time.monotonic()
    count = 0
    with open_salex_source() as source:
        for _ in iter_salex_membership_records(
            source,
            expected_source_identity=salex_identity(),
            fingerprint=structure_candidate_fingerprint_sha256,
            prototype_group=matbench_prototype_group,
            expected_record_count=SALEX_RECORD_COUNT,
            max_records=max_records,
        ):
            count += 1
    elapsed = time.monotonic() - started
    if count != max_records:
        raise RuntimeError(
            f"pilot stopped early: expected={max_records} observed={count}"
        )
    rate = count / elapsed
    payload = {
        "schema_version": "rhombus-v2-salex-throughput-pilot-v1",
        "mode": "NON_AUTHORITATIVE_THROUGHPUT_PILOT",
        "processed_records": count,
        "elapsed_seconds": elapsed,
        "records_per_second": rate,
        "naive_full_stream_estimate_hours": SALEX_RECORD_COUNT / rate / 3600.0,
        "complete_source_identity_verified": False,
        "production_membership_index_built": False,
        "exposure_claim_authorized": False,
    }
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))


def run_full(
    *,
    wbm_path: Path,
    target_db: Path,
    membership_db: Path,
    overlap_jsonl: Path,
    summary_json: Path,
) -> None:
    observed_wbm_sha = sha256_file(wbm_path)
    if observed_wbm_sha != WBM_SHA256:
        raise RuntimeError(
            f"WBM source SHA256 mismatch: expected={WBM_SHA256} observed={observed_wbm_sha}"
        )

    target_summary = build_wbm_target_index(
        iter_wbm_initial_structure_jsonl(wbm_path),
        target_db,
        source_file_sha256=WBM_SHA256,
    )
    if target_summary.row_count != WBM_RECORD_COUNT:
        target_db.unlink(missing_ok=True)
        raise RuntimeError(
            "WBM target row-count mismatch: "
            f"expected={WBM_RECORD_COUNT} observed={target_summary.row_count}"
        )

    started = time.monotonic()
    with WBMStreamingOverlapAuditor(target_db) as auditor:
        with open_salex_source() as source:
            membership_summary = build_salex_membership_index_with_frozen_protocols(
                source,
                membership_db,
                expected_source_identity=salex_identity(),
                expected_record_count=SALEX_RECORD_COUNT,
                batch_size=5000,
                on_structure=auditor.observe,
            )

        material_rows = auditor.material_records()
        audit_summary = auditor.summary()
        observed_training = auditor.observed_training_structures
        candidate_training = auditor.candidate_training_structures

    if membership_summary.row_count != SALEX_RECORD_COUNT:
        membership_db.unlink(missing_ok=True)
        raise RuntimeError(
            "sAlex production index row-count mismatch: "
            f"expected={SALEX_RECORD_COUNT} observed={membership_summary.row_count}"
        )

    with overlap_jsonl.open("w", encoding="utf-8") as handle:
        for row in material_rows:
            handle.write(json.dumps(asdict(row), sort_keys=True) + "\n")

    result = {
        "schema_version": "rhombus-v2-salex-wbm-production-overlap-v1",
        "mode": "PRODUCTION_COMPLETE_SOURCE_STREAM",
        "wbm_source_sha256": WBM_SHA256,
        "wbm_target_count": target_summary.row_count,
        "salex_source_sha256": SALEX_SHA256,
        "salex_membership_row_count": membership_summary.row_count,
        "salex_observed_training_structures": observed_training,
        "salex_candidate_training_structures": candidate_training,
        "membership_index_sha256": sha256_file(membership_db),
        "target_index_sha256": sha256_file(target_db),
        "overlap_jsonl_sha256": sha256_file(overlap_jsonl),
        "elapsed_seconds": time.monotonic() - started,
        "audit_summary": asdict(audit_summary),
        "full_training_lineage_resolved": False,
        "unseen_generalization_claim_authorized": False,
        "remaining_blocker": "MPTRJ_TRAINING_REPRESENTATION_UNATTESTED",
    }
    summary_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)

    pilot = subparsers.add_parser("pilot")
    pilot.add_argument("--max-records", type=int, default=10000)
    pilot.add_argument("--output-json", required=True)

    full = subparsers.add_parser("full")
    full.add_argument("--wbm-path", required=True)
    full.add_argument("--target-db", required=True)
    full.add_argument("--membership-db", required=True)
    full.add_argument("--overlap-jsonl", required=True)
    full.add_argument("--summary-json", required=True)

    args = parser.parse_args()
    if args.mode == "pilot":
        run_pilot(args.max_records, Path(args.output_json))
        return

    run_full(
        wbm_path=Path(args.wbm_path),
        target_db=Path(args.target_db),
        membership_db=Path(args.membership_db),
        overlap_jsonl=Path(args.overlap_jsonl),
        summary_json=Path(args.summary_json),
    )


if __name__ == "__main__":
    main()
