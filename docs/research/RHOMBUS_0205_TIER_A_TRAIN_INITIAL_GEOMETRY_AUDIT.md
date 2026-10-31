# RHOMBUS 0205 — TRAIN initial XYZ geometry-only audit

2026-10-31. Additive scientific **preflight** only on existing draft PR #377; no model run, scores or qualification.

The task is the nondirectional single-Li-hop **discrete NEB image energy span** `max(E_images)-min(E_images)`. It is NOT a forward activation barrier, global SoftBV 3D percolation, diffusivity, or ionic conductivity.

Only the previously SHA256-pinned four **TRAIN** `*_init.xyz` members of the owner-provided LiTraj ZIP are read. The ZIP is rehashed using the same file descriptor that supplies its members. No `*_relaxed.xyz`, validation/test members, index target columns, or numerical energy/force/stress metadata values are parsed. Initial XYZ *does contain* energy/force fields, which are explicitly ignored. Raw bytes are read solely for identity verification and geometry decoding.

| TRAIN edge | Images | Atoms / image | Li | Largest direct Cartesian successive-image atom displacement (Å) |
|---|---:|---:|---:|---:|
| mp-777350_8_5_1_-1_0 | 5 | 135 | 39 | 0.9761 |
| mp-1186148_1_2_0_0_1 | 5 | 143 | 89 | 0.7591 |
| mp-765219_4_7_0_0_0 | 5 | 89 | 9 | 1.2051 |
| mp-758202_0_1_1_1_0 | 5 | 111 | 15 | 0.8947 |

All four passed **structural parser** checks for five images, identical fixed-cell, PBC in all axes, constant atom species order and finite Cartesian coordinates. The direct displacements are NOT periodic-minimum-image transport lengths or saddle estimates. No arbitrary physical cutoff was used. This evidence does NOT establish path/charge/chemistry correctness, NEB convergence, DFT fidelity, model independence, publisher authenticity or performance superiority.

Files: `rhombus/benchmark/tier_a_initial_geometry.py`, `scripts/benchmark/audit_tier_a_initial_geometry_0205.py` and negative tests. Runner is non-executable, only writes a new diagnostic JSON file, and refuses overwrite. Existing independent science status remains `SCIENTIFIC_NO_GO_ABSTAIN`, `BENCHMARK_NOT_FROZEN` and Tier B not frozen. Separate owner authorization is required for any MLIP/NEB/DFT/MD computation.

Next: freeze the numerical NEB configuration and matched total cost ceilings with justification; independently verify model environments and training overlap; then consider a separately approved tiny TRAIN-only execution pilot. Evaluate risk/coverage on a truly sealed eligible cohort only after pre-registration, never from these four TRAIN structural checks.
