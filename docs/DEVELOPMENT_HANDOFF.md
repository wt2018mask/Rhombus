# Rhombus Development Handoff

> Generated from `data/development/CURRENT.json`. Normal recovery should read CURRENT first and dereference only what the next action needs.

- Checkpoint: `0119`
- Mode: `RHOMBUS_2_INCREMENTAL_MIGRATION`
- PR: `#283`
- Branch: `worker/redteam-remediation-batch-a`
- Status: `COMPLETE_PENDING_MERGE`
- Phase: `R2_PHASE3_DOMAIN_MAP_C0_C4`
- Next action: `Review PR283 Batch A; require exact-head Fast/Continuity/Wave2; retain science NO-GO and no-submit; obtain atomic consumption, admin protection and external lineage/reproduction evidence.`
- Blockers: MPTRJ_TRAINING_REPRESENTATION_UNATTESTED, MPTRJ_CANONICAL_SOURCE_SHA256_NOT_FROZEN, MPTRJ_SOURCE_ADAPTER_NOT_REAL_SOURCE_VALIDATED, REDTEAM_P0_LEGACY_PUBLIC_HELDOUT_NOT_INDEPENDENT, REDTEAM_P0_EXACT_MACE_MPA0_SELECTED_TRAINING_FRAMES_UNATTESTED, REDTEAM_P0_MATERIAL_LEVEL_VALIDATION_UNDERPOWERED, REDTEAM_P1_GITHUB_PROTECTION_ENFORCEMENT_ADMIN_UNVERIFIED, REDTEAM_P1_KAGGLE_REAL_SOURCE_CRASH_RESUME_UNPROVEN, KAGGLE_ATOMIC_CONSUMPTION_UNAVAILABLE

## State codes

`PHASE3_SCIENTIFIC_NO_GO`, `LEGACY_PUBLIC_HELDOUT_NOT_INDEPENDENT`, `EXACT_MODEL_TRAINING_LINEAGE_UNATTESTED`, `MATERIAL_LEVEL_VALIDATION_UNDERPOWERED`, `BATCH_A_ENGINEERING_IMPLEMENTED_INDEPENDENT_ACCEPTANCE_PENDING`, `SALEX_NEW_SUBMISSIONS_DISABLED`, `OPAQUE_EXPORTS_DENIED`, `REPRODUCIBILITY_PARTIAL`

## Evidence / policy pointers

- **architecture:** `README.md`
- **policy:** `AGENTS.md`
- **handoff:** `docs/DEVELOPMENT_HANDOFF.md`
- **redteam_remediation_register:** `data/development/phase3_redteam_remediation_register_v1.json`
- **redteam_remediation_plan:** `docs/PHASE3_REDTEAM_REMEDIATION_PLAN_V1.md`
- **batch_a_evidence:** `data/development/phase3_redteam_batch_a_evidence_v1.json`
- **batch_a_review:** `docs/PHASE3_REDTEAM_REMEDIATION_BATCH_A_V1.md`
- **kaggle_launch_policy:** `data/development/phase3_salex_kaggle_launch_v1.json`
- **kaggle_controller:** `.github/workflows/r2-phase3-salex-kaggle-full-run.yml`
- **artifact_scanner:** `scripts/security/scan_outgoing_artifacts.py`
- **transport_numerics:** `rudeus/mlip/p3_transport.py`
- **runtime_provenance:** `rhombus/evidence/runtime_provenance.py`

Historical checkpoint events are audit-only and are not read during normal recovery.
