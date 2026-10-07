# Rhombus Development Handoff

> Generated from `data/development/CURRENT.json`. Normal recovery should read CURRENT first and dereference only what the next action needs.

- Checkpoint: `0026`
- Mode: `RHOMBUS_2_INCREMENTAL_MIGRATION`
- PR: `#181`
- Branch: `worker/readme-scientific-control-plane-sync`
- Status: `COMPLETE_PENDING_MERGE`
- Phase: `R2_PHASE3_DOMAIN_MAP_C0_C4`
- Next action: `run_stream_verification_for_wbm_initial_structures_and_freeze_mptrj_salex_audit_basis`
- Blockers: WBM_STRUCTURE_FILE_SHA256_NOT_YET_CAPTURED, MPTRJ_SALEX_AUDIT_BASIS_NOT_YET_FROZEN, EXPOSURE_FINGERPRINT_AND_NEAR_DUPLICATE_PROTOCOLS_NOT_YET_FROZEN

## State codes

`P1_DEV_3_KEEP_FOR_P2`, `P2_DEV_COHORT_3_AUTHORIZED`, `LLZO_P0_INDETERMINATE`, `P2_SPECIES_NORMALIZATION_FIXED`, `P2_ASE_UNIT_BUG_DIAGNOSED`, `OLD_GAMMA_P2_FAIL_INVALID_PROTOCOL_EXECUTION`, `P2_PROTOCOL_V3_ASE_UNITS_CORRECTED`, `P2_THRESHOLDS_UNCHANGED`, `GAMMA_P2_CORRECTED_STABILITY_PASS`, `LEGACY_B6_B8_DEFERRED`, `CANDIDATE_SUPPLY_V2_PAUSED`, `AI_FIRST_NAMING_CONTRACT_FROZEN`, `RHOMBUS_V2_NAMESPACE_BOOTSTRAPPED`, `LIBH4_HEX_P2_SEMANTIC_GATE_CONFLICT`, `LIBH4_ORTHO_P2_STABILITY_FAIL`, `P2_MOBILE_COUNT_GATE_ORDER_BUG_IDENTIFIED`, `P2_EVAL_POLICY_V2_HOST_FIRST_MOBILE_NEUTRAL`, `HEX_LIBH4_P2_STABILITY_FAIL_AUTHORITATIVE`, `TRANSPORT_REGIME_ADMISSION_CONTRACT_V1`, `GAMMA_ONLY_TRANSPORT_REGIME_AUTHORIZED`, `LIBH4_BOTH_EXCLUDED_BY_STABILITY_FAIL`, `LLZO_EXCLUDED_BY_UPSTREAM_INDETERMINATE`, `AI_FIRST_CLASSIFY_TRANSPORT_REGIME_ADAPTER`, `GAMMA_TRANSPORT_REGIME_INDETERMINATE`, `GAMMA_POINT_NONDIFFUSIVE_NOT_CLAIMABLE`, `GAMMA_TRANSPORT_EVIDENCE_EXTENSION_REQUIRED`, `R2_FAST_CI_TIER_ADDED`, `FAST_FIRST_CANONICAL_PREMERGE_POLICY`, `GAMMA_TRANSPORT_EXTENSION_AUTHORIZED`, `GAMMA_EXTENSION_ONE_SHOT_FULL_8000`, `GAMMA_EXTENSION_KAGGLE_PREFERRED`, `KAGGLE_REMOTE_FAIL_CLOSED_IF_UNCONFIGURED`, `GAMMA_TRANSPORT_EXTENSION_GITHUB_CPU_ACTIVE`, `KAGGLE_FALLBACK_MANUAL_ONLY`, `PHASE0_CLOSED`, `GAMMA_EXTENSION_STABILITY_PASS`, `GAMMA_TRANSPORT_REGIME_NONDIFFUSIVE`, `GAMMA_TRANSPORT_SUFFICIENCY_MET`, `PHASE1_ARCHITECTURE_FREEZE_NEXT`, `MCP_PLUGIN_COMPATIBILITY_DESIGN_TARGET`, `PHASE1_ARCHITECTURE_FROZEN`, `PUBLIC_TOOL_CONTRACT_V1_FROZEN`, `MCP_PLUGIN_SEMANTICS_BOUND`, `SEALED_QUALIFICATION_REMAINS_UNCONSUMED`, `PHASE2_EVIDENCE_LEDGER_NEXT`, `V2_EVIDENCE_SCHEMAS_V1`, `V2_TYPED_IDENTITY_BINDINGS_V1`, `LEGACY_B5_EVIDENCE_ADAPTERS_V1`, `V2_PASS_CLAIMS_FAIL_CLOSED`, `LEGACY_COMPATIBILITY_CONTEXT_V1`, `MODEL_IDENTITY_EXACT_CHECKPOINT_BINDING`, `MODEL_LINEAGE_BOUND_FROM_FROZEN_LEDGER`, `PROTOCOL_IDENTITY_BOUND_FROM_EXPLICIT_LEGACY_RECORDS`, `PHASE2_EVIDENCE_LEDGER_FROZEN`, `LEGACY_ADAPTER_COVERAGE_ALLOWLISTED`, `UNSUPPORTED_LEGACY_SCHEMA_FAILS_CLOSED`, `PHASE3_DOMAIN_MAP_NEXT`, `PHASE3_DOMAIN_FOUNDATION_STARTED`, `COMPOSITION_DESCRIPTOR_V1`, `ELEMENT_COVERAGE_PREFLIGHT_V1`, `SUPPORTED_ELEMENTS_REMAIN_UNQUALIFIED`, `UNSUPPORTED_ELEMENTS_FAR_OOD`, `STRUCTURAL_DESCRIPTOR_BASELINE_V1`, `TRANSPARENT_STRUCTURAL_DISTANCE_V1`, `DISTANCE_NOT_OOD_CLASSIFIER`, `REFERENCE_COVERAGE_PROFILE_V1`, `EVIDENCE_BOUND_DISTANCE_CALIBRATION_V1`, `DOMAIN_VERDICT_REQUIRES_MATCHING_REFERENCE_SET`, `NO_THRESHOLD_INFERENCE_FROM_SMALL_KNOWN_MATERIAL_COHORT`, `K_NEIGHBOR_REFERENCE_COVERAGE_V1`, `DOMAIN_PROMOTION_REQUIRES_MIN_REFERENCE_COUNT`, `DOMAIN_PROMOTION_REQUIRES_LEAVE_GROUP_OUT_VALIDATION`, `EMPIRICAL_ERROR_DISTANCE_OBSERVATION_V1`, `DOMAIN_CALIBRATION_READINESS_GATE_V1`, `CURRENT_EMPIRICAL_CALIBRATION_NOT_READY`, `NO_THRESHOLD_FABRICATION`, `REFERENCE_ERROR_SOURCE_CANDIDATE_IDENTIFIED`, `WBM_NOT_YET_ADMITTED`, `MPTRJ_SALEX_REJECTED_AS_INDEPENDENT_CALIBRATION`, `SEALED_COHORT_STILL_UNCONSUMED`, `WBM_SOURCE_CONTRACT_V1`, `WBM_OUTCOME_BLIND_SAMPLING_V1`, `WBM_STRATIFIED_BY_SUBSTITUTION_STEP`, `WBM_EMPIRICAL_CALIBRATION_NOT_YET_AUTHORIZED`, `WBM_REMOTE_FILE_IDENTITIES_FROZEN`, `WBM_DOWNLOAD_MD5_VERIFICATION_REQUIRED`, `WBM_LOCAL_SHA256_RECORD_REQUIRED`, `WBM_EXPOSURE_AUDIT_FAIL_CLOSED`, `WBM_FROZEN_FILE_VERIFIER_V1`, `WBM_SMALL_FILE_REMOTE_VERIFICATION_WORKFLOW`, `WBM_SHA256_CAPTURE_PENDING`, `WBM_MACE_PREDICTION_SHA256_VERIFIED`, `WBM_SUMMARY_SHA256_VERIFIED`, `WBM_LARGE_FILE_STREAM_HASHING_READY`, `WBM_EXPOSURE_AUDIT_INPUT_CONTRACT_V1`, `WBM_EXPOSURE_AUDIT_INPUTS_NOT_READY`, `FULL_TRAINING_LINEAGE_AUDIT_REQUIRED`, `README_SCIENTIFIC_CONTROL_PLANE_DIRECTION_SYNCED`, `RHOMBUS_REFERENCE_DOMAIN_FOR_GENERIC_VERIFICATION_CONTRACTS`, `GENERIC_CORE_EXTRACTION_DEFERRED_UNTIL_CROSS_DOMAIN_VALIDATION`

