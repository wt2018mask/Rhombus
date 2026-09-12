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
import sys
from pathlib import Path

import yaml

from rudeus.generation import generate_children, retrieve_obelix_parents
from rudeus.mlip.sharding import make_batch_file


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
                    out_dir: str) -> list:
    """Generate children for the given parents and write eligible batch files."""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    gcfg = cfg["generation"]
    ckpt_id = cfg["mlip"]["primary_checkpoint"]
    ghash = generation_config_hash(gcfg)

    parents = {p.parent_id: p for p in retrieve_obelix_parents(
        cfg["datasets"]["obelix_repo"])}
    ops = ["displace", "strain", "defect", "substitute"]
    written = []
    for i, pid in enumerate(parent_ids):
        parent = parents.get(pid)
        if parent is None or not parent.perturbable:
            print(f"skip {pid}: not retrievable/perturbable")
            continue
        kids = generate_children(
            parent, operators=ops,
            children_per_parent=gcfg["children_per_parent"],
            seed=gcfg["random_seed"] + i,
            allowed_swaps=gcfg["allowed_swaps_provisional"],
            displacement_sigma_A_provisional=gcfg["displacement_sigma_A_provisional"],
            strain_max_fraction_provisional=gcfg["strain_max_fraction_provisional"],
            mobile_ion=gcfg["mobile_ion"],
            defect_modes=tuple(gcfg["defect_modes"]),
            matcher_ltol_provisional=gcfg["matcher"]["ltol_provisional"],
            matcher_stol_provisional=gcfg["matcher"]["stol_provisional"],
            matcher_angle_tol_provisional=gcfg["matcher"]["angle_tol_provisional"],
        )
        for j, kid in enumerate(kids):
            if not p1_eligible(kid):
                continue
            path = make_batch_file(
                out_dir, parent_id=pid, child_index=j,
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
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare P1 batch files.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--parent-ids", default="",
                        help="comma-separated parent IDs")
    parser.add_argument("--smoke20", action="store_true",
                        help="first 8 oxide + 8 sulfide + 4 halide CIF parents")
    parser.add_argument("--out", default="data/batches/pending")
    args = parser.parse_args()

    if args.smoke20:
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
    written = prepare_batches(args.config, parent_ids, args.out)
    print(f"wrote {len(written)} batch files to {args.out}")


if __name__ == "__main__":
    main()
