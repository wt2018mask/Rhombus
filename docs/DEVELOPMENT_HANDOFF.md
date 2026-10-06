# Rhombus Development Handoff

> **Canonical recovery entry point.** This file is generated from `data/development/CURRENT.json`. Do not edit it by hand.

- **Schema:** `rhombus-development-continuity-v1`
- **Checkpoint:** `0001` / `r2-0001-continuity-bootstrap`
- **Recorded date:** 2026-10-07
- **Canonical branch:** `main`
- **Project mode:** `RHOMBUS_2_INCREMENTAL_MIGRATION`
- **Architecture:** `README.md`

## Integration state

- Task branch: `worker/r2-continuity-bootstrap`
- Base main SHA: `d66c530e18ad365db483c3aaa1244346ed88f1af`
- Pull request: `PENDING`
- Task status: `COMPLETE_PENDING_MERGE`

## Last completed task

**Bootstrap durable cross-chat development continuity**

Make repository state sufficient to resume development even if chat context disappears.

- Previous completed PR: `#155`
- Previous main SHA: `d66c530e18ad365db483c3aaa1244346ed88f1af`

Outcomes:
- README is the canonical Rhombus 2.0 roadmap.
- A machine-readable CURRENT development state is canonical.
- Each completed task appends an immutable checkpoint.
- The human-readable handoff is deterministically rendered from CURRENT.
- CI requires every pull request to carry a synchronized continuity checkpoint.
- AGENTS.md requires agents to recover from repository state before editing.

## Current frontier

**Program:** Rhombus 2.0 Phase 0 — close B5 diagnostic evidence before v2 core implementation

Scientific state:
- Real P1 completed for gamma-LiAlO2 and two LiBH4 phase units; all three were KEEP_FOR_P2.
- Exact three-unit DEV P2 cohort is authorized; cubic Al-stabilized LLZO remains P0 INDETERMINATE and is not authorized downstream.
- Real gamma-LiAlO2 P2 pilot reproducibly terminates during equilibration through explosive-step before production.
- Oxidation-state species normalization was fixed so Li+ is recognized as mobile Li.
- P2 numerical-abort provenance now persists phase, MD step, sample index, step jump, threshold, temperature, energy, maximum force, and finite-state evidence.
- Legacy B6-B8 qualification is deferred until the Rhombus 2.0 scientific architecture intended for qualification is frozen.

**Next exact action:**

Inspect the latest persisted gamma-LiAlO2 P2 numerical_abort evidence and classify the equilibration termination as physical instability, initial-condition/protocol issue, model-domain behavior, or numerical artifact without tuning thresholds to force a PASS.

**Blocked on:**
- Nothing currently recorded.

## Critical invariants

- GitHub main is the source of truth; chat history is not.
- Missing evidence is never PASS.
- Operational ERROR, representation failure, model-domain limitation, insufficient evidence, and physical material FAIL remain distinct.
- P2 PASS does not imply diffusion; only qualified transport-regime evidence may authorize downstream transport quantification.
- Historical evidence is immutable; corrections create new versioned records.
- Current v1 repository-visible HELD_OUT must not be used as strong-blind qualification evidence.
- Future qualification cohort identity/truth must remain externally sealed until the frozen one-shot evaluation.
- Candidate Supply v2 production remains paused.
- Do not repeatedly poll GitHub Actions. After the user reports completion, verify the relevant run once and act from that result.

## Canonical recovery files

- `README.md`
- `AGENTS.md`
- `data/development/CURRENT.json`
- `docs/DEVELOPMENT_HANDOFF.md`
- `data/benchmarks/known_material/b5_p1_real_evidence_v1.json`
- `data/benchmarks/known_material/b5_p2_authorization_v1.json`

## Recovery protocol

1. Fetch current main and open pull requests before editing.
2. Read data/development/CURRENT.json first.
3. Verify CURRENT is JSON-equivalent to the highest-index immutable checkpoint in data/development/checkpoints/.
4. Read docs/DEVELOPMENT_HANDOFF.md and README.md for human context and architecture.
5. Inspect only the workflow/PR explicitly referenced by CURRENT unless new repository state requires otherwise.
6. Resume from current_frontier.next_action; do not reconstruct state from chat memory.
7. Before declaring the next task complete, update CURRENT, append one new immutable checkpoint, regenerate DEVELOPMENT_HANDOFF.md, and pass Development Continuity CI.

## Completion contract

A development task is not complete until repository continuity state is synchronized and CI-valid.

Every pull request must update:
- `data/development/CURRENT.json`
- `docs/DEVELOPMENT_HANDOFF.md`
- `one newly added data/development/checkpoints/*.json file`

If a future chat has no prior context, the repository files above are sufficient to resume from this checkpoint.
