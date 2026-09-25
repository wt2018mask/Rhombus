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
import itertools
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
    neutrality_ok: Optional[bool]
    pauling_ok: Optional[bool]
    geometry_ok: Optional[bool]
    details: Dict[str, Any]
    evidence_event: EvidenceEvent


def _site_dominant_element(site):
    """Dominant-occupancy Element/Species for a site (ordered or disordered).

    Compatibility helper: ``PeriodicSite.specie`` was removed in newer
    pymatgen and raises ``AttributeError`` on disordered (partial-occupancy)
    sites. ``site.species`` works in both cases; for disordered sites the
    highest-occupancy species is used (same convention as bvse.py).
    """
    species = site.species
    if hasattr(species, "elements"):  # Composition-like (disordered site)
        return max(species.elements, key=lambda el: float(species[el]))
    return species  # Ordered site: single Element/Species


def _site_has_majority_species(site) -> bool:
    """Whether a site has one species with occupancy > 0.5.

    CrystalNN raises on sites without a majority species, so callers must
    handle such structures explicitly instead of letting the exception
    masquerade as a failed coordination check.
    """
    species = site.species
    if hasattr(species, "elements"):  # Composition-like (disordered site)
        return max(float(species[el]) for el in species.elements) > 0.5
    return True  # Ordered site always has a majority species.


def check_charge_neutrality_smact(composition: Union[str, Composition]) -> Tuple[Optional[bool], Dict[str, Any]]:
    """Check whether a composition can form a charge-neutral compound using SMACT oxidation states."""
    try:
        if isinstance(composition, str):
            comp = Composition(composition)
        else:
            comp = composition

        elements = [str(el) for el in comp.elements]

        # Handle single element or trivial cases
        if len(elements) == 1:
            return True, {"neutral_found": True, "type": "elemental"}

        valid = bool(smact.screening.smact_validity(comp, use_pauling_test=False, include_alloys=False))
        return valid, {"neutral_found": valid, "elements": elements}
    except Exception as e:
        return None, {
            "error": str(e),
            "elements": [str(el) for el in comp.elements] if "comp" in locals() and hasattr(comp, "elements") else [],
        }


def check_pauling_electronegativity(composition: Union[str, Composition]) -> Tuple[Optional[bool], Dict[str, Any]]:
    """Check Pauling electronegativity sanity to prevent unphysical elemental combinations."""
    try:
        if isinstance(composition, str):
            comp = Composition(composition)
        else:
            comp = composition

        elements = [str(el) for el in comp.elements]
        if len(elements) < 2:
            return True, {"pauling_ok": True}

        smact_elements = [smact.Element(el) for el in elements]
        # Check if electronegativities exist
        enegs = [e.pauling_eneg for e in smact_elements]
        if any(eneg is None for eneg in enegs):
            return None, {
                "error": "unknown_electronegativity",
                "elements": elements,
                "electronegativities": enegs,
            }

        ox_combos = [e.oxidation_states for e in smact_elements]
        if any(not ox for ox in ox_combos):
            return None, {
                "error": "missing_oxidation_states",
                "elements": elements,
            }

        # Pauling test from smact: check if any oxidation state combination
        # satisfies the Pauling electronegativity criterion
        p_test = any(
            smact.screening.pauling_test(combo, enegs)
            for combo in itertools.product(*ox_combos)
        )
        return p_test, {"pauling_test": p_test, "electronegativities": enegs}
    except Exception as e:
        return None, {
            "error": f"pauling_check_error: {e}",
            "elements": [str(el) for el in comp.elements] if "comp" in locals() and hasattr(comp, "elements") else [],
        }


