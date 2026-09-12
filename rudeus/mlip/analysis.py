"""Post-relaxation structural analysis (pure functions, no calculator needed).

- compare_structures: audit metrics between initial and relaxed structures.
- annotate_post_relax_novelty: parent-collapse / rediscovery detection with the
  existing StructureMatcher machinery. Tags are descriptive only — no scientific
  scores, no state changes (P2/P2.5/P3 own their evidence dimensions).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def compare_structures(initial_dict: Dict[str, Any],
                       relaxed_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Audit metrics between two structures with the same atom ordering.

    Displacements are raw Cartesian differences and therefore INCLUDE any
    rigid-body translation/rotation from the optimizer; the matcher-based
    collapse check (insensitive to rigid motion) is the companion verdict.
    All fields are None-safe only when inputs are valid structure dicts.
    """
    from pymatgen.core import Structure

    initial = Structure.from_dict(initial_dict)
    relaxed = Structure.from_dict(relaxed_dict)
    if len(initial) != len(relaxed):
        raise ValueError(
            f"atom count changed {len(initial)} -> {len(relaxed)}: "
            "relaxation must preserve composition/order")
    v0, v1 = float(initial.volume), float(relaxed.volume)
    disp = np.linalg.norm(relaxed.cart_coords - initial.cart_coords, axis=1)
    abc0 = np.array(initial.lattice.abc, dtype=float)
    abc1 = np.array(relaxed.lattice.abc, dtype=float)
    ang0 = np.array(initial.lattice.angles, dtype=float)
    ang1 = np.array(relaxed.lattice.angles, dtype=float)
    dm = relaxed.distance_matrix
    n = len(relaxed)
    min_dist = float(min(dm[i, j] for i in range(n) for j in range(i + 1, n))) if n > 1 else 0.0
    return {
        "n_atoms": n,
        "initial_volume_A3": v0,
        "relaxed_volume_A3": v1,
        "volume_change_fraction": float((v1 - v0) / v0) if v0 else 0.0,
        "abc_change_A": [float(x) for x in (abc1 - abc0)],
        "angles_change_deg": [float(x) for x in (ang1 - ang0)],
        "max_atomic_displacement_A": float(disp.max()) if n else 0.0,
        "rms_displacement_A": float(np.sqrt((disp ** 2).mean())) if n else 0.0,
        "min_interatomic_distance_A": min_dist,
    }


def annotate_post_relax_novelty(
    relaxed_dict: Optional[Dict[str, Any]],
    parent_dict: Optional[Dict[str, Any]],
    sibling_dicts: List[Tuple[str, Dict[str, Any]]],
    matcher=None,
) -> Dict[str, Any]:
    """Tag a relaxed child vs parent and vs already-relaxed siblings.

    Returns {"post_relax_novelty": "novel" | "rediscovery_after_relaxation" |
    "not-checked", "matched": "parent" | batch_id | None, "note": ...}.
    A matcher failure yields "not-checked", never a verdict. No thresholds,
    no scores — pure description for later scientific interpretation.
    """
    from pymatgen.analysis.structure_matcher import StructureMatcher
    from pymatgen.core import Structure

    matcher = matcher or StructureMatcher()
    if relaxed_dict is None:
        return {"post_relax_novelty": "not-checked", "matched": None,
                "note": "no relaxed structure (skipped/failed before relax)"}
    try:
        relaxed = Structure.from_dict(relaxed_dict)
        if parent_dict is not None:
            if matcher.fit(Structure.from_dict(parent_dict), relaxed):
                return {"post_relax_novelty": "rediscovery_after_relaxation",
                        "matched": "parent", "note": None}
        for sib_id, sib_dict in sibling_dicts:
            if matcher.fit(Structure.from_dict(sib_dict), relaxed):
                return {"post_relax_novelty": "rediscovery_after_relaxation",
                        "matched": sib_id, "note": None}
        return {"post_relax_novelty": "novel", "matched": None, "note": None}
    except Exception as e:
        return {"post_relax_novelty": "not-checked", "matched": None,
                "note": f"matcher-error: {type(e).__name__}: {e}"}
