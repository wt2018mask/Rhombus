"""P0 Static Filters: Fast Chemical & Geometric Pre-Screening.

Filters candidates before compute-intensive MLIP relaxation:
1. SMACT charge-neutrality check (neutral oxidation state combinations).
2. Pauling electronegativity sanity check.
3. CrystalNN & pairwise distance clash check (basic geometry validity).

Output is compatible with rudeus.schema.ExistenceState:
- Passing P0 sets existence_state to PLAUSIBLE (never SUPPORTED without empirical/MLIP evidence).
- Failing P0 sets existence_state to FAIL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from pymatgen.core import Composition, Structure
from pymatgen.analysis.local_env import CrystalNN
import smact
import smact.screening

from rudeus.schema import CandidateMaterial, EvidenceEvent, ExistenceState


@dataclass(frozen=True)
class P0FilterResult:
    """Result of P0 static filter evaluation."""
    passed: bool
    existence_state: ExistenceState
    neutrality_ok: bool
    pauling_ok: bool
    geometry_ok: bool
    details: Dict[str, Any]
    evidence_event: EvidenceEvent


def check_charge_neutrality_smact(composition: Union[str, Composition]) -> Tuple[bool, Dict[str, Any]]:
    """Check whether a composition can form a charge-neutral compound using SMACT oxidation states."""
    if isinstance(composition, str):
        comp = Composition(composition)
    else:
        comp = composition

    elements = [str(el) for el in comp.elements]
    stoichs = [int(comp[el]) for el in comp.elements]

    # Handle single element or trivial cases
    if len(elements) == 1:
        return True, {"neutral_found": True, "type": "elemental"}

    try:
        valid = bool(smact.screening.smact_validity(comp, use_pauling_test=False, include_alloys=False))
        return valid, {"neutral_found": valid, "elements": elements}
    except Exception as e:
        return False, {"error": str(e), "elements": elements}


def check_pauling_electronegativity(composition: Union[str, Composition]) -> Tuple[bool, Dict[str, Any]]:
    """Check Pauling electronegativity sanity to prevent unphysical elemental combinations."""
    if isinstance(composition, str):
        comp = Composition(composition)
    else:
        comp = composition

    elements = [str(el) for el in comp.elements]
    if len(elements) < 2:
        return True, {"pauling_ok": True}

    try:
        smact_elements = [smact.Element(el) for el in elements]
        # Check if electronegativities exist
        enegs = [e.pauling_eneg for e in smact_elements]
        if any(eneg is None for eneg in enegs):
            return True, {"warning": "unknown_electronegativity"}

        # Pauling test from smact
        p_test = bool(smact.screening.pauling_test(smact_elements))
        return p_test, {"pauling_test": p_test, "electronegativities": enegs}
    except Exception as e:
        return True, {"warning": f"pauling_check_skipped: {e}"}


def check_geometry_clash(
    structure: Structure,
    clash_ratio_provisional: float = 0.60,  # PROVISIONAL: Minimum distance ratio of sum of radii
) -> Tuple[bool, Dict[str, Any]]:
    """Check for unphysical atomic overlaps using pairwise atomic distances.

    Args:
        structure: Pymatgen Structure object.
        clash_ratio_provisional: Fractional cutoff relative to sum of covalent radii.

    Returns:
        (passed, details)
    """
    try:
        dm = structure.distance_matrix
        n = len(structure)
        for i in range(n):
            for j in range(i + 1, n):
                dist = dm[i, j]
                r_i = structure[i].specie.atomic_radius or 1.0
                r_j = structure[j].specie.atomic_radius or 1.0
                min_allowed = (r_i + r_j) * clash_ratio_provisional
                if dist < min_allowed:
                    return False, {
                        "clash_detected": True,
                        "atom_i": str(structure[i].specie),
                        "atom_j": str(structure[j].specie),
                        "distance": float(dist),
                        "min_allowed": float(min_allowed),
                    }
        return True, {"clash_detected": False}
    except Exception as e:
        return False, {"error": f"geometry_clash_check_error: {e}"}


def check_crystal_coordination(
    structure: Structure,
) -> Tuple[bool, Dict[str, Any]]:
    """Inspect local coordination environments using CrystalNN to ensure sane coordination numbers."""
    try:
        cnn = CrystalNN(weighted_cn=False, distance_cutoffs=None, x_diff_weight=0.0)
        cns = []
        for i in range(len(structure)):
            cn = cnn.get_cn(structure, i)
            cns.append(cn)
            # Sane physical bounds: coordination number must be between 1 and 16
            if cn < 1 or cn > 16:
                return False, {
                    "unphysical_coordination": True,
                    "site_index": i,
                    "site_specie": str(structure[i].specie),
                    "coordination_number": cn,
                }
        return True, {"mean_coordination": float(np.mean(cns)), "all_sites_sane": True}
    except Exception as e:
        # If CrystalNN fails (e.g. ill-defined periodic cell), flag for review
        return False, {"error": f"crystalnn_error: {e}"}


def evaluate_p0(
    formula_or_candidate: Union[str, CandidateMaterial],
    structure: Optional[Structure] = None,
    clash_ratio_provisional: float = 0.60,
) -> P0FilterResult:
    """Run comprehensive P0 static filters and produce an ExistenceState verdict.

    Returns:
        P0FilterResult with existence_state=PLAUSIBLE on pass, or FAIL on failure.
    """
    if isinstance(formula_or_candidate, CandidateMaterial):
        formula = formula_or_candidate.formula
        if structure is None and formula_or_candidate.structure_dict:
            structure = Structure.from_dict(formula_or_candidate.structure_dict)
    else:
        formula = formula_or_candidate

    neutrality_ok, neut_details = check_charge_neutrality_smact(formula)
    pauling_ok, pauling_details = check_pauling_electronegativity(formula)

    geometry_ok = True
    geom_details: Dict[str, Any] = {}
    coord_details: Dict[str, Any] = {}

    if structure is not None:
        geom_ok, geom_details = check_geometry_clash(structure, clash_ratio_provisional)
        coord_ok, coord_details = check_crystal_coordination(structure)
        geometry_ok = geom_ok and coord_ok

    passed = bool(neutrality_ok and pauling_ok and geometry_ok)
    verdict = ExistenceState.PLAUSIBLE if passed else ExistenceState.FAIL

    details = {
        "neutrality": neut_details,
        "pauling": pauling_details,
        "geometry": geom_details,
        "coordination": coord_details,
        "provisional_clash_ratio": clash_ratio_provisional,
    }

    event = EvidenceEvent(
        level="P0",
        method="static_composition_and_geometry_filters",
        conditions={
            "clash_ratio_provisional": clash_ratio_provisional,
            "has_structure": structure is not None,
        },
        uncertainty=None,
        source="p0_filter",
        artifact_hash="",
        model_or_data_version="smact-4.0.0_pymatgen",
    )

    return P0FilterResult(
        passed=passed,
        existence_state=verdict,
        neutrality_ok=neutrality_ok,
        pauling_ok=pauling_ok,
        geometry_ok=geometry_ok,
        details=details,
        evidence_event=event,
    )