def check_geometry_clash(
    structure: Structure,
    clash_ratio_provisional: float = 0.60,  # PROVISIONAL: Minimum distance ratio of sum of radii
) -> Tuple[Optional[bool], Dict[str, Any]]:
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
                r_i = _site_dominant_element(structure[i]).atomic_radius or 1.0
                r_j = _site_dominant_element(structure[j]).atomic_radius or 1.0
                min_allowed = (r_i + r_j) * clash_ratio_provisional
                if dist < min_allowed:
                    return False, {
                        "clash_detected": True,
                        "atom_i": str(_site_dominant_element(structure[i])),
                        "atom_j": str(_site_dominant_element(structure[j])),
                        "distance": float(dist),
                        "min_allowed": float(min_allowed),
                    }
        return True, {"clash_detected": False}
    except AttributeError:
        # API breakage (e.g. removed pymatgen attributes) must fail loudly,
        # never masquerade as a geometry verdict.
        raise
    except Exception as e:
        return None, {"error": f"geometry_clash_check_error: {e}"}


def check_crystal_coordination(
    structure: Structure,
) -> Tuple[Optional[bool], Dict[str, Any]]:
    """Inspect local coordination environments using CrystalNN to ensure sane coordination numbers.

    CrystalNN requires every site to have a majority species, so structures
    with no-majority disordered sites skip coordination explicitly (flagged in
    details) instead of failing: disorder is the norm in this domain, not
    evidence of unphysical geometry. The clash check still applies.
    """
    if not all(_site_has_majority_species(structure[i]) for i in range(len(structure))):
        return True, {
            "coordination_skipped": True,
            "reason": "disordered_no_majority_species",
            "mean_coordination": None,
            "all_sites_sane": None,
        }
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
                    "site_specie": str(_site_dominant_element(structure[i])),
                    "coordination_number": cn,
                }
        return True, {"mean_coordination": float(np.mean(cns)), "all_sites_sane": True}
    except AttributeError:
        # API breakage (e.g. removed pymatgen attributes) must fail loudly,
        # never masquerade as a coordination verdict.
        raise
    except Exception as e:
        # If CrystalNN fails (e.g. ill-defined periodic cell), flag for review
        return None, {"error": f"crystalnn_error: {e}"}


def evaluate_p0(
    formula_or_candidate: Union[str, CandidateMaterial],
    structure: Optional[Structure] = None,
    clash_ratio_provisional: float = 0.60,
) -> P0FilterResult:
    """Run comprehensive P0 static filters and produce an ExistenceState verdict.

    Returns:
        P0FilterResult with existence_state=PLAUSIBLE on pass, FAIL on scientific
        failure, or UNKNOWN on execution/library/data error.
    """
    struct_error = None
    if isinstance(formula_or_candidate, CandidateMaterial):
        formula = formula_or_candidate.formula
        if structure is None and formula_or_candidate.structure_dict:
            try:
                structure = Structure.from_dict(formula_or_candidate.structure_dict)
            except Exception as e:
                struct_error = str(e)
    else:
        formula = formula_or_candidate

    neutrality_ok, neut_details = check_charge_neutrality_smact(formula)
    pauling_ok, pauling_details = check_pauling_electronegativity(formula)

    geom_details: Dict[str, Any] = {}
    coord_details: Dict[str, Any] = {}

    if struct_error is not None:
        geometry_ok: Optional[bool] = None
        geom_details = {"error": f"structure_reconstruction_error: {struct_error}"}
    elif structure is not None:
        geom_ok, geom_details = check_geometry_clash(structure, clash_ratio_provisional)
        coord_ok, coord_details = check_crystal_coordination(structure)
        if geom_ok is None or coord_ok is None:
            geometry_ok = None
        elif not geom_ok or not coord_ok:
            geometry_ok = False
        else:
            geometry_ok = True
    else:
        geometry_ok = True

    checks = (neutrality_ok, pauling_ok, geometry_ok)
    if any(c is None for c in checks):
        passed = False
        verdict = ExistenceState.UNKNOWN
    elif all(c is True for c in checks):
        passed = True
        verdict = ExistenceState.PLAUSIBLE
    else:
        passed = False
        verdict = ExistenceState.FAIL

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
