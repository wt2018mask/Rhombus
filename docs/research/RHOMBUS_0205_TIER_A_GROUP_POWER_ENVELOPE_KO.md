# RHOMBUS 0205 — Tier A chemsys group-risk feasibility envelope

2026-10-31 — Non-executable, metadata-only research diagnostic.

## Scientific task and claim boundary

The intended Tier A observable is the nondirectional discrete DFT-NEB image energy span max(E_images)-min(E_images), **not** a directional forward activation barrier, 3D BVSE percolation, ionic diffusion, or conductivity.

This module asks how many *accepted independent test groups* would be required even in the ideal case of zero severe errors. No ground-truth energy values or model predictions are loaded. The candidate grouping is by canonical chemical-system string. **Chemical-system grouping is not evidence of independent prototypes, independent sources, or independence from any MACE training set.**

For n IID Bernoulli group-level failures and zero observed failures, a one-sided exact Clopper–Pearson bound with confidence C is U=1-(1-C)^(1/n). When n=0, the conditional risk is UNDEFINED, not zero. For a hypothetical target r, the minimum independent accepted zero-failure groups required are ceil(log(1-C)/log(1-r)). This best-case sensitivity is not actual statistical power, not a scientific qualification, and not a measured risk confidence interval.

## Owner-provided source, metadata only

Owner ZIP: 68,583,182 bytes, SHA256 b7a99d89337902e9e1da319f57547170fdb132bf15bf6ffef03a0140e2207d7f. The verified allowlist index contains 1,681 Li-hop edges and 277 chemical systems. No DFT/BVSE target index fields, XYZ energies, forces, or held-out predictions were read, decoded, or scored. Matching the owner ZIP hash does not prove publisher authenticity.

Current conflict-purge *candidate* keeps Train 619 edges / 110 chemsys; Val 165 / 64; Test 220 / 103. It excludes 677 published train/val edges to remove cross-split exact chemsys strings, without moving any edge between published splits. The stricter *sensitivity-only* alternative keeps only groups already exclusive to one published split; this leaves **6 test chemsys**.

## Illustration only: 95% one-sided confidence, 5% severe-error risk threshold

These numbers are NOT owner-approved, not a benchmark freeze, and not a performance measurement.

- Minimum independent accepted groups, **if all show zero severe errors**: **59**.
- Four-group TRAIN cost pilot: optimistic upper bound about **52.7%** even if all four accepted with zero severe errors. Not sufficient for a 5% risk claim.
- 103-group test candidate: optimistic upper bound about **2.87%** at full coverage with zero severe errors, and at least 59/103 = **57.3% group coverage** required even for the best-case 5% threshold.
- Six-group strict-exclusive test sensitivity: optimistic upper bound about **39.3%** even at full coverage, so cannot establish the 5% threshold under this test population.

Group coverage is different from edge coverage. Within-group correlated hops cannot be counted as independent statistical units. Selection and per-group aggregation rules must be preregistered before seeing sealed reference results. These optimistic calculations become invalid as evidence if IID independence, model training disjointness, or preselection assumptions do not hold; actual severe errors would require more accepted groups.

## Executable surface, tests, blockers

- rhombus/benchmark/tier_a_power_envelope.py: recompute and authenticate the complete metadata-only group registry before best-case arithmetic; reject counts, split, or target injection.
- scripts/benchmark/analyze_tier_a_power_envelope_0205.py: require explicit registry and hypothetical risk/confidence values; reject overwrites, duplicate JSON keys, and nonfinite parameters.
- tests/test_tier_a_power_envelope_0205.py: analytical inverse and boundary checks, group semantics and tamper tests, CLI fail-closed tests.

The executable output is only a hypothetical planning sensitivity. All science/production/real-model execution is prohibited. Model checkpoints, reference comparability, numerical NEB protocol, equal-budget caps, source independence, training overlap, and owner run approval remain unresolved.

**Disposition:** TIER_A_PROTOCOL_DRAFT_READY; TIER_B_NOT_FROZEN; BENCHMARK_NOT_FROZEN; SCIENTIFIC_NO_GO_ABSTAIN; execution_authorized=false.
