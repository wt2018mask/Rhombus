"""Deterministic execution priority for frozen P1 candidate cohorts.

This module orders already-admitted P1 batches for efficient GPU execution.
It does NOT change G/P0/P1 scientific eligibility or any downstream verdict.
Published parent conductivity is acquisition/scheduling evidence only, never a
claim that a child is diffusive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence

import yaml

from rudeus.generation import retrieve_obelix_parents


POLICY_ID = "parent-conductivity-desc_then-batch-id-v1"


def _cohort_identity(rows: Sequence[Dict[str, Any]]) -> str:
    """Hash frozen batch identity + structure identity, independent of order."""
    bound = [
        {
            "batch_id": str(row["batch_id"]),
            "structure_sha256": str(row["structure_sha256"]),
        }
        for row in rows
    ]
    bound.sort(key=lambda x: x["batch_id"])
    payload = json.dumps(bound, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def rank_p1_payloads(
    payloads: Iterable[Mapping[str, Any]],
    parents: Iterable[Any],
) -> Dict[str, Any]:
    """Rank an already-frozen P1 cohort by parent conductivity.

    Preconditions are fail-closed: every batch must resolve to a perturbable,
    ordered parent with finite published conductivity. The function does not
    filter batches; a broken provenance link raises instead of silently
    changing the cohort.
    """
    parent_map = {str(p.parent_id): p for p in parents}
    rows = []

    for payload in payloads:
        batch_id = str(payload.get("batch_id", ""))
        parent_id = str(payload.get("parent_id", ""))
        structure_sha256 = str(payload.get("structure_sha256", ""))
        if not batch_id or not parent_id or not structure_sha256:
            raise ValueError("batch missing batch_id/parent_id/structure_sha256")

        parent = parent_map.get(parent_id)
        if parent is None:
            raise ValueError(f"unresolved parent for batch {batch_id}: {parent_id}")
        value = getattr(parent, "conductivity", None)
        structure = getattr(parent, "structure", None)
        if not getattr(parent, "perturbable", False):
            raise ValueError(f"non-perturbable parent in frozen cohort: {parent_id}")
        if structure is None or not getattr(structure, "is_ordered", False):
            raise ValueError(f"unordered parent in frozen cohort: {parent_id}")
        if (not isinstance(value, (int, float))
                or not math.isfinite(float(value))):
            raise ValueError(f"missing/non-finite conductivity: {parent_id}")

        rows.append({
            "batch_id": batch_id,
            "structure_sha256": structure_sha256,
            "parent_id": parent_id,
            "parent_conductivity_S_per_cm": float(value),
            "child_material_id": payload.get("child_material_id"),
            "child_formula": payload.get("child_formula"),
            "p0_state": payload.get("p0_state"),
            "novelty_tag": payload.get("novelty_tag"),
        })

    rows.sort(key=lambda row: (
        -row["parent_conductivity_S_per_cm"],
        row["batch_id"],
    ))
    for index, row in enumerate(rows, start=1):
        row["priority_rank"] = index

    return {
        "policy_id": POLICY_ID,
        "purpose": "execution_priority_only",
        "scientific_verdict_changed": False,
        "conductivity_interpretation": (
            "published parent acquisition evidence; not child diffusion evidence"
        ),
        "n_batches": len(rows),
        "cohort_identity_sha256": _cohort_identity(rows),
        "ranking": rows,
    }


def build_priority_audit(
    pending_dir: str | Path,
    parents: Iterable[Any],
) -> Dict[str, Any]:
    pending = Path(pending_dir)
    files = sorted(pending.glob("*.json"))
    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in files
    ]
    report = rank_p1_payloads(payloads, parents)
    report["pending_dir"] = str(pending).replace("\\", "/")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze deterministic execution priority for a P1 cohort.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--pending", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    parents = retrieve_obelix_parents(cfg["datasets"]["obelix_repo"])
    report = build_priority_audit(args.pending, parents)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"policy: {report['policy_id']}")
    print(f"cohort identity: {report['cohort_identity_sha256']}")
    print(f"ranked batches: {report['n_batches']}")
    for row in report["ranking"]:
        print(
            f"{row['priority_rank']:02d} {row['batch_id']} "
            f"{row['parent_id']} "
            f"{row['parent_conductivity_S_per_cm']:.12g}"
        )


if __name__ == "__main__":
    main()
