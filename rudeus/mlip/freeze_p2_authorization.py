"""Freeze an exact P2 authorization manifest from P1 KEEP_FOR_P2 results."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def build_p2_authorization(p1_done_dir: str | Path) -> dict:
    p1_done_dir = Path(p1_done_dir)
    candidates = []

    for path in sorted(p1_done_dir.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        result = rec.get("result") or {}

        if result.get("p1_verdict") != "KEEP_FOR_P2":
            continue
        if rec.get("p0_state") != "PLAUSIBLE":
            continue

        batch_id = str(rec.get("batch_id", ""))
        relaxed_sha = str(result.get("relaxed_structure_sha256", ""))
        relaxed = result.get("relaxed_structure_dict")

        if batch_id != path.stem or not batch_id:
            raise ValueError(f"batch_id/filename mismatch: {path.name}")
        if not relaxed_sha or not isinstance(relaxed, dict):
            raise ValueError(f"KEEP_FOR_P2 missing relaxed structure binding: {batch_id}")

        candidates.append({
            "batch_id": batch_id,
            "parent_id": rec.get("parent_id"),
            "child_material_id": rec.get("child_material_id"),
            "generation_operator": rec.get("generation_operator"),
            "parent_chemical_family": rec.get("parent_chemical_family"),
            "p0_state": rec.get("p0_state"),
            "p1_verdict": result.get("p1_verdict"),
            "relaxed_structure_sha256": relaxed_sha,
        })

    if not candidates:
        raise ValueError("no P2-eligible P1 records")

    bound = [
        {
            "batch_id": row["batch_id"],
            "relaxed_structure_sha256": row["relaxed_structure_sha256"],
        }
        for row in candidates
    ]
    payload = json.dumps(bound, sort_keys=True, separators=(",", ":"))
    identity = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return {
        "manifest_version": "p2-production-auth/ordered-expansion-wave1-v1",
        "purpose": "P2 execution authorization only",
        "scientific_verdict_changed": False,
        "expected_authorized": len(candidates),
        "verified_eligible": len(candidates),
        "cohort_identity_sha256": identity,
        "candidates": candidates,
        "decision": {
            "verified_eligible": len(candidates),
            "expected": len(candidates),
            "verdict": "AUTHORIZED",
            "md_executions": 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze exact P2 authorization.")
    parser.add_argument("--p1-done", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = build_p2_authorization(args.p1_done)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"authorized: {report['expected_authorized']}")
    print(f"cohort identity: {report['cohort_identity_sha256']}")


if __name__ == "__main__":
    main()
