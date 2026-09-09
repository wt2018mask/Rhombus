"""F2 Bond Valence Site Energy (BVSE) Percolation Scoring.

CRITICAL ARCHITECTURAL CONTRACT:
This filter is under PROBATIONARY status pending the Step B benchmark enrichment gate.
Its output must be usable, but it must NEVER independently set existence_state to SUPPORTED
or transport_state to DIFFUSIVE. It can only contribute evidence tagged as PROBATION.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from pymatgen.core import Structure, Element
from rudeus.schema import CandidateMaterial, EvidenceEvent, ExistenceState, TransportState


@dataclass(frozen=True)
class BVSEFilterResult:
    """Result of F2 BVSE percolation scoring.

    Attributes:
        score: Percolation score (lower barrier / higher connectivity = higher score).
        percolation_barrier_ev: Estimated percolation activation energy barrier in eV (PROVISIONAL).
        is_percolating: True if estimated barrier is below the provisional threshold.
        status: ALWAYS 'PROBATION'. Never sets state to SUPPORTED independently.
        details: Structural details and parameters.
        evidence_event: EvidenceEvent record with level='F2_PROBATION'.
    """
    score: float
    percolation_barrier_ev: float
    is_percolating: bool
    status: str
    details: Dict[str, Any]
    evidence_event: EvidenceEvent


# Standard Bond Valence Parameters (Brown & Altermatt / Brese & O'Keeffe) for Li-anion pairs
BV_PARAMETERS = {
    ("Li", "O"): 1.393,
    ("Li", "S"): 1.830,
    ("Li", "Se"): 1.950,
    ("Li", "Te"): 2.120,
    ("Li", "F"): 1.220,
    ("Li", "Cl"): 1.700,
    ("Li", "Br"): 1.840,
    ("Li", "I"): 2.050,
}
DEFAULT_B = 0.370  # Standard universal bond valence softness parameter (Angstrom)


def estimate_bvse_barrier(
    structure: Structure,
    mobile_ion: str = "Li",
    target_valence: float = 1.0,
    max_radius: float = 8.0,
    barrier_cutoff_ev_provisional: float = 0.60,  # PROVISIONAL: Maximum acceptable barrier
) -> Tuple[float, float, bool, Dict[str, Any]]:
    """Estimate the BVSE percolation barrier and score for a structure.

    Args:
        structure: Crystal structure to evaluate.
        mobile_ion: Target diffusing species (default: "Li").
        target_valence: Formal valence of mobile ion (default: 1.0 for Li+).
        max_radius: Neighbor cutoff distance in Angstroms.
        barrier_cutoff_ev_provisional: Provisional cutoff for percolation barrier (eV).

    Returns:
        (score, barrier_ev, is_percolating, details)
    """
    mobile_indices = [
        i for i, site in enumerate(structure) if site.specie.symbol == mobile_ion
    ]

    if not mobile_indices:
        return 0.0, 99.0, False, {"error": f"No {mobile_ion} sites found in structure"}

    bvs_list = []
    min_inter_mobile_dists = []

    # Compute bond valence sums for each mobile ion site
    for idx in mobile_indices:
        site = structure[idx]
        neighbors = structure.get_neighbors(site, r=max_radius)
        bvs = 0.0

        for neighbor in neighbors:
            anion_sym = neighbor.specie.symbol
            pair = (mobile_ion, anion_sym)
            if pair in BV_PARAMETERS:
                r0 = BV_PARAMETERS[pair]
                d = neighbor.nn_distance
                bvs += np.exp((r0 - d) / DEFAULT_B)

        bvs_list.append(bvs)

    # Calculate inter-mobile ion bottlenecks
    all_mobile_sites = [structure[i] for i in mobile_indices]
    if len(all_mobile_sites) > 1:
        for i in range(len(all_mobile_sites)):
            dists = [
                all_mobile_sites[i].distance(all_mobile_sites[j])
                for j in range(len(all_mobile_sites))
                if i != j
            ]
            if dists:
                min_inter_mobile_dists.append(min(dists))
    else:
        min_inter_mobile_dists = [5.0]

    # BVSE activation barrier approximation:
    # Deviation from ideal valence + penalty for wide inter-site bottleneck jumps
    mean_bvs = float(np.mean(bvs_list)) if bvs_list else target_valence
    valence_mismatch = float(np.mean([abs(b - target_valence) for b in bvs_list]))
    bottleneck_dist = float(np.mean(min_inter_mobile_dists)) if min_inter_mobile_dists else 4.0

    # Empirical barrier proxy:
    # E_barrier ~ 0.5 * |Delta V| + 0.15 * (d_bottleneck - 2.8)^+ (PROVISIONAL calibration)
    jump_penalty = max(0.0, bottleneck_dist - 2.8) * 0.15
    estimated_barrier = float(0.40 * valence_mismatch + jump_penalty + 0.15)

    # Bounded between 0.1 eV and 3.0 eV
    estimated_barrier = min(3.0, max(0.10, estimated_barrier))

    is_percolating = estimated_barrier <= barrier_cutoff_ev_provisional

    # Score: monotonic transform where higher is better (e.g. 1 / (1 + barrier))
    score = float(1.0 / (1.0 + estimated_barrier))

    details = {
        "mean_bvs": mean_bvs,
        "valence_mismatch": valence_mismatch,
        "bottleneck_distance": bottleneck_dist,
        "barrier_cutoff_provisional": barrier_cutoff_ev_provisional,
        "n_mobile_sites": len(mobile_indices),
    }

    return score, estimated_barrier, is_percolating, details


def evaluate_f2_bvse(
    structure: Structure,
    mobile_ion: str = "Li",
    barrier_cutoff_ev_provisional: float = 0.60,
) -> BVSEFilterResult:
    """Evaluate F2 BVSE percolation filter.

    CRITICAL INVARIANT:
    Always returns status='PROBATION'. This function NEVER promotes candidates to SUPPORTED.
    """
    score, barrier, percolating, details = estimate_bvse_barrier(
        structure=structure,
        mobile_ion=mobile_ion,
        barrier_cutoff_ev_provisional=barrier_cutoff_ev_provisional,
    )

    event = EvidenceEvent(
        level="F2_PROBATION",
        method="bvse_percolation_barrier_proxy",
        conditions={
            "mobile_ion": mobile_ion,
            "barrier_cutoff_ev_provisional": barrier_cutoff_ev_provisional,
            "status": "PROBATION",
        },
        uncertainty=0.15,
        source="f2_bvse_filter",
        artifact_hash="",
        model_or_data_version="bvse_v1_probation",
    )

    return BVSEFilterResult(
        score=score,
        percolation_barrier_ev=barrier,
        is_percolating=percolating,
        status="PROBATION",  # Explicitly locked to PROBATION
        details=details,
        evidence_event=event,
    )
