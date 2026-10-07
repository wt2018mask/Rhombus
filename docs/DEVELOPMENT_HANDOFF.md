# Rhombus Development Handoff

> Generated from `data/development/CURRENT.json`. Normal recovery should read CURRENT first and dereference only what the next action needs.

- Checkpoint: `0034`
- Mode: `RHOMBUS_2_INCREMENTAL_MIGRATION`
- PR: `#191`
- Branch: `worker/r2-phase3-structure-protocol-executors`
- Status: `COMPLETE_PENDING_MERGE`
- Phase: `R2_PHASE3_DOMAIN_MAP_C0_C4`
- Next action: `implement_one_pass_wbm_salex_streaming_overlap_audit_and_build_production_salex_index`
- Blockers: MPTRJ_TRAINING_REPRESENTATION_UNATTESTED, MPTRJ_CANONICAL_SOURCE_SHA256_NOT_FROZEN, MPTRJ_SOURCE_ADAPTER_NOT_IMPLEMENTED, SALEX_PRODUCTION_INDEX_NOT_BUILT, SALEX_STREAMING_OVERLAP_AUDIT_NOT_IMPLEMENTED, FULL_STRUCTURE_MEMBERSHIP_INDEX_NOT_BUILT

## State codes

`PHASE0_CLOSED`, `PHASE1_ARCHITECTURE_FROZEN`, `PHASE2_EVIDENCE_LEDGER_FROZEN`, `PHASE3_DOMAIN_FOUNDATION_STARTED`, `CURRENT_EMPIRICAL_CALIBRATION_NOT_READY`, `SEALED_COHORT_STILL_UNCONSUMED`, `FULL_TRAINING_LINEAGE_AUDIT_REQUIRED`, `MPTRJ_CANONICAL_SOURCE_RESOLVED`, `MPTRJ_TRAINING_REPRESENTATION_UNATTESTED`, `SALEX_SOURCE_BYTE_IDENTITY_VERIFIED`, `SALEX_SOURCE_ADAPTER_READY`, `MEMORY_BOUNDED_MEMBERSHIP_INDEX_BUILDER_V1`, `MEMBERSHIP_INDEX_SOURCE_HASH_BOUND`, `WBM_EXPOSURE_COMPARISON_PROTOCOL_V2_FROZEN`, `STRUCTURE_PROTOCOL_EXECUTORS_V1`, `CANDIDATE_FINGERPRINT_NOT_EXACT_VERDICT`, `STRICT_STRUCTURE_COMPARATOR_AUTHORITATIVE`, `MATBENCH_PROTOTYPE_RUNTIME_BLOB_BOUND`, `EXPOSURE_AUDIT_REMAINS_NOT_READY`, `PRODUCTION_MEMBERSHIP_INDEX_NOT_YET_AUTHORIZED`

## Evidence / policy pointers

- **architecture:** `README.md`
- **policy:** `AGENTS.md`
- **handoff:** `docs/DEVELOPMENT_HANDOFF.md`
- **architecture_freeze:** `data/development/rhombus_v2_architecture_freeze_v1.json`
- **evidence_ledger_freeze:** `data/development/rhombus_v2_evidence_ledger_freeze_v1.json`
- **empirical_calibration_readiness:** `data/development/phase3_domain_calibration_readiness_v1.json`
- **reference_error_source_plan:** `data/development/phase3_reference_error_source_plan_v1.json`
- **wbm_source_contract:** `data/development/phase3_wbm_source_contract_v1.json`
- **wbm_file_freeze:** `data/development/phase3_wbm_file_freeze_v1.json`
- **wbm_exposure_audit_contract:** `rhombus/domain/wbm_audit.py`
- **wbm_exposure_audit_input_plan:** `data/development/phase3_wbm_exposure_audit_input_plan_v1.json`
- **training_exposure_audit_basis:** `data/development/phase3_training_exposure_audit_basis_v1.json`
- **training_snapshot_resolution:** `data/development/phase3_training_snapshot_resolution_v1.json`
- **membership_index_contract:** `rhombus/domain/membership.py`
- **membership_index_plan:** `data/development/phase3_membership_index_plan_v1.json`
- **salex_archive_identity:** `data/development/phase3_salex_archive_identity_v1.json`
- **salex_archive_file_verification:** `data/development/phase3_salex_archive_file_verification_v1.json`
- **salex_source_adapter:** `data/development/phase3_salex_source_adapter_v1.json`
- **salex_source_adapter_code:** `rhombus/domain/salex.py`
- **structure_protocol_executors:** `data/development/phase3_structure_protocol_executors_v1.json`
- **structure_protocol_code:** `rhombus/domain/structure_protocols.py`
- **structure_protocol_ci:** `.github/workflows/r2-phase3-structure-protocols.yml`

Historical checkpoint events are audit-only and are not read during normal recovery.
