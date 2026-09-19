"""Diagnostic-only fixed-position local force replay.

Reproduces the existing deterministic P2 initialization for a bounded number of
steps, captures exact full-structure positions at selected steps, then evaluates
those fixed geometries with pinned MACE float32 and float64 calculators. No
production trajectory is written and no P2 semantics are changed.
"""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path

import numpy as np


def replay_snapshots(*, structure_dict, snapshots, calc32, calc64, batch_id, output_dir):
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    structure = Structure.from_dict(structure_dict)
    results = []

    for snap in snapshots:
        atoms32 = AseAtomsAdaptor.get_atoms(structure)
        atoms32.set_positions(np.asarray(snap["positions_A"], dtype=float))
        atoms32.calc = calc32
        f32 = np.asarray(atoms32.get_forces(), dtype=float)
        e32 = float(atoms32.get_potential_energy())

        atoms64 = AseAtomsAdaptor.get_atoms(structure)
        atoms64.set_positions(np.asarray(snap["positions_A"], dtype=float))
        atoms64.calc = calc64
        f64 = np.asarray(atoms64.get_forces(), dtype=float)
        e64 = float(atoms64.get_potential_energy())

        delta = f64 - f32
        dmag = np.sqrt((delta ** 2).sum(axis=1))
        m32 = np.sqrt((f32 ** 2).sum(axis=1))
        m64 = np.sqrt((f64 ** 2).sum(axis=1))

        results.append({
            "step": int(snap["step"]),
            "temperature_K": float(snap["temperature_K"]),
            "max_force_float32_eV_A": float(m32.max()),
            "max_force_float64_eV_A": float(m64.max()),
            "max_force_float32_atom_index": int(m32.argmax()),
            "max_force_float64_atom_index": int(m64.argmax()),
            "max_force_delta_eV_A": float(dmag.max()),
            "max_force_delta_atom_index": int(dmag.argmax()),
            "rms_force_delta_eV_A": float(np.sqrt(np.mean(delta ** 2))),
            "potential_energy_float32_eV": e32,
            "potential_energy_float64_eV": e64,
            "potential_energy_delta_eV": float(e64 - e32),
        })

    result = {
        "diagnostic": "p2_local_force_replay",
        "diagnostic_version": "p2-local-force-replay-v1",
        "batch_id": batch_id,
        "natoms": len(structure),
        "trace_steps": [int(s["step"]) for s in snapshots],
        "results": results,
    }

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{batch_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return result


def main():
    import yaml
    from ase.md.langevin import Langevin
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    from rudeus.mlip.gpu_diagnostic import resolve_device, resolve_diagnostic_candidate
    from rudeus.mlip.p2 import (
        P2_PROTOCOL_DEFAULTS,
        batch_seed,
        load_authorization_manifest,
        protocol_config_hash,
    )
    from rudeus.mlip.relax import default_model_path, ensure_checkpoint, load_calculator

    p = argparse.ArgumentParser(description="Fixed-position local MACE force replay.")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--p1-done", default="data/batches/done")
    p.add_argument("--authorized-manifest",
                   default="data/batches/audit/p2_production_authorized_44_adaptive.json")
    p.add_argument("--batch-id", required=True)
    p.add_argument("--device", default="cuda")
    p.add_argument("--steps", type=int, default=10)
    p.add_argument("--trace-steps", default="0,1,2,5,10")
    p.add_argument("--out", default="data/batches/audit/p2_local_force_replay")
    args = p.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update(cfg.get("p2", {}))
    protocol["_protocol_hash"] = protocol_config_hash(protocol)

    allowlist = load_authorization_manifest(args.authorized_manifest)
    if args.batch_id not in allowlist:
        raise SystemExit(f"STOP: batch {args.batch_id} is not authorized")

    device = resolve_device(args.device)
    candidate = resolve_diagnostic_candidate(args.p1_done, args.batch_id)

    mcfg = cfg["mlip"]
    model_path = ensure_checkpoint(
        mcfg["checkpoint_url"], default_model_path(), mcfg["checkpoint_sha256"]
    )
    calc32 = load_calculator(model_path, device=device, dtype="float32")
    calc64 = load_calculator(model_path, device=device, dtype="float64")

    structure = Structure.from_dict(candidate["structure_dict"])
    atoms = AseAtomsAdaptor.get_atoms(structure)
    atoms.calc = calc32

    temperature = float(protocol["temperature_K"])
    timestep_fs = float(protocol["timestep_fs"])
    friction = float(protocol["friction_fs_inv_provisional"])
    fixcm = bool(protocol["fix_center_of_mass"])

    seed = batch_seed(int(protocol.get("base_seed", 550)), args.batch_id)
    rng_init = np.random.default_rng(int(seed) + 1)
    rng_dyn = np.random.default_rng(int(seed) + 2)
    MaxwellBoltzmannDistribution(atoms, temperature_K=temperature, rng=rng_init)
    dyn = Langevin(
        atoms,
        timestep=timestep_fs,
        temperature_K=temperature,
        friction=friction,
        fixcm=fixcm,
        rng=rng_dyn,
    )

    trace = sorted(set(int(x) for x in args.trace_steps.split(",") if x.strip()))
    trace = [s for s in trace if 0 <= s <= args.steps]
    snapshots = []

    def capture(step):
        snapshots.append({
            "step": int(step),
            "positions_A": np.asarray(atoms.get_positions(), dtype=float).copy().tolist(),
            "temperature_K": float(atoms.get_temperature()),
        })

    capture(0)

    def observer():
        step = int(dyn.nsteps)
        if step in trace:
            capture(step)

    dyn.attach(observer, interval=1)
    dyn.run(int(args.steps))

    del dyn
    del atoms
    gc.collect()

    payload = replay_snapshots(
        structure_dict=candidate["structure_dict"],
        snapshots=snapshots,
        calc32=calc32,
        calc64=calc64,
        batch_id=args.batch_id,
        output_dir=args.out,
    )
    payload.update({
        "device": device,
        "checkpoint_id": mcfg["primary_checkpoint"],
        "checkpoint_sha256": mcfg["checkpoint_sha256"],
        "seed": int(seed),
        "initialization": {
            "temperature_K": temperature,
            "timestep_fs": timestep_fs,
            "friction_fs_inv": friction,
            "fix_center_of_mass": fixcm,
            "init_rng_seed": int(seed) + 1,
            "dynamics_rng_seed": int(seed) + 2,
        },
    })
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
