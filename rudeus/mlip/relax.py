"""P1 real relaxation with mace_mp("medium-mpa-0") + manifest writer.

Checkpoint discipline: the model file is verified by sha256 against the pinned
value BEFORE the calculator is built. Any mismatch (upstream update, truncated
download, cache poisoning) raises loudly — never a silent fallback.
E_hull is explicit null with hull_source "deferred" (DESIGN.md Q1).
"""

from __future__ import annotations

import hashlib
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Union

from rudeus.generation.generator import structure_sha256

#: Energy-comparison tolerance for dedup logic (DESIGN.md Q4, PROVISIONAL).
ENERGY_MATCH_TOL_MEV_PER_ATOM_PROVISIONAL = 5.0


def default_model_path() -> Path:
    """Local checkpoint location (NOT committed to git; (re)downloaded)."""
    return Path.home() / ".cache" / "rudeus" / "mace-mpa-0-medium.model"


def sha256_file(path: Union[str, Path]) -> str:
    """Hex sha256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_checkpoint(checkpoint_url: str, model_path: Union[str, Path],
                      expected_sha256: str) -> Path:
    """Download (if absent) and hash-verify the checkpoint. Loud on mismatch."""
    model_path = Path(model_path)
    if not expected_sha256:
        raise ValueError(
            "checkpoint_sha256 is not pinned: record the hash (see DESIGN.md "
            "section 4) before running. Refusing to relax against an "
            "unverified checkpoint.")
    if not model_path.exists():
        model_path.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(checkpoint_url, model_path)
    actual = sha256_file(model_path)
    if actual != expected_sha256:
        raise ValueError(
            f"checkpoint hash mismatch: expected {expected_sha256}, got "
            f"{actual} for {model_path}. Upstream update, truncated "
            f"download, or cache poisoning — refusing to run.")
    return model_path


def load_calculator(model_path: Union[str, Path], device: str = "cpu",
                    dtype: str = "float64"):
    """Build the pinned MACECalculator (imported lazily: mace is GPU-optional)."""
    from mace.calculators import mace_mp
    return mace_mp(model=str(model_path), device=device, default_dtype=dtype)


def energies_match(e1_ev: float, e2_ev: float, n_atoms: int,
                   tol_mev_per_atom_provisional: float
                   = ENERGY_MATCH_TOL_MEV_PER_ATOM_PROVISIONAL) -> bool:
    """Dedup comparison: per-atom energies within PROVISIONAL tolerance."""
    return abs(e1_ev - e2_ev) / max(1, n_atoms) * 1000.0 <= tol_mev_per_atom_provisional


def relax_structure(structure_dict: Dict[str, Any], calc,
                    force_tol_ev_A: float = 0.01,
                    max_steps: int = 200,
                    mace_precision: str = "float64",
                    worker_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Relax one structure; return the DESIGN.md section 3 result manifest.

    Deliberate placeholder for disordered input: partial occupancies have no
    defined single configuration for the calculator, so disordered structures
    get p1_verdict SKIPPED_DISORDERED with a reason (DESIGN.md Q5 tracks the
    real strategy choice). This is explicit triage, NOT silent canonicalizing.
    """
    import numpy as np
    from ase.filters import FrechetCellFilter
    from ase.optimize import LBFGS
    from pymatgen.core import Structure
    from pymatgen.io.ase import AseAtomsAdaptor

    structure = Structure.from_dict(structure_dict)
    if not structure.is_ordered:
        return {
            "input_structure_sha256": structure_sha256(structure),
            "relaxed_structure_sha256": None,
            "relaxed_structure_dict": None,
            "relaxed_energy_ev": None,
            "energy_per_atom_ev": None,
            "e_hull_ev_per_atom": None,  # deferred per DESIGN.md Q1
            "hull_source": "deferred",
            "converged": False,
            "n_steps": 0,
            "max_force_ev_A": None,
            "force_tol_ev_A": force_tol_ev_A,
            "volume_change_fraction": None,
            "wall_clock_s": 0.0,
            "worker": worker_info or {},
            "mace_precision": mace_precision,
            "p1_verdict": "SKIPPED_DISORDERED",
            "reason": ("partial occupancies have no defined single configuration; "
                       "canonicalization strategy open (DESIGN.md Q5)"),
        }
    n_atoms = len(structure)
    v0 = structure.volume
    atoms = AseAtomsAdaptor.get_atoms(structure)
    atoms.calc = calc
    ecf = FrechetCellFilter(atoms)  # relax cell + positions (volume optimization)

    t_start = time.time()
    opt = LBFGS(ecf, logfile=None)
    opt.run(fmax=force_tol_ev_A, steps=max_steps)
    wall_s = time.time() - t_start

    energy = float(atoms.get_potential_energy())
    forces = np.asarray(atoms.get_forces())
    max_force = float(np.sqrt((forces ** 2).sum(axis=1)).max())
    relaxed = AseAtomsAdaptor.get_structure(atoms)
    converged = bool(opt.converged())

    unphysical = (not np.isfinite(energy)
                  or abs(relaxed.volume - v0) / v0 > 0.50)  # PROVISIONAL cap
    if not converged:
        verdict = "FAIL_CONVERGENCE"
    elif unphysical:
        verdict = "FAIL_UNPHYSICAL"
    else:
        verdict = "KEEP_FOR_P2"

    return {
        "input_structure_sha256": structure_sha256(structure),
        "relaxed_structure_sha256": structure_sha256(relaxed),
        "relaxed_structure_dict": relaxed.as_dict(),
        "relaxed_energy_ev": energy,
        "energy_per_atom_ev": energy / n_atoms,
        "e_hull_ev_per_atom": None,  # deferred per DESIGN.md Q1: explicit null
        "hull_source": "deferred",
        "converged": converged,
        "n_steps": int(opt.nsteps),
        "max_force_ev_A": max_force,
        "force_tol_ev_A": force_tol_ev_A,
        "volume_change_fraction": float((relaxed.volume - v0) / v0),
        "wall_clock_s": wall_s,
        "worker": worker_info or {},
        "mace_precision": mace_precision,
        "p1_verdict": verdict,
    }
