# Wave 2 Contract Lock

Base: `33daf3a4bf6a53c0718019711c88c22a4564d90a`

Wave 1 status: `WAVE1_BLOCKER_CLEAN`

## Canonical pipeline

`E → G → P0 → P1 → P2 → P2.5 → P3 → X → N → S → Application → Final Claim Vector → OUT`

P3 is not final. Historical M6-A/M6-B evidence, the original M6-B validation failure, append-only reconciliation, the frozen 100 allocation, the five canonical P2.5 NONDIFFUSIVE outcomes, and M7 default-OFF status remain immutable.

## Shared frozen surfaces

The following are frozen during parallel lane implementation:

- `rudeus/science/contracts.py`
- `rudeus/science/claims.py`
- `rudeus/execution/contracts.py`
- `rudeus/schema.py`

If a lane proves that a shared change is required, it must return `SHARED_SCHEMA_DELTA` and stop depending on that change until it is applied serially.

## Integration-owner-only surfaces

- `rudeus/science/evidence.py`
- `rudeus/science/pipeline_handoff.py`

Generic trajectory, transport, statistics, execution backend/runtime/launcher/local/Kaggle backend, receipt, and code-bundle modules are read-only dependencies unless a serial integration decision explicitly reassigns ownership.

## Lane 1 — P3 scientific closure

Branch: `worker/wave2-p3-closure`

Owned production files:

- `rudeus/science/p3.py`
- `rudeus/mlip/p3_transport.py`
- new `rudeus/science/p3_series.py`

Owned tests:

- `tests/test_p3.py`
- `tests/test_p3_data_contract.py`
- `tests/test_p3_scientific_slice.py`
- `tests/test_p3_transport.py`
- `tests/test_p3_uncertainty_contract.py`
- new `tests/test_p3_series.py`

Exit condition: preserve per-temperature and replicate identity; add D(T), uncertainty, Arrhenius/regime/activation-energy, extrapolation, sigma_NE semantics and collective-transport limitations; keep qualification unresolved without applicable held-out evidence; emit P3 assessments usable by X without making P3 final or rewriting P2/P2.5 history.

## Lane 2 — Scientific follow-up + scheduler

Branch: `worker/wave2-followup-scheduler`

Owned production files:

- `rudeus/science/followups.py`
- new `rudeus/execution/scheduler.py`

Owned tests:

- `tests/test_followups.py`
- new `tests/test_scheduler.py`

Exit condition: Scientific Engine owns evidence sufficiency and scientific follow-up TaskSpecs. Scheduler owns only backend, ordering, batching/sharding, resource assignment, and infrastructure retries as new attempts of the same task. Scientific FAIL is never retried to seek a different answer.

## Lane 3 — X/N/S/Application productionization

Branch: `worker/wave2-downstream-production`

Owned production file:

- `rudeus/science/downstream.py`

Owned test:

- `tests/test_downstream.py`

Exit condition: X binds qualified independent evidence without selecting an unqualified model; N preserves incomplete reference coverage as UNKNOWN; S remains criterion-level with no scalar synthesizability score; Application remains versioned, applicability-aware and species-neutral; OUT stays conservative and provenance-bound.

## Lane 4 — Canonical E2E + release infrastructure

Branch: `worker/wave2-e2e-release`

Owned production/integration files:

- `rudeus/science/evidence.py`
- `rudeus/science/pipeline_handoff.py`
- new `rudeus/science/pipeline_release.py`
- new `.github/workflows/wave2-synthetic-e2e.yml`

Owned tests:

- `tests/test_pipeline_handoff.py`
- `tests/test_task_binding.py`
- `tests/test_evidence.py`
- new `tests/test_wave2_synthetic_e2e.py`

Exit condition: deterministic synthetic canonical path from Candidate Supply through OUT with bound TaskSpec/ExecutionAttempt/ArtifactManifest ancestry and immutable receipts. Missing evidence remains UNKNOWN or INDETERMINATE; no fabricated PASS evidence.

## Write-set collision proof

Pairwise lane write intersections are empty for all six pairs:

- Lane 1 × Lane 2: EMPTY
- Lane 1 × Lane 3: EMPTY
- Lane 1 × Lane 4: EMPTY
- Lane 2 × Lane 3: EMPTY
- Lane 2 × Lane 4: EMPTY
- Lane 3 × Lane 4: EMPTY

## Dependency DAG

Contract Lock precedes all lanes.

Lanes 1, 2 and 3 are independent against frozen shared interfaces.

Lane 4 may build its shell in parallel, but final wiring depends on outputs from Lanes 1–3.

Any required shared-schema change is a hard serial dependency and must be applied before affected lane work continues.

## Merge order

1. Lane 1 — P3
2. Lane 2 — follow-up/scheduler
3. Lane 3 — downstream
4. Lane 4 — E2E/release integration

Each merge is followed by focused/affected CI. After all four merge, run full GitHub regression. Local broad pytest is not the default gate.

## Lane-count decision

Four lanes minimize expected total completion time. Three combines independent large scopes and lengthens the critical path. Five splits tightly coupled P3 or E2E work and increases interface/testing/merge coordination cost.

