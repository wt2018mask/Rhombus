# Rhombus Development Handoff

> Generated from `data/development/CURRENT.json`. Normal recovery should read CURRENT first and dereference only what the next action needs.

- Checkpoint: `0047`
- Mode: `RHOMBUS_2_INCREMENTAL_MIGRATION`
- PR: `#209`
- Branch: `worker/r2-ai-task-proposal-deny-by-default-v1`
- Status: `COMPLETE_PENDING_MERGE`
- Phase: `R2_PHASE3_DOMAIN_MAP_C0_C4`
- Next action: `await_running_kaggle_salex_production_result_then_verify_frozen_wbm_and_salex_outputs`
- Blockers: MPTRJ_TRAINING_REPRESENTATION_UNATTESTED, MPTRJ_CANONICAL_SOURCE_SHA256_NOT_FROZEN, MPTRJ_SOURCE_ADAPTER_NOT_IMPLEMENTED, KAGGLE_WBM_FROZEN_SOURCE_DOWNLOADED_EMPTY, KAGGLE_CPU_FULL_RUN_NOT_YET_COMPLETED, SALEX_PRODUCTION_INDEX_NOT_BUILT, FULL_STRUCTURE_MEMBERSHIP_INDEX_NOT_BUILT

## State codes

`PHASE0_CLOSED`, `PHASE1_ARCHITECTURE_FROZEN`, `PHASE2_EVIDENCE_LEDGER_FROZEN`, `PHASE3_DOMAIN_FOUNDATION_STARTED`, `SEALED_COHORT_STILL_UNCONSUMED`, `FULL_TRAINING_LINEAGE_AUDIT_REQUIRED`, `MPTRJ_TRAINING_REPRESENTATION_UNATTESTED`, `SALEX_SOURCE_BYTE_IDENTITY_VERIFIED`, `SALEX_SOURCE_ADAPTER_READY`, `MEMORY_BOUNDED_MEMBERSHIP_INDEX_BUILDER_V1`, `STRUCTURE_PROTOCOL_EXECUTORS_V1`, `WBM_SALEX_ONE_PASS_PRODUCTION_ENGINE_V1`, `REAL_SOURCE_SALEX_THROUGHPUT_PILOT_CAPTURED`, `KAGGLE_CPU_SELECTED_FOR_SALEX_FULL_RUN`, `EXPOSURE_AUDIT_REMAINS_NOT_READY`, `KAGGLE_CPU_ONE_SHOT_AUTOMATION_V1`, `SALEX_FULL_RUN_AUTHORIZED`, `FULL_SALEX_RUN_NOT_YET_COMPLETE`, `KAGGLE_CPU_MERGE_LAUNCH_ARMED`, `KAGGLE_ONE_SHOT_LAUNCH_DISPATCHED`, `KAGGLE_CONTROLLER_AUTHORIZATION_PASSED`, `KAGGLE_ACTIONS_CREDENTIAL_VERIFIED`, `KAGGLE_PRIVATE_REQUEST_DATASET_CREATED`, `KAGGLE_CPU_KERNEL_SUBMISSION_CONFIRMED`, `KAGGLE_CPU_KERNEL_EXECUTION_ENTERED`, `KAGGLE_RUNTIME_EXACT_REQUEST_RECOVERY_VERIFIED`, `KAGGLE_MATBENCH_CHECKOUT_VERIFIED`, `KAGGLE_WBM_EMPTY_SOURCE_REJECTED`, `KAGGLE_WBM_SOURCE_FALLBACK_RECOVERY_ARMED`, `AI_TOOLS_READONLY_EVIDENCE_GATEWAY_V1`, `AI_TOOL_FUNCTION_CALLING_SCHEMA_V1`, `AI_TOOL_SCIENTIFIC_CLAIMS_FAIL_CLOSED`, `AI_TOOLS_MCP_V2_STDIO_ADAPTER_V1`, `AI_TOOL_OFFICIAL_MCP_CLIENT_CONTRACT_V1`, `KAGGLE_PRODUCTION_DEFAULT_DENY_GATE`, `KAGGLE_PRODUCTION_ENVIRONMENT_REVIEW_REQUIRED`, `KAGGLE_ERROR_LOG_REDACTION_V1`, `AI_TOOL_KAGGLE_EXECUTION_NOT_EXPOSED`, `SECRET_HISTORY_AND_ARTIFACT_AUDIT_WORKFLOW`, `AI_TOOLS_DOMAIN_ELEMENT_PREFLIGHT_V1`, `AI_TOOLS_STRUCTURE_REPRESENTATION_PREFLIGHT_V1`, `AI_TOOLS_MCP_READONLY_ALLOWLIST_THREE_V1`, `AI_TOOL_EVIDENCE_MANIFEST_V1`, `AI_TASK_PROPOSAL_RESOURCE_BOUNDS_V1`

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
- **salex_kaggle_kernel_conflict:** `data/development/phase3_salex_kaggle_kernel_conflict_v1.json`
- **salex_kaggle_input_failure:** `data/development/phase3_salex_kaggle_input_failure_v1.json`
- **salex_kaggle_wbm_source_failure:** `data/development/phase3_salex_kaggle_wbm_source_failure_v1.json`
- **ai_tools_guide:** `docs/AI_TOOLS_READONLY_V1.md`
- **ai_tools_code:** `rhombus/tools/evidence_query.py`
- **ai_mcp_guide:** `docs/AI_TOOLS_MCP_STDIO_V1.md`
- **ai_mcp_code:** `rhombus/tools/mcp_server.py`
- **security_redactor:** `scripts/security/redact_stream.py`
- **security_credential_auditor:** `scripts/security/audit_credential_history.py`
- **security_operations:** `docs/SECURITY_OPERATIONS.md`
- **ai_analysis_guide:** `docs/AI_TOOLS_ANALYSIS_V1.md`
- **ai_analysis_code:** `rhombus/tools/read_only_analysis.py`
- **ai_analysis_tests:** `tests/test_r2_ai_analysis.py`
- **ai_manifest_code:** `rhombus/tools/evidence_manifest.py`
- **ai_manifest_guide:** `docs/AI_TOOLS_MANIFEST_V1.md`
- **ai_manifest_tests:** `tests/test_r2_ai_manifest.py`
- **ai_task_proposal_code:** `rhombus/tools/task_proposal.py`
- **ai_task_proposal_guide:** `docs/AI_TOOLS_TASK_PROPOSAL_V1.md`
- **ai_task_proposal_tests:** `tests/test_r2_ai_task_proposal.py`

Historical checkpoint events are audit-only and are not read during normal recovery.
