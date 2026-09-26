"""Deterministic acquisition-wave selection for expanded P1 cohorts.

Wave 1 maximizes parent diversity: at most one eligible child per parent.
Remaining children become later waves. This is execution scheduling only and
does not change any scientific eligibility or verdict.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _candidate_key(row: Dict[str, Any], operator_counts: Counter) -> tuple:
    """Prefer globally rarer operators within a parent, then stable batch_id."""
    op = str(row.get("generation_operator", "unknown"))
    return (operator_counts[op], op, str(row["batch_id"]))


def select_parent_diverse_wave(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = list(rows)
    if not rows:
        raise ValueError("empty P1 cohort")

    seen_ids = set()
    by_parent: Dict[str, List[Dict[str, Any]]] = {}
    operator_counts = Counter()

    for row in rows:
        batch_id = str(row.get("batch_id", ""))
        parent_id = str(row.get("parent_id", ""))
        if not batch_id or not parent_id:
            raise ValueError("batch missing batch_id/parent_id")
        if batch_id in seen_ids:
            raise ValueError(f"duplicate batch_id: {batch_id}")
        seen_ids.add(batch_id)
        by_parent.setdefault(parent_id, []).append(row)
        operator_counts[str(row.get("generation_operator", "unknown"))] += 1

    selected = []
    deferred = []
    for parent_id in sorted(by_parent):
        candidates = sorted(
            by_parent[parent_id],
            key=lambda row: _candidate_key(row, operator_counts),
        )
        selected.append(candidates[0])
        deferred.extend(candidates[1:])

    # Order wave execution to surface underrepresented families/operators early.
    family_counts = Counter(str(r.get("parent_chemical_family", "unknown")) for r in selected)
    selected.sort(key=lambda r: (
        family_counts[str(r.get("parent_chemical_family", "unknown"))],
        operator_counts[str(r.get("generation_operator", "unknown"))],
        str(r.get("parent_chemical_family", "unknown")),
        str(r.get("generation_operator", "unknown")),
        str(r["batch_id"]),
    ))
    deferred.sort(key=lambda r: str(r["batch_id"]))

    def summarize(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "n_batches": len(items),
            "n_unique_parents": len({str(r["parent_id"]) for r in items}),
            "by_operator": dict(sorted(Counter(
                str(r.get("generation_operator", "unknown")) for r in items
            ).items())),
            "by_parent_family": dict(sorted(Counter(
                str(r.get("parent_chemical_family", "unknown")) for r in items
            ).items())),
            "batch_ids": [str(r["batch_id"]) for r in items],
        }

    return {
        "policy_id": "one-child-per-parent-first-v1",
        "purpose": "execution_scheduling_only",
        "scientific_verdict_changed": False,
        "wave1": summarize(selected),
        "deferred": summarize(deferred),
    }


def load_rows(pending_dir: str | Path) -> List[Dict[str, Any]]:
    pending = Path(pending_dir)
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(pending.glob("*.json"))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build parent-diverse P1 execution waves.")
    parser.add_argument("--pending", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    report = select_parent_diverse_wave(load_rows(args.pending))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"policy: {report['policy_id']}")
    print(f"wave1: {report['wave1']['n_batches']} batches / "
          f"{report['wave1']['n_unique_parents']} parents")
    print(f"wave1 operators: {report['wave1']['by_operator']}")
    print(f"wave1 families: {report['wave1']['by_parent_family']}")
    print(f"deferred: {report['deferred']['n_batches']} batches")


if __name__ == "__main__":
    main()
