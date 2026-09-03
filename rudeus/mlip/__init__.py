"""Machine Learning Interatomic Potential (MLIP) evaluation stages (P1-P3).

RESPONSIBILITIES:
- P1 Relaxation: Athermal structural relaxation, equilibrium volume determination,
  and energy-above-hull estimation.
- P2 Finite-Temperature Stability: Short NPT/NVT molecular dynamics simulations to test
  for spontaneous decomposition, lattice collapse, or amorphization (dynamic_state evaluation).
- P3 Arrhenius Fitting: Temperature-dependent molecular dynamics (e.g. 600K-1000K) to extract
  diffusion coefficients and activation barriers via Arrhenius fitting (transport_state evaluation).

MODEL GOVERNANCE & CONSTRAINTS:
- Default primary MLIP is `mace_mp("medium-mpa-0")` (MIT license), NOT MACE-MP-0.
- Cross-checking (X-stage) requires a secondary MLIP trained on a fundamentally distinct dataset
  distribution (SevenNet or CHGNet).
- BANNED: Same-seed or pseudo-ensembles of the same base model architecture/data are strictly
  forbidden. Correlated failure modes previously yielded false confidence in prior project iterations.
"""
