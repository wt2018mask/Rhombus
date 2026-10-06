# Rhombus Development Handoff

> Generated from `data/development/CURRENT.json`. Normal recovery should read CURRENT first and dereference only what the next action needs.

- Checkpoint: `0001`
- Mode: `RHOMBUS_2_INCREMENTAL_MIGRATION`
- PR: `#156`
- Branch: `worker/r2-continuity-bootstrap`
- Status: `COMPLETE_PENDING_MERGE`
- Phase: `R2_PHASE0_B5_DIAGNOSTIC`
- Next action: `diagnose_gamma_p2_abort`
- Blockers: none

## State codes

`P1_DEV_3_KEEP_FOR_P2`, `P2_DEV_COHORT_3_AUTHORIZED`, `LLZO_P0_INDETERMINATE`, `GAMMA_P2_EQUIL_EXPLOSIVE_ABORT`, `P2_SPECIES_NORMALIZATION_FIXED`, `P2_ABORT_PROVENANCE_PERSISTED`, `LEGACY_B6_B8_DEFERRED`, `CANDIDATE_SUPPLY_V2_PAUSED`

## Evidence / policy pointers

- **architecture:** `README.md`
- **policy:** `AGENTS.md`
- **handoff:** `docs/DEVELOPMENT_HANDOFF.md`
- **p1_evidence:** `data/benchmarks/known_material/b5_p1_real_evidence_v1.json`
- **p2_authorization:** `data/benchmarks/known_material/b5_p2_authorization_v1.json`
- **p2_implementation:** `rudeus/mlip/p2.py`

Historical checkpoint events are audit-only and are not read during normal recovery.
