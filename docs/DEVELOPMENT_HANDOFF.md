# Rhombus Development Handoff

> Generated from `data/development/CURRENT.json`. Normal recovery should read CURRENT first and dereference only what the next action needs.

- Checkpoint: `0006`
- Mode: `RHOMBUS_2_INCREMENTAL_MIGRATION`
- PR: `#161`
- Branch: `worker/r2-transport-regime-admission`
- Status: `COMPLETE_PENDING_MERGE`
- Phase: `R2_PHASE0_B5_DIAGNOSTIC`
- Next action: `run_gamma_transport_regime_classification`
- Blockers: none

## State codes

`P1_DEV_3_KEEP_FOR_P2`, `P2_DEV_COHORT_3_AUTHORIZED`, `LLZO_P0_INDETERMINATE`, `P2_SPECIES_NORMALIZATION_FIXED`, `P2_ASE_UNIT_BUG_DIAGNOSED`, `OLD_GAMMA_P2_FAIL_INVALID_PROTOCOL_EXECUTION`, `P2_PROTOCOL_V3_ASE_UNITS_CORRECTED`, `P2_THRESHOLDS_UNCHANGED`, `GAMMA_P2_CORRECTED_STABILITY_PASS`, `LEGACY_B6_B8_DEFERRED`, `CANDIDATE_SUPPLY_V2_PAUSED`, `AI_FIRST_NAMING_CONTRACT_FROZEN`, `RHOMBUS_V2_NAMESPACE_BOOTSTRAPPED`, `LIBH4_HEX_P2_SEMANTIC_GATE_CONFLICT`, `LIBH4_ORTHO_P2_STABILITY_FAIL`, `P2_MOBILE_COUNT_GATE_ORDER_BUG_IDENTIFIED`, `P2_EVAL_POLICY_V2_HOST_FIRST_MOBILE_NEUTRAL`, `HEX_LIBH4_P2_STABILITY_FAIL_AUTHORITATIVE`, `TRANSPORT_REGIME_ADMISSION_CONTRACT_V1`, `GAMMA_ONLY_TRANSPORT_REGIME_AUTHORIZED`, `LIBH4_BOTH_EXCLUDED_BY_STABILITY_FAIL`, `LLZO_EXCLUDED_BY_UPSTREAM_INDETERMINATE`

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

Historical checkpoint events are audit-only and are not read during normal recovery.
