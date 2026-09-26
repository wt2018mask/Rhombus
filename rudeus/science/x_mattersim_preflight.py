"""MatterSim operational preflight for stage X.

This module is deliberately NOT a scientific X observation producer. It verifies
that a frozen Rhombus structure can be loaded in an isolated Python>=3.12
MatterSim runtime and evaluated on CUDA. The output is operational evidence only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any

import numpy as np
from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor

from rudeus.science.contracts import canonical_bytes


PREFLIGHT_VERSION = "mattersim-x-preflight-v1"
CHECKPOINT_LABEL = "MatterSim-v1.0.0-1M"
TRAINING_DATA_ID = "mattersim-manuscript-generated-dataset-v1"
MODEL_FAMILY = "M3GNet-MatterSim"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_runtime() -> tuple[Any, Any]:
    if sys.version_info < (3, 12):
        raise RuntimeError("MatterSim X preflight requires Python >=3.12")
    try:
        import torch
        from mattersim.forcefield import MatterSimCalculator
    except ImportError as exc:
        raise RuntimeError("MatterSim runtime is not installed") from exc
    if not torch.cuda.is_available():
        raise RuntimeError("MatterSim X preflight requires CUDA; CPU fallback is forbidden")
    return torch, MatterSimCalculator


def run_preflight(batch_path: Path) -> dict[str, Any]:
    torch, MatterSimCalculator = _require_runtime()

    raw = json.loads(batch_path.read_text(encoding="utf-8"))
    required = {"batch_id", "structure_sha256", "structure_dict"}
    if not required.issubset(raw):
        raise ValueError("batch missing structure identity fields")

    structure = Structure.from_dict(raw["structure_dict"])
    if not structure.is_ordered:
        raise ValueError("disordered structure is unsupported for X preflight")

    atoms = AseAtomsAdaptor.get_atoms(structure)
    atoms.calc = MatterSimCalculator(device="cuda")

    energy = float(atoms.get_potential_energy())
    forces = np.asarray(atoms.get_forces(), dtype=float)
    stress = np.asarray(atoms.get_stress(voigt=False), dtype=float)

    if not math.isfinite(energy) or not np.all(np.isfinite(forces)) or not np.all(np.isfinite(stress)):
        raise FloatingPointError("MatterSim produced non-finite output")
    if forces.shape != (len(atoms), 3) or stress.shape != (3, 3):
        raise ValueError("MatterSim output shape mismatch")

    result = {
        "schema_version": PREFLIGHT_VERSION,
        "status": "PREFLIGHT_ONLY",
        "scientific_x_evidence": False,
        "scientific_verdict_changed": False,
        "batch_id": raw["batch_id"],
        "structure_sha256": raw["structure_sha256"],
        "batch_file_sha256": _sha256(batch_path),
        "n_atoms": len(atoms),
        "formula": structure.composition.reduced_formula,
        "model_identity": {
            "model_name": CHECKPOINT_LABEL,
            "model_family": MODEL_FAMILY,
            "training_data_id": TRAINING_DATA_ID,
            "checkpoint_label": CHECKPOINT_LABEL,
        },
        "runtime": {
            "python": platform.python_version(),
            "mattersim": importlib.metadata.version("mattersim"),
            "torch": torch.__version__,
            "cuda_available": bool(torch.cuda.is_available()),
            "cuda_device_name": torch.cuda.get_device_name(0),
        },
        "single_point": {
            "energy_eV": energy,
            "energy_eV_per_atom": energy / len(atoms),
            "force_max_eV_per_A": float(np.linalg.norm(forces, axis=1).max()),
            "force_rms_eV_per_A": float(np.sqrt(np.mean(forces ** 2))),
            "stress_eV_per_A3": stress.tolist(),
        },
        "interpretation": (
            "Operational compatibility check only; this result is not a transport "
            "observable and cannot satisfy or modify stage-X scientific assessment."
        ),
    }
    canonical_bytes(result)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="MatterSim CUDA preflight for a frozen Rhombus batch")
    parser.add_argument("--batch", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    output = Path(args.output)
    try:
        result = run_preflight(Path(args.batch))
        data = canonical_bytes(result)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists() and output.read_bytes() != data:
            raise FileExistsError("refusing to overwrite different MatterSim preflight result")
        if not output.exists():
            output.write_bytes(data)
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, sort_keys=True))
        return 1

    print(json.dumps({
        "status": result["status"],
        "batch_id": result["batch_id"],
        "n_atoms": result["n_atoms"],
        "model": result["model_identity"]["model_name"],
        "scientific_x_evidence": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
