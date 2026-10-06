# Rhombus / Rudeus coding-agent policy

This file defines durable operating policy for coding agents. Detailed scientific
behavior belongs in the repository's authoritative contracts and design notes.

## Mandatory recovery before editing

Before any coding task, recover project state from the repository rather than
from chat memory:

1. inspect current `main` and open pull requests;
2. read `data/development/CURRENT.json`;
3. run `python scripts/development/continuity.py check`;
4. read `docs/DEVELOPMENT_HANDOFF.md` and `README.md`;
5. resume from `current_frontier.next_action` unless newer repository state
   proves that action obsolete.

The machine-readable CURRENT record and highest-index immutable checkpoint must
remain JSON-equivalent. If they disagree, stop and repair continuity before
scientific development.

## Mandatory task-completion checkpoint

Every pull request is also a development handoff. Before a task may be declared
complete or merged:

- update `data/development/CURRENT.json`;
- add exactly one new immutable
  `data/development/checkpoints/<index>-<id>.json`;
- regenerate `docs/DEVELOPMENT_HANDOFF.md` with
  `python scripts/development/continuity.py write`;
- preserve all older checkpoint files unchanged;
- pass the Development Continuity workflow.

A future agent must be able to continue the project from repository state alone,
even if the previous chat disappears completely.

## Inspect before editing

- Inspect the relevant source, tests, existing diffs, contracts, and provenance
  before changing code.
- Treat the repository as the current authority; do not assume a task
  description is newer than the checked-in implementation or contracts.
- Identify existing interfaces, schemas, state transitions, and invariants
  before implementing a change.

## Smallest robust patch

- Make the smallest scoped change that satisfies the task.
- Preserve unrelated user changes and do not perform speculative refactors.
- Do not redesign architecture unless explicitly requested and justified by a
  current repository contract.

## Scientific evidence semantics

- Preserve independent `existence_state`, `dynamic_state`, and
  `transport_state` fields. Never collapse scientific evidence into one scalar
  fitness or score.
- Operational success is not a scientific verdict and must never be promoted
  automatically.
- Distinguish measured, simulated, estimated, extrapolated, diagnostic,
  benchmark-only, and unsupported values.
- Preserve temperature-specific evidence; do not average away conditions needed
  for activation-barrier or conductivity interpretation.
- Do not promote `UNKNOWN` or `INDETERMINATE` without an authorized evidence
  path.
- Scientific thresholds remain `PROVISIONAL` unless the repository contains
  explicit calibration or qualification evidence.

## Historical and frozen evidence

- Treat historical P2/P2.5 and other explicitly frozen artifacts as immutable
  evidence.
- Do not silently rerun, rewrite, delete, or replace frozen cohort results.
- Corrections require new versioned artifacts or explicit repair records.
- P3 analysis must not overwrite the scientific meaning of P2/P2.5 results.
- Artifact paths, hashes, protocol versions, and bindings are part of
  provenance.

## Append-only and content-addressed provenance

- Git is a major system of record, but Git durability is distinct from
  scientific qualification.
- Do not mutate content-addressed artifacts in place. Append-only records use
  new hashes and records rather than silent replacement.
- Preserve exact task, input, and output ancestry.
- Where the contract requires it, aggregate reports must be reproducible from
  retained row-level evidence.

## Generated audit artifacts

- Review provenance before committing generated JSON, NPZ, CSV, or report
  artifacts.
- Do not delete or overwrite historical audit artifacts.
- Preserve required schema, version, hash, and source metadata.
- Diagnostic artifacts do not authorize activation, P1 eligibility, downstream
  scientific claims, or production use unless an explicit authorization field
  or contract says so.

## Tests and verification

- Add or update focused tests when behavior changes.
- Run focused tests before reporting success; run broader relevant regression
  tests when practical.
- Report tests that were not run and why.
- Never weaken or rewrite a test merely to make a failure disappear.
- Passing tests alone do not establish success when scientific or provenance
  invariants remain unchecked.

## Git safety

- Do not commit or push unless explicitly requested; never force-push by
  default.
- Never embed credentials, tokens, or secrets.
- Inspect staged files before committing and keep unrelated changes out of a
  commit.
- Generated scientific outputs require provenance validation before commit.

## Execution boundaries

- Use local controlled execution where current execution contracts support it.
- Do not infer remote execution capability merely from Kaggle/Colab code or
  documentation.
- Keep remote or GPU workers restartable and stateless where current contracts
  require it, with deterministic sharding and resume semantics.
- Do not add Redis, Celery, databases, persistent queues, daemons, or
  orchestration services without an explicitly authorized architecture
  decision.

## Resource budget

- Keep the project operable without paid cloud infrastructure, paid APIs, new
  paid subscriptions, or required hardware upgrades unless the user explicitly
  authorizes a new budget decision.
- Prefer existing local resources, already-authorized subscriptions, and
  verified free/preemptible compute.
- Do not introduce an external service merely to simplify orchestration when
  the repository's stateless/Git-based architecture can satisfy the
  requirement.
- Verify free-provider availability and capability rather than assuming them.

## Scientific architecture constraints

- Use the official OBELiX leakage-aware/grouped split. Never silently
  reshuffle, regenerate, or repartition it.
- Keep LiIon as a distinct empirical source and retain its temperature
  dimension; do not merge its rows into OBELiX.
- MatterGen, BoTorch, Bayesian optimization, and active-learning loops remain
  deferred until the repository's calibration/qualification gate explicitly
  authorizes them.
- Do not reintroduce BVSE into active discovery execution. Legacy BVSE code or
  APIs may remain for compatibility, history, or negative-reference
  benchmarking; their presence is not authorization for discovery use.
- Follow current MLIP design and configuration contracts. Do not hard-code
  stale model lists into this policy.
- Same-seed ensembles of the same base MLIP must not be used as independent
  scientific confirmation unless a newer explicit scientific contract
  supersedes this rule.

## Authority and conflicts

- Keep durable operating policy here, not historical narrative or temporary
  task instructions.
- If this file conflicts with a newer explicit repository contract, stop and
  report the conflict rather than guessing.
- Do not copy old benchmark statistics, dates, corrupted symbols, or historical
  failure narratives into this file.
