# Phase 3 science C2 — material-group exclusion diagnostics (checkpoint 0126)

**Scientific completion focus:** RT-P0-01/03 and RT-P1-05, Stage C2 in
the Rhombus 2.0 README. This is not another security feature.

## Run a real program command, without model/compute calls

From the repository root with Python 3.11 (no network required):

```powershell
py -3.11 -m rhombus.qualification.group_exclusion --evaluation-json data/examples/phase3_c2_group_exclusion_synthetic_v1.json
```

The included example contains only `SYNTHETIC_TEST_ONLY` public materials.
It contains four material-level outcomes in two LOCO groups. A correct
synthetic expectation is **2/4 (50%) diagnostic accuracy**, with one
FAILED operating error and one UNKNOWN included in the denominator.
The output is deterministic JSON with per-group/overall totals, full outcome
counts, operational failure counts and input SHA256. It does **not** call
a model, DFT, MACE, Kaggle or an external service.

## Required input and science checks

`rhombus-group-exclusion-evaluation-v1` fields:

- `scope`: **PUBLIC_DIAGNOSTIC_ONLY**; secret or externally blind cohorts
  are explicitly unsupported by this entrypoint
- `method`: `LOCO` (leave one cluster out) or `LOFO` (leave one family out)
- `model_family_id`: declared shared family, not proof of independent models
- `folds`: at least two groups, with exact `held_out_group_id`,
  `declared_training_group_ids` and `declared_training_material_ids`;
  every training list must equal *all other group IDs/material IDs*,
  excluding exactly the held-out group; duplicate material identities
  across folds are invalid
- `fold_model_sha256`: one 64-character lowercase SHA256 per fold,
  distinct across folds. It is **declared metadata**, not a verified
  cryptographic observation or training history
- `materials`: one observation per independently identified material,
  with `observed_truth` restricted to POSITIVE/NEGATIVE/BORDERLINE,
  `predicted_outcome` one of the seven conservative scientific outcomes,
  and `operational_status` one of SUCCEEDED/ERROR/CANCELLED

A FAILED/CANCELLED operation cannot claim a conclusive scientific prediction.
FAILED, UNKNOWN, INDETERMINATE and NONDIFFUSIVE predictions are never
dropped from the material denominator, and no repeated trajectories can
increase sample size. Per-group scores and overall scores count **materials,
not timesteps or trajectories**. Input is limited to 1 MiB, 512 groups and
10,000 materials in the direct library API.

## Crucial distinction: declared exclusion vs real model independence

The report proves only *internal consistency of the declarations*. It
does **not** prove that the model's real training excluded any of the
held-out structures or structurally equivalent records. The input has
public diagnostic truth available from the start and is therefore **not
a new independently blinded B1 trial**.

Accordingly:
- `actual_model_training_exclusion_independently_attested=false`
- `observed_materials_independently_sampled=false`
- `calibrated_error_estimate_available=false`
- `scientific_verdict=INDETERMINATE`
- `claim_authorized=false`
- `unseen_generalization_authorized=false`

Before any independently defensible C2 qualification, connect the outputs
to a publisher/independent-auditor training lineage from scientific A,
new externally sealed material identities/truth from B1, an independently
chosen evaluation cohort, and an explicit statistical precision/power
review. C3/C4 calibration must use separate enough materials/groups and
cannot be inferred from these artificial fixtures.

Unit contracts: `tests/test_phase3_c2_group_exclusion.py`.
Checkpoints and nonclaims:
`data/development/phase3_science_c2_0126_evidence_v1.json`.

**Next planned development C:** add a physically conservative material-level
transport adequacy review (MD window/blocks, event rarity, extrapolation
bounds, and honest failed/non-diffusive outcomes), rather than using these
diagnostic scores as validated 300K ionic conductivity.
