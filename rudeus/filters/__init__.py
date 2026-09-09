"""Heuristic, electrostatic, and dynamical filters for candidate pre-screening.

RESPONSIBILITIES:
- P0 Static Filters: Fast composition and structure sanity checks (charge neutrality via SMACT,
  electronegativity checks, minimum interatomic distances, packing density).
- F2 Bond Valence Site Energy (BVSE, probationary): Geometric/electrostatic percolation
  pathway estimation. Tagged as probationary until validated on the empirical benchmark.
- F3 Diffusive-Regime Validator: Verifies that trajectories are genuinely within the diffusive
  regime using mobile-ion-only mean squared displacement (MSD) and the non-Gaussian parameter
  alpha_2 (to distinguish true continuous diffusion from jump-cage rattling or lattice melting).

CONSTRAINTS & DESIGN NOTES:
- Any numeric threshold (e.g. MSD slope cutoff, alpha_2 cutoff, Lindemann criterion, BVSE barrier)
  must remain explicitly tagged PROVISIONAL in code and config until calibrated against real data.
- Log-log slope ≈ 1 is necessary but not sufficient evidence of diffusive motion (it cannot
  distinguish sustained hopping from caging/vibration/transient motion alone).
- F2 BVSE output is under PROBATION status and must never independently set existence_state to SUPPORTED.
"""

from rudeus.filters.f3_diffusive import (
    compute_msd_curve,
    compute_non_gaussian_alpha2,
    compute_species_resolved_msd,
    fit_log_log_slope,
    validate_diffusive_regime,
    DiffusiveValidationResult,
)
from rudeus.filters.p0 import (
    evaluate_p0,
    check_charge_neutrality_smact,
    check_pauling_electronegativity,
    check_geometry_clash,
    P0FilterResult,
)
from rudeus.filters.bvse import (
    evaluate_f2_bvse,
    estimate_bvse_barrier,
    BVSEFilterResult,
)

__all__ = [
    "compute_msd_curve",
    "compute_non_gaussian_alpha2",
    "compute_species_resolved_msd",
    "fit_log_log_slope",
    "validate_diffusive_regime",
    "DiffusiveValidationResult",
    "evaluate_p0",
    "check_charge_neutrality_smact",
    "check_pauling_electronegativity",
    "check_geometry_clash",
    "P0FilterResult",
    "evaluate_f2_bvse",
    "estimate_bvse_barrier",
    "BVSEFilterResult",
]
