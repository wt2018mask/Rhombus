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
"""
