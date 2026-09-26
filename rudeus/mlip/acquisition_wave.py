"""Deterministic acquisition-wave selection for expanded P1 cohorts.

Wave 1 maximizes parent diversity: at most one eligible child per parent.
Remaining children become later waves. This is execution scheduling only and
does not change any scientific eligibility or verdict.
"""

from __future__ import annotations

import argparse
import hashlib
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
        bindings = [
            {
                "batch_id": str(r["batch_id"]),
                "structure_sha256": str(r.get("structure_sha256", "")),
            }
            for r in items
        ]
        if any(not b["structure_sha256"] for b in bindings):
            raise ValueError("batch missing structure_sha256")
        cohort_payload = json.dumps(
            sorted(bindings, key=lambda x: x["batch_id"]),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
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
            "bindings": bindings,
            "cohort_identity_sha256": hashlib.sha256(cohort_payload).hexdigest(),
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


def materialize_wave(
    pending_dir: str | Path,
    manifest: Dict[str, Any],
    out_dir: str | Path,
    wave_key: str = "wave1",
) -> List[str]:
    """Materialize an exact frozen wave, preserving source batch bytes.

    The manifest binds both batch IDs and structure hashes. Existing identical
    files are accepted; conflicting files are refused.
    """
    pending = Path(pending_dir)
    out = Path(out_dir)
    wave = manifest.get(wave_key)
    if not isinstance(wave, dict):
        raise ValueError(f"manifest missing {wave_key}")
    bindings = wave.get("bindings")
    if not isinstance(bindings, list) or not bindings:
        raise ValueError(f"{wave_key} missing non-empty bindings")

    expected = {
        str(row.get("batch_id", "")): str(row.get("structure_sha256", ""))
        for row in bindings
    }
    if len(expected) != len(bindings) or any(not k or not v for k, v in expected.items()):
        raise ValueError(f"{wave_key} bindings malformed")

    out.mkdir(parents=True, exist_ok=True)
    written = []
    for batch_id in wave.get("batch_ids", []):
        batch_id = str(batch_id)
        if batch_id not in expected:
            raise ValueError(f"{wave_key} batch_ids/bindings mismatch: {batch_id}")
        src = pending / f"{batch_id}.json"
        if not src.exists():
            raise ValueError(f"missing source batch: {batch_id}")
        payload = json.loads(src.read_text(encoding="utf-8"))
        if str(payload.get("batch_id", "")) != batch_id:
            raise ValueError(f"source batch_id mismatch: {batch_id}")
        if str(payload.get("structure_sha256", "")) != expected[batch_id]:
            raise ValueError(f"source structure_sha256 mismatch: {batch_id}")
        dst = out / src.name
        source_bytes = src.read_bytes()
        if dst.exists():
            if dst.read_bytes() != source_bytes:
                raise ValueError(f"refusing conflicting existing batch: {batch_id}")
        else:
            dst.write_bytes(source_bytes)
        written.append(str(dst))

    actual_ids = sorted(p.stem for p in out.glob("*.json"))
    if actual_ids != sorted(expected):
        raise ValueError("materialized directory does not exactly match frozen wave")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build parent-diverse P1 execution waves.")
    parser.add_argument("--pending", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--materialize-dir", default="",
                        help="optional exact frozen wave1 pending directory")
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
    print(f"wave1 cohort identity: {report['wave1']['cohort_identity_sha256']}")
    if args.materialize_dir:
        files = materialize_wave(
            args.pending, report, args.materialize_dir, wave_key="wave1")
        print(f"materialized wave1: {len(files)} files -> {args.materialize_dir}")


if __name__ == "__main__":
    main()
