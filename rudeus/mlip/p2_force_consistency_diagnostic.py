"""Diagnostic-only MACE float32/float64 force-consistency replay.

Runs the existing deterministic P2 initialization with the production MD dtype
(float32), records selected early-step snapshots, then evaluates the exact same
positions with the pinned MACE checkpoint in float64. This module does not alter
P2 protocol, thresholds, verdicts, or production artifacts.
"""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from typing import Any

import numpy as np


def _force_metrics(f32: np.ndarray, f64: np.ndarray) -> dict[str, Any]:
    a = np.asarray(f32, dtype=float)
    b = np.asarray(f64, dtype=float)
    delta = b - a
    dmag = np.sqrt((delta ** 2).sum(axis=1))
    m32 = np.sqrt((a ** 2).sum(axis=1))
    m64 = np.sqrt((b ** 2).sum(axis=1))
    scale = np.maximum(m64, 1e-12)
    rel = dmag / scale
    return {
        "max_abs_force_delta_eV_A": float(dmag.max()) if len(dmag) else 0.0,
        "rms_force_delta_eV_A": float(np.sqrt(np.mean(delta ** 2))) if delta.size else 0.0,
        "mean_abs_force_delta_eV_A": float(dmag.mean()) if len(dmag) else 0.0,
        "max_relative_force_delta": float(rel.max()) if len(rel) else 0.0,
        "max_force_f32_eV_A": float(m32.max()) if len(m32) else 0.0,
        "max_force_f64_eV_A": float(m64.max()) if len(m64) else 0.0,
        "max_force_f32_atom_index": int(m32.argmax()) if len(m32) else None,
        "max_force_f64_atom_index": int(m64.argmax()) if len(m64) else None,
        "max_delta_atom_index": int(dmag.argmax()) if len(dmag) else None,
    }


def run_force_consistency_diagnostic(
    *,
    candidate: dict[str, Any],
    calc32: Any,
    calc64_loader: Any,
    protocol: dict[str, Any],
    seed: int,
    batch_id: str,
    steps: int = 10,
    trace_steps: list[int] | None = None,
    output_dir: str | Path = "data/batches/audit/p2_force_consistency_diagnostic",
) -> dict[str, Any]:
    from ase import Atoms
    from ase.md.langevin import Langevin
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    if steps < 0:
        raise ValueError("steps must be >= 0")

    structure = Structure.from_dict(candidate["structure_dict"])
    atoms = AseAtomsAdaptor.get_atoms(structure)
    atoms.calc = calc32

    temperature = float(protocol["temperature_K"])
    timestep_fs = float(protocol["timestep_fs"])
    friction = float(protocol["friction_fs_inv_provisional"])
    fixcm = bool(protocol["fix_center_of_mass"])

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

    trace = sorted(set([0, 1, 2, 3, 4, 5, 10] if trace_steps is None else trace_steps))
    trace = [s for s in trace if 0 <= s <= steps]

    snapshots: dict[int, dict[str, Any]] = {}

    def capture(step: int) -> None:
        positions = np.asarray(atoms.get_positions(), dtype=float).copy()
        forces32 = np.asarray(atoms.get_forces(), dtype=float).copy()
        snapshots[int(step)] = {
            "step": int(step),
            "positions_A": positions.tolist(),
            "forces_float32_eV_A": forces32.tolist(),
            "temperature_K": float(atoms.get_temperature()),
            "potential_energy_float32_eV": float(atoms.get_potential_energy()),
        }

    capture(0)

    def observer() -> None:
        step = int(dyn.nsteps)
        if step in trace:
            capture(step)

    dyn.attach(observer, interval=1)
    if steps:
        dyn.run(int(steps))
    if int(dyn.nsteps) in trace and int(dyn.nsteps) not in snapshots:
        capture(int(dyn.nsteps))

    # Release the float32 calculator before loading the float64 calculator so the
    # comparison remains usable on constrained GPU workers.
    atoms.calc = None
    del atoms
    del dyn
    gc.collect()

    calc64 = calc64_loader()
    results: list[dict[str, Any]] = []

    for step in sorted(snapshots):
        snap = snapshots[step]
        atoms64: Atoms = AseAtomsAdaptor.get_atoms(structure)
        atoms64.set_positions(np.asarray(snap["positions_A"], dtype=float))
        atoms64.calc = calc64
        forces64 = np.asarray(atoms64.get_forces(), dtype=float)
        f32 = np.asarray(snap["forces_float32_eV_A"], dtype=float)

        metrics = _force_metrics(f32, forces64)
        metrics.update({
            "step": int(step),
            "temperature_K": float(snap["temperature_K"]),
            "potential_energy_float32_eV": float(snap["potential_energy_float32_eV"]),
            "potential_energy_float64_eV": float(atoms64.get_potential_energy()),
            "potential_energy_delta_eV": float(
                atoms64.get_potential_energy() - snap["potential_energy_float32_eV"]
            ),
        })
        results.append(metrics)

    result = {
        "diagnostic": "p2_mace_force_consistency",
        "diagnostic_version": "p2-force-consistency-v1",
        "batch_id": batch_id,
        "child_material_id": candidate.get("child_material_id"),
        "parent_id": candidate.get("parent_id"),
        "natoms": len(structure),
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
        "steps_completed": int(max(snapshots) if snapshots else 0),
        "trace_steps": trace,
        "float32_checkpoint": "medium-mpa-0",
        "float64_checkpoint": "medium-mpa-0",
        "results": results,
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
        description="Diagnostic-only MACE float32/float64 force consistency replay."
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--p1-done", default="data/batches/done")
    parser.add_argument(
        "--authorized-manifest",
        default="data/batches/audit/p2_production_authorized_44_adaptive.json",
    )
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument("--worker", default="p2-force-consistency-diagnostic")
    parser.add_argument("--out", default="data/batches/audit/p2_force_consistency_diagnostic")
    parser.add_argument("--trace-steps", default="0,1,2,3,4,5,10")
    args = parser.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    protocol = dict(P2_PROTOCOL_DEFAULTS)
    protocol.update(cfg.get("p2", {}))
    protocol["_protocol_hash"] = protocol_config_hash(protocol)

    allowlist = load_authorization_manifest(args.authorized_manifest)
    if args.batch_id not in allowlist:
        raise SystemExit(
            f"STOP: batch {args.batch_id} is not authorized by {args.authorized_manifest}"
        )

    device = resolve_device(args.device)
    candidate = resolve_diagnostic_candidate(args.p1_done, args.batch_id)

    mcfg = cfg["mlip"]
    model_path = ensure_checkpoint(
        mcfg["checkpoint_url"],
        default_model_path(),
        mcfg["checkpoint_sha256"],
    )

    calc32 = load_calculator(model_path, device=device, dtype="float32")

    def load64() -> Any:
        return load_calculator(model_path, device=device, dtype="float64")

    seed = batch_seed(int(protocol.get("base_seed", 550)), args.batch_id)
    trace_steps = [int(x) for x in args.trace_steps.split(",") if x.strip()]

    payload = run_force_consistency_diagnostic(
        candidate=candidate,
        calc32=calc32,
        calc64_loader=load64,
        protocol=protocol,
        seed=seed,
        batch_id=args.batch_id,
        steps=args.steps,
        trace_steps=trace_steps,
        output_dir=args.out,
    )
    payload["device"] = device
    payload["checkpoint_id"] = mcfg["primary_checkpoint"]
    payload["checkpoint_sha256"] = mcfg["checkpoint_sha256"]
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
