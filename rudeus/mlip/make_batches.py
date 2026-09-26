"""Prepare P1 batch files (runs LOCALLY on CPU, committed before any GPU session).

Usage:
    python -m rudeus.mlip.make_batches --smoke20
    python -m rudeus.mlip.make_batches --parent-ids obelix:1e9,obelix:2uv

Only novel + (PLAUSIBLE or geometry-only FAIL) children become batches
(DESIGN.md Q3). Output: data/batches/pending/<batch_id>.json (committed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Optional

import yaml

from rudeus.generation import generate_children, retrieve_obelix_parents
from rudeus.mlip.sharding import make_batch_file


def _apportion(sizes: dict, n_parents: int) -> dict:
    """Largest-remainder split of n_parents over {family: pool_size}."""
    total = sum(sizes.values())
    quotas = {fam: sizes[fam] * n_parents / total for fam in sizes}
    counts = {fam: min(int(quotas[fam]), sizes[fam]) for fam in sizes}
    remainder = n_parents - sum(counts.values())
    for fam in sorted(quotas, key=lambda f: quotas[f] - counts[f], reverse=True):
        if remainder <= 0:
            break
        if counts[fam] < sizes[fam]:
            counts[fam] += 1
            remainder -= 1
    return counts


def proportional_mix(by_fam: dict, n_parents: int,
                     skip: Optional[dict] = None) -> list:
    """Deterministic take mirroring pool proportions (largest remainder).

    `skip` maps family -> already-consumed count for non-overlapping top-up
    runs against the same pools. Same G1/G2 policy — only the parent count
    scales.
    """
    skip = skip or {}
    remaining = {fam: len(v) - skip.get(fam, 0) for fam, v in by_fam.items()}
    counts = _apportion(remaining, n_parents)
    picked = []
    for fam in sorted(by_fam):
        start = skip.get(fam, 0)
        picked += [p.parent_id for p in by_fam[fam][start:start + counts[fam]]]
    return picked


def consumed_by_take(by_fam: dict, n_first: int) -> dict:
    """Per-family counts consumed by proportional_mix(by_fam, n_first)."""
    sizes = {fam: len(v) for fam, v in by_fam.items()}
    counts = _apportion(sizes, n_first)
    return counts


def top_conductivity_parent_ids(parents: list, n_parents: int) -> list:
    """Deterministically select P1-representable parents by conductivity.

    This is an acquisition policy for candidate generation, not a scientific
    transport verdict or threshold. Parents must be perturbable, have an
    ordered structure representable by the current MLIP path, and carry a
    finite published conductivity. Ties are broken by stable parent_id.
    """
    eligible = []
    for parent in parents:
        value = getattr(parent, "conductivity", None)
        structure = getattr(parent, "structure", None)
        if (not getattr(parent, "perturbable", False)
                or structure is None
                or not getattr(structure, "is_ordered", False)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))):
            continue
        eligible.append(parent)
    eligible.sort(key=lambda p: (-float(p.conductivity), str(p.parent_id)))
    return [p.parent_id for p in eligible[:max(0, int(n_parents))]]


def generation_config_hash(gcfg: dict) -> str:
    """Hash of the generation config section (batch provenance)."""
    return hashlib.sha256(
        json.dumps(gcfg, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def p1_eligible(candidate) -> bool:
    """DESIGN.md Q3 rule: novel AND (PLAUSIBLE or geometry-only FAIL)."""
    if candidate.metadata.get("novelty_tag") != "novel":
        return False
    if candidate.existence_state.value == "PLAUSIBLE":
        return True
    rej = candidate.metadata.get("p0_rejection") or {}
    return (candidate.existence_state.value == "FAIL"
            and rej.get("neutrality_ok") is True)


def prepare_batches(config_path: str, parent_ids: list,
                     out_dir: str, audit_out: str = "") -> list:
    """Generate children for the given parents and write eligible batch files.

    When audit_out is given, the full distribution audit over ALL generated
    children (eligible or not) is written there as JSON for pilot diagnosis.
    """
    from rudeus.generation import audit_candidates, audit_parent_selection

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    gcfg = cfg["generation"]
    ckpt_id = cfg["mlip"]["primary_checkpoint"]
    ghash = generation_config_hash(gcfg)

    parents = {p.parent_id: p for p in retrieve_obelix_parents(
        cfg["datasets"]["obelix_repo"])}
    ops = ["displace", "strain", "defect", "substitute"]
    written = []
    all_kids = []
    for i, pid in enumerate(parent_ids):
        parent = parents.get(pid)
        if parent is None or not parent.perturbable:
            print(f"skip {pid}: not retrievable/perturbable")
            continue
        seed = gcfg["random_seed"] + i
        kids = generate_children(
            parent, operators=ops,
            children_per_parent=gcfg["children_per_parent"],
            seed=seed,
            generation_config_hash=ghash,
            allowed_swaps=gcfg["allowed_swaps_provisional"],
            displacement_sigma_A_provisional=gcfg["displacement_sigma_A_provisional"],
            strain_max_fraction_provisional=gcfg["strain_max_fraction_provisional"],
            mobile_ion=gcfg["mobile_ion"],
            defect_modes=tuple(gcfg["defect_modes"]),
            matcher_ltol_provisional=gcfg["matcher"]["ltol_provisional"],
            matcher_stol_provisional=gcfg["matcher"]["stol_provisional"],
            matcher_angle_tol_provisional=gcfg["matcher"]["angle_tol_provisional"],
        )
        all_kids.extend(kids)
        for j, kid in enumerate(kids):
            if not p1_eligible(kid):
                continue
            path = make_batch_file(
                out_dir, parent_id=pid, child_index=j, seed=seed,
                generation_config_hash=ghash, checkpoint_id=ckpt_id,
                structure_dict=kid.structure_dict,
                extra={"child_material_id": kid.material_id,
                       "child_formula": kid.formula,
                       "p0_state": kid.existence_state.value,
                       "novelty_tag": kid.metadata["novelty_tag"]},
            )
            written.append(str(path))
            print(f"batch {path.name}: {kid.material_id} {kid.formula} "
                  f"{kid.existence_state.value}")
    if audit_out:
        from rudeus.generation import format_audit
        report = audit_candidates(all_kids)
        eligible_by_operator = {}
        for kid in all_kids:
            if not p1_eligible(kid):
                continue
            op = str(((kid.metadata.get("operators") or [{}])[0]).get(
                "operator", "unknown"
            ))
            eligible_by_operator[op] = eligible_by_operator.get(op, 0) + 1
        report["p1_eligibility"] = {
            "rule": "novel AND (PLAUSIBLE or geometry-only FAIL)",
            "n_eligible": sum(eligible_by_operator.values()),
            "by_operator": dict(sorted(eligible_by_operator.items())),
        }
        report["parent_selection"] = audit_parent_selection(
            list(parents.values()), parent_ids
        )
        Path(audit_out).parent.mkdir(parents=True, exist_ok=True)
        with open(audit_out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, sort_keys=True)
        print(format_audit(report))
        parent_audit = report["parent_selection"]
        print(
            "parent selection: "
            f"{parent_audit['n_selected_parents']}/"
            f"{parent_audit['n_perturbable_parents']} perturbable; "
            f"published conductivity known for "
            f"{parent_audit['n_with_published_conductivity']}"
        )
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare P1 batch files.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--parent-ids", default="",
                        help="comma-separated parent IDs")
    parser.add_argument("--smoke20", action="store_true",
                        help="first 8 oxide + 8 sulfide + 4 halide CIF parents")
    parser.add_argument("--n-parents", type=int, default=0,
                        help="proportional deterministic mix of N parents")
    parser.add_argument("--top-conductivity", type=int, default=0,
                        help="top N perturbable parents by published ionic conductivity")
    parser.add_argument("--continue-from", type=int, default=0,
                        help="skip parents consumed by a previous --n-parents N take")
    parser.add_argument("--out", default="data/batches/pending")
    parser.add_argument("--audit-out", default="",
                        help="write full distribution audit JSON here (all children)")
    args = parser.parse_args()

    if args.top_conductivity:
        if args.n_parents or args.smoke20 or args.parent_ids or args.continue_from:
            print("--top-conductivity cannot be combined with other parent-selection modes",
                  file=sys.stderr)
            sys.exit(2)
        parents = retrieve_obelix_parents(
            yaml.safe_load(open(args.config, encoding="utf-8"))
            ["datasets"]["obelix_repo"])
        parent_ids = top_conductivity_parent_ids(parents, args.top_conductivity)
    elif args.n_parents:
        parents = retrieve_obelix_parents(
            yaml.safe_load(open(args.config, encoding="utf-8"))
            ["datasets"]["obelix_repo"])
        by_fam = {}
        for p in parents:
            if p.perturbable:
                by_fam.setdefault(p.chemical_family, []).append(p)
        skip = consumed_by_take(by_fam, args.continue_from) if args.continue_from else None
        parent_ids = proportional_mix(by_fam, args.n_parents, skip=skip)
    elif args.smoke20:
        parents = retrieve_obelix_parents(
            yaml.safe_load(open(args.config, encoding="utf-8"))
            ["datasets"]["obelix_repo"])
        by_fam = {}
        for p in parents:
            if p.perturbable:
                by_fam.setdefault(p.chemical_family, []).append(p)
        parent_ids = ([p.parent_id for p in by_fam.get("oxide", [])[:8]]
                      + [p.parent_id for p in by_fam.get("sulfide", [])[:8]]
                      + [p.parent_id for p in by_fam.get("halide", [])[:4]])
    else:
        parent_ids = [s for s in args.parent_ids.split(",") if s]
    if not parent_ids:
        print("no parents selected", file=sys.stderr)
        sys.exit(1)
    written = prepare_batches(args.config, parent_ids, args.out,
                              audit_out=args.audit_out)
    print(f"wrote {len(written)} batch files to {args.out}")


if __name__ == "__main__":
    main()
