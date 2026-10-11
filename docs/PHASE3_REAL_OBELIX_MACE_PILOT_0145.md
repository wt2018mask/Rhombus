# 0145 — actual public OBELiX TRAIN crystal geometry + pinned MACE CPU calculation pilot

This is the **first new material-level physical inference execution expansion**, not another metadata-only science readiness exercise. The pinned public [NRC-Mila/OBELiX](https://github.com/NRC-Mila/OBELiX) original commit `4eaac889809dd489e3bae468c45d5c0e02b9147a` has 599 source records, with 478 official TRAIN and 121 original public TEST (TEST never selected, parsed as geometry, evaluated, tuned or included in the pilot results). Full source CIF bytes are checked against the existing attested original-source hashes.

The pilot independently downloads the already full-SHA256-verified original [MACE-MPA-0 medium](https://github.com/ACEsuit/mace-foundations/releases/tag/mace_mpa_0) 79,462,305-byte asset, rejects mismatched bytes, and uses actual `MACECalculator` on **up to 50** deterministically eligible original TRAIN-only structures on a GitHub CPU (finite per-run wall-clock budget). Each calculation obtains real MACE **single-point total potential energy and atomic forces**, recording correct units (eV, eV/Å) and preflight structure/validation status, with per-row failures counted. It does not predict conductivity or run MD. MODEL LICENSE: original publisher's release terms still apply; this workflow never redistributes checkpoint weights, raw source CIF, private experimental measurements or other source rows.

## Public-record admission (no speculative materials)

- Source commit and official TRAIN indices are checked by the existing intake; the official public TEST count is checked but not sent to the geometry parser or calculator.
- Only original `Match` structure links are eligible for *exact-CIF source-match* first. `Close Match` is excluded (phase ambiguity); `No Match` has no model geometry.
- Verify each original raw CIF against `cif_content_sha256`, finite cell and coordinates, fully ordered sites, 3D periodicity, at least one Li atom, 2–96 atoms, and minimum interatomic distance at least 0.65 Å. A successful CIF parse is **not** proof that the structure exactly reproduces the experimental phase; OBELiX publishes randomized geometry variants.
- All rows are counted as either screening admission or a reason for exclusion, but inference selection is deterministic: lowest atom count then original TRAIN ID, max 50.
- Any candidate lacking source CIF or qualified atomistic geometry is marked ineligible, never auto-repaired or silently treated as a model success.
- Original processed conductivity includes censored/surrogate records: **these are NOT model predictions or experimental comparison targets**. Source TRAIN metadata may be used for a later scientifically controlled bulk/total/temperature-specific transport evaluation, not this energy/force pilot.

## Real experimental score boundary

`number_of_actual_mace_singlepoint_structures` = count of successfully executed distinct original TRAIN structures, **NOT independently verified physical experimental samples**. Actual experimental conductivity MAE/RMSE, room-temperature conductivity classification accuracy, blind generalization or MD tracer conductivity **remain null and unclaimed**.

## Extensibility

The exact-head original three-structure CPU pilot passed (39 TRAIN geometry-eligible, 3/3 actual MACE energy+forces). Expand the *same pinned verified execution* to up to 50 deterministic eligible structures on CPU (actual eligible count may be less); next add hash-separated batch evaluation and temperature-aware transport physics, then separate finite-temperature MD and experimental paper/truth adjudication. Heavy MD should run in bounded resumable Kaggle jobs only after exact source/model hashes and compute authorization. Never infer success from metadata-only CI.

The Red Team P0 independent blind cohort, exact MACE selected training-frame manifest and independent experimental statistics **remain BLOCKED**; `science_go=false`.
