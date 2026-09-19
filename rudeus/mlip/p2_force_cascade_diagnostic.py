"""Diagnostic-only P2 force-cascade trace.

Extends the existing P2 initialization path with bounded early-step force and
minimum-distance diagnostics. This module does not alter P2 protocol, thresholds,
verdicts, or production artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


def _minimum_pair(positions: np.ndarray, cell: np.ndarray, species: list[str]) -> Dict[str, Any]:
    n = len(positions)
    if n < 2:
        return {"distance_A": None, "i": None, "j": None}
    inv = np.linalg.inv(np.asarray(cell, dtype=float))
    frac = np.asarray(positions, dtype=float) @ inv
    dfrac = frac[:, None, :] - frac[None, :, :]
    dfrac -= np.round(dfrac)
    dcart = dfrac @ np.asarray(cell, dtype=float)
    dist = np.sqrt((dcart ** 2).sum(axis=2))
    dist[np.diag_indices(n)] = np.inf
    i, j = np.unravel_index(int(np.argmin(dist)), dist.shape)
    return {
        "distance_A": float(dist[i, j]),
        "i": int(i),
        "j": int(j),
        "species_i": species[i],
        "species_j": species[j],
    }


def _mic_pair_distance(positions: np.ndarray, cell: np.ndarray, i: int, j: int) -> float:
    inv = np.linalg.inv(np.asarray(cell, dtype=float))
    frac = np.asarray(positions, dtype=float) @ inv
    dfrac = frac[int(i)] - frac[int(j)]
    dfrac -= np.round(dfrac)
    dcart = dfrac @ np.asarray(cell, dtype=float)
    return float(np.linalg.norm(dcart))


def _top_forces(positions: np.ndarray, forces: np.ndarray, species: list[str], k: int = 8) -> list[Dict[str, Any]]:
    fmag = np.sqrt((np.asarray(forces, dtype=float) ** 2).sum(axis=1))
    order = np.argsort(-fmag)[: min(k, len(fmag))]
    return [
        {
            "index": int(i),
            "species": species[int(i)],
            "force_eV_A": float(fmag[int(i)]),
            "position_A": np.asarray(positions[int(i)], dtype=float).tolist(),
        }
        for i in order
    ]


def run_force_cascade_diagnostic(
    *,
    candidate: Dict[str, Any],
    calc: Any,
    protocol: Dict[str, Any],
    seed: int,
    batch_id: str,
    steps: int = 10,
    trace_steps: Optional[list[int]] = None,
    top_k_forces: int = 8,
    output_dir: str | Path = "data/batches/audit/p2_force_cascade_diagnostic",
    target_atoms: Optional[list[int]] = None,
    target_pairs: Optional[list[tuple[int, int]]] = None,
) -> Dict[str, Any]:
    from ase.md.langevin import Langevin
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    if steps < 0:
        raise ValueError("steps must be >= 0")

    structure = Structure.from_dict(candidate["structure_dict"])
    atoms = AseAtomsAdaptor.get_atoms(structure)
    atoms.calc = calc
    species = [str(s.specie) for s in structure]
    cell = np.asarray(atoms.get_cell(), dtype=float)

    temperature = float(protocol["temperature_K"])
    timestep_fs = float(protocol["timestep_fs"])
    friction = float(protocol["friction_fs_inv_provisional"])
    fixcm = bool(protocol["fix_center_of_mass"])

    rng_init = np.random.default_rng(int(seed) + 1)
    rng_dyn = np.random.default_rng(int(seed) + 2)
    MaxwellBoltzmannDistribution(atoms, temperature_K=temperature, rng=rng_init)
    dyn = Langevin(
        atoms, timestep=timestep_fs, temperature_K=temperature,
        friction=friction, fixcm=fixcm, rng=rng_dyn,
    )

    trace = sorted(set([0, 1, 2, 3, 4, 5, 10] if trace_steps is None else trace_steps))
    target_atoms = [0, 14, 20, 32, 50, 85, 108, 117] if target_atoms is None else [int(i) for i in target_atoms]
    target_pairs = [(20, 117), (50, 117), (32, 108), (14, 85)] if target_pairs is None else [(int(i), int(j)) for i, j in target_pairs]
    target_atoms = [i for i in target_atoms if 0 <= i < len(atoms)]
    target_pairs = [(i, j) for i, j in target_pairs if 0 <= i < len(atoms) and 0 <= j < len(atoms) and i != j]
    trace = [s for s in trace if 0 <= s <= steps]

    def frame(step: int) -> Dict[str, Any]:
        pos = np.asarray(atoms.get_positions(), dtype=float)
        vel = np.asarray(atoms.get_velocities(), dtype=float)
        forces = np.asarray(atoms.get_forces(), dtype=float)
        speed = np.sqrt((vel ** 2).sum(axis=1))
        fmag = np.sqrt((forces ** 2).sum(axis=1))
        target_atom_records = []
        for i in target_atoms:
            target_atom_records.append({
                "index": int(i),
                "species": species[i],
                "position_A": pos[i].tolist(),
                "velocity_A_fs": vel[i].tolist(),
                "speed_A_fs": float(speed[i]),
                "force_vector_eV_A": forces[i].tolist(),
                "force_eV_A": float(fmag[i]),
            })

        target_pair_records = []
        for i, j in target_pairs:
            target_pair_records.append({
                "i": int(i),
                "j": int(j),
                "species_i": species[i],
                "species_j": species[j],
                "distance_A": _mic_pair_distance(pos, cell, i, j),
            })

        return {
            "step": int(step),
            "temperature_K": float(atoms.get_temperature()),
            "kinetic_energy_eV": float(atoms.get_kinetic_energy()),
            "potential_energy_eV": float(atoms.get_potential_energy()),
            "total_energy_eV": float(atoms.get_kinetic_energy() + atoms.get_potential_energy()),
            "max_speed_A_fs": float(speed.max()) if len(speed) else 0.0,
            "max_speed_atom_index": int(speed.argmax()) if len(speed) else None,
            "max_force_eV_A": float(fmag.max()) if len(fmag) else 0.0,
            "max_force_atom_index": int(fmag.argmax()) if len(fmag) else None,
            "top_force_atoms": _top_forces(pos, forces, species, k=top_k_forces),
            "minimum_pair": _minimum_pair(pos, cell, species),
            "target_atoms": target_atom_records,
            "target_pairs": target_pair_records,
        }

    snapshots: Dict[int, Dict[str, Any]] = {0: frame(0)}

    def observer() -> None:
        step = int(dyn.nsteps)
        if step in trace:
            snapshots[step] = frame(step)

    dyn.attach(observer, interval=1)
    if steps:
        dyn.run(int(steps))
    if int(dyn.nsteps) in trace and int(dyn.nsteps) not in snapshots:
        snapshots[int(dyn.nsteps)] = frame(int(dyn.nsteps))

    result = {
        "diagnostic": "p2_force_cascade_early_steps",
        "diagnostic_version": "p2-force-cascade-v2-targeted",
        "batch_id": batch_id,
        "child_material_id": candidate.get("child_material_id"),
        "parent_id": candidate.get("parent_id"),
        "natoms": len(atoms),
        "seed": int(seed),
        "initialization": {
            "temperature_K": temperature,
            "timestep_fs": timestep_fs,
            "friction_fs_inv": friction,
            "fix_center_of_mass": fixcm,
            "init_rng_seed": int(seed) + 1,
            "dynamics_rng_seed": int(seed) + 2,
        },
        "steps_requested": int(steps),
        "steps_completed": int(dyn.nsteps),
        "trace_steps": trace,
        "top_k_forces": int(top_k_forces),
        "target_atoms": target_atoms,
        "target_pairs": [list(pair) for pair in target_pairs],
        "snapshots": [snapshots[s] for s in sorted(snapshots)],
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{batch_id}.json"
    tmp = out_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(out_file)
    result["record_file"] = out_file.as_posix()
    return result


def main() -> None:
    import argparse
    import yaml
    from rudeus.mlip.gpu_diagnostic import resolve_device, resolve_diagnostic_candidate
    from rudeus.mlip.p2 import P2_PROTOCOL_DEFAULTS, batch_seed, load_authorization_manifest, protocol_config_hash
    from rudeus.mlip.relax import default_model_path, ensure_checkpoint, load_calculator

    parser = argparse.ArgumentParser(description="Diagnostic-only P2 force-cascade and minimum-distance trace.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--p1-done", default="data/batches/done")
    parser.add_argument("--authorized-manifest", default="data/batches/audit/p2_production_authorized_44_adaptive.json")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--worker", default="p2-force-cascade-diagnostic")
    parser.add_argument("--out", default="data/batches/audit/p2_force_cascade_diagnostic")
    parser.add_argument("--trace-steps", default="0,1,2,3,4,5,10")
    parser.add_argument("--target-atoms", default="0,14,20,32,50,85,108,117")
    parser.add_argument("--target-pairs", default="20:117,50:117,32:108,14:85")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update(cfg.get("p2", {}))
    protocol["_protocol_hash"] = protocol_config_hash(protocol)

    allowlist = load_authorization_manifest(args.authorized_manifest)
    if args.batch_id not in allowlist:
        raise SystemExit(f"STOP: batch {args.batch_id} is not authorized by {args.authorized_manifest}")

    device = resolve_device(args.device)
    candidate = resolve_diagnostic_candidate(args.p1_done, args.batch_id)

    mcfg = cfg["mlip"]
    model_path = ensure_checkpoint(mcfg["checkpoint_url"], default_model_path(), mcfg["checkpoint_sha256"])
    calc = load_calculator(model_path, device=device, dtype=cfg.get("p2", {}).get("dtype", "float32"))
    seed = batch_seed(int(protocol.get("base_seed", 550)), args.batch_id)

    trace_steps = [int(x) for x in args.trace_steps.split(",") if x.strip()]
    target_atoms = [int(x) for x in args.target_atoms.split(",") if x.strip()]
    target_pairs = []
    for item in args.target_pairs.split(","):
        i, j = item.split(":")
        target_pairs.append((int(i), int(j)))

    payload = run_force_cascade_diagnostic(
        candidate=candidate, calc=calc, protocol=protocol, seed=seed,
        batch_id=args.batch_id, steps=args.steps, trace_steps=trace_steps,
        output_dir=args.out, target_atoms=target_atoms, target_pairs=target_pairs,
    )
    payload["device"] = device
    payload["checkpoint_id"] = mcfg["primary_checkpoint"]
    payload["checkpoint_sha256"] = mcfg["checkpoint_sha256"]
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
