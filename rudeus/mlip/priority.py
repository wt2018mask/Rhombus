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
from rudeus.mlip.sharding import structure_dict_sha256


POLICY_ID = "parent-conductivity-desc_then-natoms-asc_then-batch-id-v2"


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

        structure_dict = payload.get("structure_dict") or {}
        sites = structure_dict.get("sites")
        if not isinstance(sites, list) or not sites:
            raise ValueError(f"batch missing non-empty structure sites: {batch_id}")

        rows.append({
            "batch_id": batch_id,
            "structure_sha256": structure_sha256,
            "parent_id": parent_id,
            "parent_conductivity_S_per_cm": float(value),
            "n_atoms": len(sites),
            "child_material_id": payload.get("child_material_id"),
            "child_formula": payload.get("child_formula"),
            "p0_state": payload.get("p0_state"),
            "novelty_tag": payload.get("novelty_tag"),
        })

    rows.sort(key=lambda row: (
        -row["parent_conductivity_S_per_cm"],
        row["n_atoms"],
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



def load_execution_priority_audit(
    audit_path: str | Path,
    pending_dir: str | Path,
) -> list[str]:
    """Validate a frozen execution-priority audit against its pending cohort.

    Validation is intentionally fail-closed and CPU-only so it can run before
    any checkpoint download or calculator initialization.  Both batch IDs and
    structure hashes must match exactly; a priority file can schedule work but
    can never redefine the frozen scientific cohort.
    """
    audit_path = Path(audit_path)
    pending_dir = Path(pending_dir)
    report = json.loads(audit_path.read_text(encoding="utf-8"))

    if report.get("policy_id") != POLICY_ID:
        raise ValueError("priority audit policy_id mismatch")
    if report.get("purpose") != "execution_priority_only":
        raise ValueError("priority audit purpose mismatch")
    if report.get("scientific_verdict_changed") is not False:
        raise ValueError("priority audit must not change scientific verdicts")

    ranking = report.get("ranking")
    if not isinstance(ranking, list) or not ranking:
        raise ValueError("priority audit missing non-empty ranking")
    if report.get("n_batches") != len(ranking):
        raise ValueError("priority audit n_batches mismatch")

    expected_ranks = list(range(1, len(ranking) + 1))
    actual_ranks = [row.get("priority_rank") for row in ranking]
    if actual_ranks != expected_ranks:
        raise ValueError("priority audit ranking is malformed")

    priority_pairs = []
    batch_order = []
    for row in ranking:
        batch_id = str(row.get("batch_id", ""))
        structure_sha = str(row.get("structure_sha256", ""))
        if not batch_id or not structure_sha:
            raise ValueError("priority audit row missing batch_id/structure_sha256")
        batch_order.append(batch_id)
        priority_pairs.append((batch_id, structure_sha))
    if len(batch_order) != len(set(batch_order)):
        raise ValueError("priority audit contains duplicate batch IDs")

    pending_pairs = []
    pending_files = sorted(pending_dir.glob("*.json"))
    for path in pending_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        batch_id = str(payload.get("batch_id", ""))
        declared_sha = str(payload.get("structure_sha256", ""))
        structure_dict = payload.get("structure_dict")
        if batch_id != path.stem:
            raise ValueError(f"pending batch_id/filename mismatch: {path.name}")
        if not isinstance(structure_dict, dict):
            raise ValueError(f"pending batch missing structure_dict: {batch_id}")
        computed_sha = structure_dict_sha256(structure_dict)
        if declared_sha != computed_sha:
            raise ValueError(f"pending structure_sha256 mismatch: {batch_id}")
        pending_pairs.append((batch_id, declared_sha))

    if sorted(priority_pairs) != sorted(pending_pairs):
        raise ValueError("priority audit does not exactly match pending cohort")

    cohort_rows = [
        {"batch_id": batch_id, "structure_sha256": structure_sha}
        for batch_id, structure_sha in priority_pairs
    ]
    if report.get("cohort_identity_sha256") != _cohort_identity(cohort_rows):
        raise ValueError("priority audit cohort identity mismatch")

    return batch_order


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
            f"{row['parent_conductivity_S_per_cm']:.12g} "
            f"n_atoms={row['n_atoms']}"
        )


if __name__ == "__main__":
    main()
