"""Diagnostic-only replay of stored early P2 positions with pinned MACE.

This does not run MD and does not alter P2 semantics. It loads the exact
float32/float64 position snapshots produced by the force-consistency diagnostic
and evaluates forces/energies at those fixed geometries.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def replay_positions(
    *,
    structure_dict: dict[str, Any],
    snapshots: list[dict[str, Any]],
    calc32: Any,
    calc64: Any,
    batch_id: str,
    output_dir: str | Path,
) -> dict[str, Any]:
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

        d = f64 - f32
        dm = np.sqrt((d ** 2).sum(axis=1))
        m32 = np.sqrt((f32 ** 2).sum(axis=1))
        m64 = np.sqrt((f64 ** 2).sum(axis=1))

        results.append({
            "step": int(snap["step"]),
            "temperature_K": float(snap["temperature_K"]),
            "max_force_float32_eV_A": float(m32.max()),
            "max_force_float64_eV_A": float(m64.max()),
            "max_force_float32_atom_index": int(m32.argmax()),
            "max_force_float64_atom_index": int(m64.argmax()),
            "max_force_delta_eV_A": float(dm.max()),
            "max_force_delta_atom_index": int(dm.argmax()),
            "rms_force_delta_eV_A": float(np.sqrt(np.mean(d ** 2))),
            "potential_energy_float32_eV": e32,
            "potential_energy_float64_eV": e64,
            "potential_energy_delta_eV": e64 - e32,
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

    parser = argparse.ArgumentParser(description="Replay stored early P2 positions with MACE.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--p1-done", default="data/batches/done")
    parser.add_argument(
        "--authorized-manifest",
        default="data/batches/audit/p2_production_authorized_44_adaptive.json",
    )
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument(
        "--force-consistency-record",
        default="data/batches/audit/p2_force_consistency_diagnostic/06c995df17893ed0.json",
    )
    parser.add_argument(
        "--out",
        default="data/batches/audit/p2_local_force_replay",
    )
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

    record = json.loads(Path(args.force_consistency_record).read_text(encoding="utf-8"))
    if record.get("batch_id") != args.batch_id:
        raise SystemExit("STOP: diagnostic record batch_id does not match requested batch")

    # Reconstruct the exact candidate structure and use the stored trajectory
    # positions from the diagnostic. Positions are the only dynamic input here.
    snapshots = record.get("snapshots")
    if not snapshots:
        raise SystemExit(
            "STOP: force-consistency record does not contain stored position snapshots"
        )

    mcfg = cfg["mlip"]
    model_path = ensure_checkpoint(
        mcfg["checkpoint_url"],
        default_model_path(),
        mcfg["checkpoint_sha256"],
    )
    calc32 = load_calculator(model_path, device=device, dtype="float32")
    calc64 = load_calculator(model_path, device=device, dtype="float64")

    payload = replay_positions(
        structure_dict=candidate["structure_dict"],
        snapshots=snapshots,
        calc32=calc32,
        calc64=calc64,
        batch_id=args.batch_id,
        output_dir=args.out,
    )
    payload["device"] = device
    payload["checkpoint_id"] = mcfg["primary_checkpoint"]
    payload["checkpoint_sha256"] = mcfg["checkpoint_sha256"]
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
