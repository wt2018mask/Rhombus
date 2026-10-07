# Rhombus Development Handoff

> Generated from `data/development/CURRENT.json`. Normal recovery should read CURRENT first and dereference only what the next action needs.

- Checkpoint: `0038`
- Mode: `RHOMBUS_2_INCREMENTAL_MIGRATION`
- PR: `#195`
- Branch: `worker/r2-phase3-salex-kaggle-credential-blocker`
- Status: `COMPLETE_PENDING_MERGE`
- Phase: `R2_PHASE3_DOMAIN_MAP_C0_C4`
- Next action: `configure_kaggle_actions_secret_then_rerun_failed_exact_commit_controller_37704726464`
- Blockers: MPTRJ_TRAINING_REPRESENTATION_UNATTESTED, MPTRJ_CANONICAL_SOURCE_SHA256_NOT_FROZEN, MPTRJ_SOURCE_ADAPTER_NOT_IMPLEMENTED, KAGGLE_ACTIONS_CREDENTIAL_NOT_CONFIGURED, KAGGLE_CPU_FULL_RUN_NOT_YET_COMPLETED, SALEX_PRODUCTION_INDEX_NOT_BUILT, FULL_STRUCTURE_MEMBERSHIP_INDEX_NOT_BUILT

## State codes

`PHASE0_CLOSED`, `PHASE1_ARCHITECTURE_FROZEN`, `PHASE2_EVIDENCE_LEDGER_FROZEN`, `PHASE3_DOMAIN_FOUNDATION_STARTED`, `SEALED_COHORT_STILL_UNCONSUMED`, `FULL_TRAINING_LINEAGE_AUDIT_REQUIRED`, `MPTRJ_TRAINING_REPRESENTATION_UNATTESTED`, `SALEX_SOURCE_BYTE_IDENTITY_VERIFIED`, `SALEX_SOURCE_ADAPTER_READY`, `MEMORY_BOUNDED_MEMBERSHIP_INDEX_BUILDER_V1`, `STRUCTURE_PROTOCOL_EXECUTORS_V1`, `WBM_SALEX_ONE_PASS_PRODUCTION_ENGINE_V1`, `REAL_SOURCE_SALEX_THROUGHPUT_PILOT_CAPTURED`, `KAGGLE_CPU_SELECTED_FOR_SALEX_FULL_RUN`, `EXPOSURE_AUDIT_REMAINS_NOT_READY`, `KAGGLE_CPU_ONE_SHOT_AUTOMATION_V1`, `SALEX_FULL_RUN_AUTHORIZED`, `FULL_SALEX_RUN_NOT_YET_COMPLETE`, `KAGGLE_CPU_MERGE_LAUNCH_ARMED`, `KAGGLE_ONE_SHOT_LAUNCH_DISPATCHED`, `KAGGLE_CONTROLLER_AUTHORIZATION_PASSED`, `KAGGLE_REMOTE_CREDENTIAL_BLOCKED`

## Evidence / policy pointers

- **architecture:** `README.md`
- **policy:** `AGENTS.md`
- **handoff:** `docs/DEVELOPMENT_HANDOFF.md`
- **training_snapshot_resolution:** `data/development/phase3_training_snapshot_resolution_v1.json`
- **training_exposure_audit_basis:** `data/development/phase3_training_exposure_audit_basis_v1.json`
- **wbm_exposure_audit_input_plan:** `data/development/phase3_wbm_exposure_audit_input_plan_v1.json`
- **membership_index_contract:** `rhombus/domain/membership.py`
- **membership_index_plan:** `data/development/phase3_membership_index_plan_v1.json`
- **salex_source_adapter:** `data/development/phase3_salex_source_adapter_v1.json`
- **salex_source_adapter_code:** `rhombus/domain/salex.py`
- **structure_protocol_executors:** `data/development/phase3_structure_protocol_executors_v1.json`
- **overlap_auditor_code:** `rhombus/domain/overlap.py`
- **salex_production_runner:** `scripts/development/run_salex_wbm_overlap.py`
- **salex_production_request:** `data/development/phase3_salex_production_request_v1.json`
- **salex_production_plan:** `data/development/phase3_salex_production_execution_plan_v1.json`
- **salex_production_workflow:** `.github/workflows/r2-phase3-salex-production.yml`
- **salex_throughput_pilot_evidence:** `data/development/phase3_salex_throughput_pilot_evidence_v1.json`
- **salex_kaggle_full_run_request:** `data/development/phase3_salex_kaggle_full_run_request_v1.json`
- **salex_kaggle_full_run_plan:** `data/development/phase3_salex_kaggle_full_run_plan_v1.json`
- **salex_kaggle_kernel_driver:** `scripts/kaggle/salex_phase3_full_run.py`
- **salex_kaggle_controller_workflow:** `.github/workflows/r2-phase3-salex-kaggle-full-run.yml`
- **salex_kaggle_launch_request:** `data/development/phase3_salex_kaggle_launch_v1.json`
- **salex_kaggle_launch_workflow:** `.github/workflows/r2-phase3-salex-kaggle-launch.yml`
- **salex_kaggle_dispatch_blocker:** `data/development/phase3_salex_kaggle_dispatch_blocker_v1.json`

Historical checkpoint events are audit-only and are not read during normal recovery.
