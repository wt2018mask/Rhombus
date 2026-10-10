# Phase 3 scientific completion — A: training-lineage acquisition readiness (checkpoint 0125)

**Primary red-team finding:** RT-P0-02. This is a scientific/provenance
roadblock, **not** another general security-audit iteration.

## What can now be used

Run from the Rhombus repository (Python 3.11, no provider, GPU, Kaggle,
download, optional runtime credentials, or paid service):

```powershell
py -3.11 -m rhombus.domain.lineage_readiness
py -3.11 -m rhombus.domain.lineage_readiness --manifest-json .\trusted\lineage-declaration.json
```

The optional input must be a bounded JSON object that follows the already
versioned `rhombus-checkpoint-training-lineage-v1` declaration shape in
`rhombus/domain/training_manifest.py`. Without an input, the command emits
the complete, machine-readable missing-evidence checklist. With a declaration,
it reports which requirements are *declared but unverified* and which still
lack artifact bytes. It prints only requirement codes/statuses, not selected
material IDs or frame contents.

Model target: MACE-MPA-0 medium, frozen publisher checkpoint metadata.
Required independent evidence includes: independent full-model-file hash;
MPTrj and sAlex full original-source observations; exact model-selected
frame count and SHA-bound selected-frame artifact; bound preprocessing and
energy-label artifact bytes; role-separated, authenticated observations,
publisher and lineage-auditor receipts; independent host-owned trust keys
and host-approved preprocessing/label digests.

`assess_training_lineage_readiness` also accepts **trusted-host inputs**
(`artifacts`, `receipts`, `trusted_issuers`,
`trusted_rule_bindings`) when integrated by an independently provisioned
host. Only when every required input is present does it call the existing
strict `verify_training_lineage_manifest`; synthetic receipts never
authenticate external provenance. CLI JSON cannot import trust anchors
from the same untrusted declaration, by design.

## Scientific/nonclaims

The output retains `scientific_verdict=INDETERMINATE` and
`unseen_generalization_authorized=false` in every outcome. A successfully
authenticated external review package can at most become
`READY_FOR_SEPARATE_MEMBERSHIP_AUDIT`. It does **not** prove training
membership, unseen generalization, independent blinded performance or
the validity of legacy public B3 held-out identities.

No selected MACE-MPA-0 training frames or independently provisioned
external trust anchors have been acquired by checkpoint 0125.
No 12.2GiB MPTrj source or 79MiB model file is downloaded by the readiness
planner, and no Kaggle job is dispatched.

## Ordered next step: scientific C2

Once this check emits a stable set of action codes, implement
the *independently grouped* LOCO/LOFO evaluation runner. It must prevent
cross-group training/test leakage; retain FAILED/UNKNOWN/INDETERMINATE/
NONDIFFUSIVE at material level; and withhold calibrated OOD/generalization
claims until independent sample/lineage evidence exists.

Evidence: `data/development/phase3_science_lineage_0125_evidence_v1.json`.
Regressions: `tests/test_phase3_training_lineage_readiness.py`.
