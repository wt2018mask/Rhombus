"""Diagnostic-only P2 initialization/early-step trace.

This module reproduces the existing P2 initialization path exactly:
MaxwellBoltzmannDistribution at the configured target temperature followed by
ASE Langevin with the existing timestep, friction, COM setting, and deterministic
per-batch RNG seeds. It records step 0 and selected early MD steps only.

No P2 verdicts are produced and no production result/trajectory is written.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


def run_initialization_diagnostic(
    *,
    candidate: Dict[str, Any],
    calc: Any,
    protocol: Dict[str, Any],
    seed: int,
    batch_id: str,
    steps: int = 10,
    trace_steps: Optional[list[int]] = None,
    output_dir: str | Path = "data/batches/audit/p2_initialization_diagnostic",
) -> Dict[str, Any]:
    """Trace P2 initialization and the first bounded MD steps."""
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

    temperature = float(protocol["temperature_K"])
    timestep_fs = float(protocol["timestep_fs"])
    friction = float(protocol["friction_fs_inv_provisional"])
    fixcm = bool(protocol["fix_center_of_mass"])

    rng_init = np.random.default_rng(int(seed) + 1)
    rng_dyn = np.random.default_rng(int(seed) + 2)

    MaxwellBoltzmannDistribution(
        atoms, temperature_K=temperature, rng=rng_init
    )
    dyn = Langevin(
        atoms,
        timestep=timestep_fs,
        temperature_K=temperature,
        friction=friction,
        fixcm=fixcm,
        rng=rng_dyn,
    )

    n = len(atoms)
    li_indices = [i for i, s in enumerate(species) if s == "Li"]
    trace = sorted(set([0, 1, 5, 10] if trace_steps is None else trace_steps))
    trace = [s for s in trace if 0 <= s <= steps]

    def frame(step: int) -> Dict[str, Any]:
        pos = np.asarray(atoms.get_positions(), dtype=float)
        vel = np.asarray(atoms.get_velocities(), dtype=float)
        forces = np.asarray(atoms.get_forces(), dtype=float)
        speed = np.sqrt((vel ** 2).sum(axis=1))
        fmag = np.sqrt((forces ** 2).sum(axis=1))

        li_payload = []
        for idx in li_indices:
            li_payload.append({
                "index": idx,
                "position_A": pos[idx].tolist(),
                "velocity_A_fs": vel[idx].tolist(),
                "speed_A_fs": float(speed[idx]),
                "force_eV_A": float(fmag[idx]),
            })

        return {
            "step": int(step),
            "temperature_K": float(atoms.get_temperature()),
            "kinetic_energy_eV": float(atoms.get_kinetic_energy()),
            "potential_energy_eV": float(atoms.get_potential_energy()),
            "total_energy_eV": float(
                atoms.get_kinetic_energy() + atoms.get_potential_energy()
            ),
            "max_speed_A_fs": float(speed.max()) if n else 0.0,
            "max_speed_atom_index": int(speed.argmax()) if n else None,
            "max_force_eV_A": float(fmag.max()) if n else 0.0,
            "max_force_atom_index": int(fmag.argmax()) if n else None,
            "li_atoms": li_payload,
        }

    snapshots: Dict[int, Dict[str, Any]] = {}
    snapshots[0] = frame(0)

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
        "diagnostic": "p2_initialization_early_steps",
        "diagnostic_version": "p2-init-v1",
        "batch_id": batch_id,
        "child_material_id": candidate.get("child_material_id"),
        "parent_id": candidate.get("parent_id"),
        "natoms": n,
        "li_indices": li_indices,
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
        "snapshots": [snapshots[s] for s in sorted(snapshots)],
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{batch_id}.json"
    tmp = out_file.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    tmp.replace(out_file)
    result["record_file"] = out_file.as_posix()
    return result


def main() -> None:
    import argparse
    import yaml

    from rudeus.mlip.gpu_diagnostic import resolve_device, resolve_diagnostic_candidate
    from rudeus.mlip.p2 import (
        P2_PROTOCOL_DEFAULTS,
        batch_seed,
        load_authorization_manifest,
        protocol_config_hash,
    )
    from rudeus.mlip.relax import default_model_path, ensure_checkpoint, load_calculator

    parser = argparse.ArgumentParser(
        description="Diagnostic-only P2 initialization and early MD trace."
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--p1-done", default="data/batches/done")
    parser.add_argument("--authorized-manifest",
                        default="data/batches/audit/p2_production_authorized_44_adaptive.json")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--worker", default="p2-init-diagnostic")
    parser.add_argument("--out",
                        default="data/batches/audit/p2_initialization_diagnostic")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update(cfg.get("p2", {}))
    protocol["_protocol_hash"] = protocol_config_hash(protocol)

    allowlist = load_authorization_manifest(args.authorized_manifest)
    if args.batch_id not in allowlist:
        raise SystemExit(
            f"STOP: batch {args.batch_id} is not authorized by "
            f"{args.authorized_manifest}"
        )

    device = resolve_device(args.device)
    candidate = resolve_diagnostic_candidate(args.p1_done, args.batch_id)

    mcfg = cfg["mlip"]
    model_path = ensure_checkpoint(
        mcfg["checkpoint_url"],
        default_model_path(),
        mcfg["checkpoint_sha256"],
    )
    calc = load_calculator(
        model_path,
        device=device,
        dtype=cfg.get("p2", {}).get("dtype", "float32"),
    )
    seed = batch_seed(int(protocol.get("base_seed", 550)), args.batch_id)

    payload = run_initialization_diagnostic(
        candidate=candidate,
        calc=calc,
        protocol=protocol,
        seed=seed,
        batch_id=args.batch_id,
        steps=args.steps,
        output_dir=args.out,
    )
    payload["device"] = device
    payload["checkpoint_id"] = mcfg["primary_checkpoint"]
    payload["checkpoint_sha256"] = mcfg["checkpoint_sha256"]
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
