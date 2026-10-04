"""Candidate distribution audit for generation pilots (diagnosis, not balancing).

Consumes generated children (CandidateMaterial list) and reports operator,
parent, chemistry/family, P0, and novelty distributions as plain JSON-able
dicts. Uses only existing schema fields and the existing
classify_chemical_family classifier. No quotas, no rebalancing, no threshold
changes — a skewed histogram is reported as-is.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any, Dict, List, Sequence

from rudeus.empirical.obelix import classify_chemical_family


def _p0_rejection_key(candidate) -> str:
    """Compact rejection class from the recorded P0 rejection dict."""
    rej = candidate.metadata.get("p0_rejection") or {}
    if not rej:
        return "none"
    neut_ok = rej.get("neutrality_ok", True)
    paul_ok = candidate.metadata.get("p0_details", {}).get("pauling_ok", True)
    geom_ok = rej.get("geometry_ok", True)
    fails = []
    if neut_ok is False:
        fails.append("neutrality")
    if paul_ok is False:
        fails.append("pauling")
    if geom_ok is False:
        fails.append("geometry")
    return "+".join(fails) if fails else "none"


def _novelty_key(candidate) -> str:
    """Novelty class from existing tags: novel / rediscovery-* / matcher-error."""
    tag = candidate.metadata.get("novelty_tag", "unknown")
    if tag == "rediscovery":
        return f"rediscovery-{candidate.metadata.get('novelty_matched', 'unknown')}"
    if tag == "novel" and candidate.metadata.get("matcher_note"):
        return "novel-matcher-error"
    return str(tag)


def audit_candidates(children: List) -> Dict[str, Any]:
    """Distribution audit over generated children (JSON-serializable)."""
    operators = Counter()
    families_g = Counter()
    parents = Counter()
    parent_families = Counter()
    child_families = Counter()
    p0 = Counter()
    rejection_reasons = Counter()
    novelty = Counter()
    operator_errors = 0

    for kid in children:
        meta = kid.metadata
        op_params = (meta.get("operators") or [{}])[0]
        op_name = str(op_params.get("operator", "unknown"))
        operators[op_name] += 1
        families_g[str(meta.get("family", "unknown"))] += 1
        if meta.get("operator_error"):
            operator_errors += 1
        pid = str(meta.get("parent_id", "unknown"))
        parents[pid] += 1
        try:
            parent_families[classify_chemical_family(
                str(meta.get("parent_composition", "")))] += 1
        except Exception:
            parent_families["unknown"] += 1
        try:
            child_families[classify_chemical_family(str(kid.formula))] += 1
        except Exception:
            child_families["unknown"] += 1
        if meta.get("p0_passed") is True:
            p0["passed"] += 1
        else:
            p0["rejected"] += 1
            rejection_reasons[_p0_rejection_key(kid)] += 1
        novelty[_novelty_key(kid)] += 1

    return {
        "total": len(children),
        "g1_g2": dict(families_g),
        "operators": dict(operators),
        "operator_errors": operator_errors,
        "unique_parents": len(parents),
        "per_parent": dict(parents),
        "parent_families": dict(parent_families),
        "child_families": dict(child_families),
        "p0": dict(p0),
        "p0_rejection_reasons": dict(rejection_reasons),
        "novelty": dict(novelty),
    }


def format_audit(report: Dict[str, Any]) -> str:
    """One-line-per-section human rendering of an audit report."""
    lines = [f"total candidates: {report['total']}"]
    lines.append(f"G1/G2: {json.dumps(report['g1_g2'], sort_keys=True)}")
    lines.append(f"operators: {json.dumps(report['operators'], sort_keys=True)} "
                 f"(errors: {report['operator_errors']})")
    lines.append(f"unique parents: {report['unique_parents']}")
    lines.append(f"parent families: {json.dumps(report['parent_families'], sort_keys=True)}")
    lines.append(f"child families: {json.dumps(report['child_families'], sort_keys=True)}")
    lines.append(f"P0: {json.dumps(report['p0'], sort_keys=True)} "
                 f"reasons: {json.dumps(report['p0_rejection_reasons'], sort_keys=True)}")
    lines.append(f"novelty: {json.dumps(report['novelty'], sort_keys=True)}")
    return "\n".join(lines)


def audit_parent_selection(parents: Sequence, selected_parent_ids: Sequence[str],
                           top_unselected: int = 10) -> Dict[str, Any]:
    """Describe how a parent selection samples the available transport evidence.

    This is diagnostic only.  It does not rank, filter, rebalance, or alter the
    selected parent IDs.  Published ionic conductivity is treated as provenance
    supplied by the source dataset, not as a calibrated discovery threshold.
    """
    selected = set(str(x) for x in selected_parent_ids)
    rows = []
    for parent in parents:
        if not getattr(parent, "perturbable", False):
            continue
        value = getattr(parent, "conductivity", None)
        finite = isinstance(value, (int, float)) and math.isfinite(float(value))
        structure = getattr(parent, "structure", None)
        ordered = bool(structure is not None and getattr(structure, "is_ordered", False))
        rows.append({
            "parent_id": str(parent.parent_id),
            "chemical_family": str(parent.chemical_family),
            "conductivity_S_per_cm": float(value) if finite else None,
            "ordered": ordered,
            "selected": str(parent.parent_id) in selected,
        })

    known = [row for row in rows if row["conductivity_S_per_cm"] is not None]
    ordered_known = [row for row in known if row["ordered"]]
    selected_known = [row for row in known if row["selected"]]
    unselected_known = [row for row in known if not row["selected"]]

    def summary(group):
        values = sorted(row["conductivity_S_per_cm"] for row in group)
        if not values:
            return {"n": 0, "min": None, "median": None, "max": None}
        n = len(values)
        mid = n // 2
        median = values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2.0
        return {
            "n": n,
            "min": float(values[0]),
            "median": float(median),
            "max": float(values[-1]),
        }

    top = sorted(
        unselected_known,
        key=lambda row: (-row["conductivity_S_per_cm"], row["parent_id"]),
    )[:max(0, int(top_unselected))]

    return {
        "diagnostic_only": True,
        "selection_policy_changed": False,
        "n_perturbable_parents": len(rows),
        "n_ordered_parents": sum(row["ordered"] for row in rows),
        "n_selected_parents": sum(row["selected"] for row in rows),
        "n_with_published_conductivity": len(known),
        "n_ordered_with_published_conductivity": len(ordered_known),
        "selected_conductivity": summary(selected_known),
        "unselected_conductivity": summary(unselected_known),
        "top_unselected_by_published_conductivity": top,
    }