## Evidence / policy pointers

- **architecture:** `README.md`
- **policy:** `AGENTS.md`
- **handoff:** `docs/DEVELOPMENT_HANDOFF.md`
- **p1_evidence:** `data/benchmarks/known_material/b5_p1_real_evidence_v1.json`
- **p2_authorization:** `data/benchmarks/known_material/b5_p2_authorization_v1.json`
- **p2_implementation:** `rudeus/mlip/p2.py`
- **ai_first_naming:** `docs/AI_FIRST_NAMING.md`
- **canonical_package:** `rhombus/__init__.py`
- **p2_unit_diagnostic:** `data/benchmarks/known_material/b5_p2_ase_units_diagnostic_v1.json`
- **p2_config:** `config.yaml`
- **p2_corrected_pilot_evidence:** `data/benchmarks/known_material/b5_p2_corrected_pilot_evidence_v1.json`
- **remaining_libh4_p2_workflow:** `.github/workflows/b5-dev-remaining-libh4-p2.yml`
- **remaining_libh4_p2_evidence:** `data/benchmarks/known_material/b5_p2_remaining_libh4_evidence_v1.json`
- **p2_semantic_recheck_workflow:** `.github/workflows/b5-dev-hex-libh4-p2-recheck.yml`
- **hex_libh4_semantic_recheck_evidence:** `data/benchmarks/known_material/b5_p2_hex_libh4_semantic_recheck_v1.json`
- **transport_regime_admission:** `rhombus/transport/admission.py`
- **transport_regime_authorization:** `data/benchmarks/known_material/b5_transport_regime_authorization_v1.json`
- **gamma_transport_regime_workflow:** `.github/workflows/r2-gamma-transport-regime.yml`
- **transport_regime_classifier:** `rhombus/transport/classify.py`
- **gamma_transport_regime_evidence:** `data/benchmarks/known_material/b5_gamma_transport_regime_evidence_v1.json`
- **fast_ci_workflow:** `.github/workflows/r2-fast-ci.yml`
- **gamma_transport_extension_authorization:** `data/benchmarks/known_material/b5_gamma_transport_extension_authorization_v1.json`
- **transport_extension_contract:** `rhombus/transport/extension.py`
- **gamma_transport_extension_kaggle_workflow:** `.github/workflows/r2-gamma-transport-extension-kaggle.yml`
- **gamma_transport_extension_kaggle_driver:** `scripts/kaggle/gamma_transport_extension.py`
- **gamma_transport_extension_github_workflow:** `.github/workflows/r2-gamma-transport-extension-github.yml`
- **gamma_transport_extension_evidence:** `data/benchmarks/known_material/b5_gamma_transport_extension_evidence_v1.json`
- **phase0_closure:** `data/development/phase0_closure_v1.json`
- **architecture_freeze:** `data/development/rhombus_v2_architecture_freeze_v1.json`
- **evidence_schema:** `rhombus/evidence/schema.py`
- **evidence_identity:** `rhombus/evidence/identity.py`
- **legacy_evidence_adapter:** `rhombus/evidence/legacy.py`
- **evidence_registry:** `rhombus/evidence/registry.py`
- **evidence_ledger_freeze:** `data/development/rhombus_v2_evidence_ledger_freeze_v1.json`
- **domain_descriptor:** `rhombus/domain/descriptors.py`
- **domain_applicability:** `rhombus/domain/applicability.py`
- **structural_distance:** `rhombus/domain/distance.py`
- **domain_coverage:** `rhombus/domain/coverage.py`
- **domain_calibration:** `rhombus/domain/calibration.py`
- **empirical_calibration_readiness:** `data/development/phase3_domain_calibration_readiness_v1.json`
- **empirical_calibration_contract:** `rhombus/domain/empirical.py`
- **reference_error_source_plan:** `data/development/phase3_reference_error_source_plan_v1.json`
- **wbm_source_contract:** `data/development/phase3_wbm_source_contract_v1.json`
- **wbm_sampling_contract:** `rhombus/domain/wbm.py`
- **wbm_file_freeze:** `data/development/phase3_wbm_file_freeze_v1.json`
- **wbm_exposure_audit_contract:** `rhombus/domain/wbm_audit.py`
- **wbm_file_verifier:** `scripts/development/verify_wbm_file.py`
- **wbm_file_verify_workflow:** `.github/workflows/r2-phase3-wbm-file-verify.yml`
- **wbm_mace_prediction_file_verification:** `data/development/phase3_wbm_mace_prediction_file_verification_v1.json`
- **wbm_summary_file_verification:** `data/development/phase3_wbm_summary_file_verification_v1.json`
- **wbm_exposure_audit_input_plan:** `data/development/phase3_wbm_exposure_audit_input_plan_v1.json`

Historical checkpoint events are audit-only and are not read during normal recovery.
