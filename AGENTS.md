# Rhombus / Rudeus coding-agent policy

This file defines durable operating policy for coding agents. Detailed scientific
behavior belongs in the repository's authoritative contracts and design notes.

## Mandatory recovery before editing

Recover from the repository, not chat memory:

1. inspect current `main` and open pull requests;
2. read only `data/development/CURRENT.json` first;
3. run `python scripts/development/continuity.py check`;
4. use `python scripts/development/continuity.py resolve --ref KEY` to retrieve
   current or inherited evidence pointers needed for `CURRENT.frontier.next_action`.

`resolve` returns the complete effective state; `resolve --baseline` returns
the complete prior checkpoint metadata. Resolution verifies the versioned,
SHA-256-bound snapshot automatically. Missing or invalid snapshots stop recovery;
do not substitute the compact delta. Baseline snapshots and their descriptors
are immutable. Lists accumulate and inherited evidence keys cannot be rewritten.

Do not read historical checkpoints during normal recovery. They are audit-only
delta events. README and the generated handoff are optional unless CURRENT
points to them for the task.

## Mandatory task-completion checkpoint

Before merge:

- keep `CURRENT.json` compact (CI tests enforce a size bound);
- add exactly one small append-only checkpoint event;
- regenerate `docs/DEVELOPMENT_HANDOFF.md`;
- preserve all older checkpoint events unchanged;
- pass Development Continuity CI.

Continuity must preserve exact next-action and evidence pointers without copying
large scientific narratives into every checkpoint.

## AI-first naming policy

For all new Rhombus 2.0 public code and AI-facing tools, follow
`docs/AI_FIRST_NAMING.md`.

- Canonical new Python namespace: `rhombus`.
- `rudeus` is legacy compatibility surface; do not create new public APIs
  under it when a v2 namespace is appropriate.
- Prefer explicit verb-object capability names such as
  `relax_structure` or `quantify_ionic_transport`.
- Do not expose legacy stage codes such as P0/P1/P2/P3 as primary AI tool names.
- Preserve legacy stage identifiers only as provenance/compatibility metadata.
- Keep AI-facing tool sets small, structured, and domain-grouped.

## Solo research and distinct scientific outcomes

- The project operator is ONE PERSON. New required milestones must be achievable
  using public materials, free compute and code this operator can execute.
  Do NOT prescribe or initiate outreach to external labs, recruited blind stewards,
  third-party signatures or unpublished author manifests as mandatory next tasks.
- `SOLO_PUBLIC_BENCHMARK` PASS/FAIL/INCONCLUSIVE is a retrospective,
  leakage-aware, preregistered-group numerical result with frozen source/test
  boundaries and explicit failures. It is **not** a claim of new experimentally
  validated material discovery, prospective independent truth or physical GO.
- Legacy `SCIENTIFIC_EXTERNAL_PHYSICAL` qualification remains NO-GO and P0-01,
  P0-02, P0-03 remain BLOCKED without the evidence they intrinsically require.
  Never lower these gates to claim success or reuse publicly exposed TEST for tuning.
- The required project deliverable is digital scientific qualification and
  candidate selection. New synthesis, manufacturing, physical measurements or
  external laboratory confirmation are outside the required operational scope.
  Historical physical gates remain unchanged, but are not prerequisites to
  separate computational progress. Digital claims still require suitable model
  applicability, actual numerical evidence, convergence and explicit uncertainty;
  successful execution alone cannot qualify a candidate. See the executed
  `docs/DIGITAL_QUALIFICATION_PILOT_0200.md` contract and its limitations.
- The shared scientific architecture is domain-neutral. O_ONLY is a historically
  bounded validation domain (oxygen-present, sulfur-absent), an element-presence
  proxy and NOT certified crystal phase; it is not the permanent research scope.
  Other families may be represented and researched through explicit domain
  profiles. Model applicability, measured quantities, source separation and
  uncertainty must be qualified separately for each domain before prediction or
  selection is activated. Preserve the frozen O_ONLY/pooled RF comparators and
  experiments; do not transfer their claims to other families or activate a
  production specialist on retrospective improvements. See
  `docs/ARCHITECTURE_DOMAIN_SCOPE_V1.md` for the owner's explicit scope revision.
- Prioritize new measured accuracy, calibration, abstention, family shift and
  same-compute-budget utility over repeated source metadata/checklist/CI PRs.
- Continue preserving all existing append-only checkpoints and canonical merge
  discipline. See Issue #349 and milestone A–E addendum for the active path.

## Owner-approved scientific priority — checkpoint 0204 (2026-10-30)

The active owner-approved research direction is `docs/RESEARCH_STRATEGY_EVIDENCE_QUALIFIED_0204.md`; its machine-readable scope and acceptance contract is `data/development/0204-research-priority-decision-v1.json`. This prioritization **supersedes future work ordering only**, never historical results or scientific qualification standards.

- **Long-term deliverable:** AI-native evidence-qualified digital scientific research and candidate selection under bounded compute; domain-neutral control plane, solid-state Li transport first.
- **First falsifiable comparison:** same-observable Li migration-hop DFT-NEB prediction decisions with strong frozen baselines and source-/composition-group-separated evaluation. Demonstrate reduced false acceptance at matched coverage, or greater coverage at matched risk, with measured cost, leakage and uncertainty. All-abstain is not a win.
- **Execution order:** source/reference and benchmark pre-registration -> timeboxed numerical falsification G0–G1 (10 working days, supporting) -> equal-budget selective-risk/coverage evaluation -> smallest evidence-gated MCP integration only if evaluation supports utility. Global continuous 3D percolation proof, broad Hamiltonian replacement and conductivity prediction are optional later research, not first-milestone prerequisites.
- **Do not conflate:** single-hop NEB, static potential edge, periodic global 3D barrier, molecular-dynamics diffusion and physical conductivity. Numerical certification of a fixed potential does not validate the potential physics.
- **Maintain abstention:** Q0/H0/H1 scientific validity, DFT spin/smearing convergence, 3D transport and conductivity are not certified; `SCIENTIFIC NO-GO / ABSTAIN`, production OFF and independent physical P0 gates remain unchanged.
- **Owner control:** existing Q0 ledger is locally reported at 4/9 after Q0-C joint SCF; no Q0-A/B joint SCF, repeat, remote job, new MLIP/MD or expenditure is authorized by this strategy decision. Per-job explicit approval remains mandatory. Existing checkpoints, baselines, sources and historical proposals remain immutable.

## Test-tier policy

Use the smallest test tier that can falsify the current change quickly.

- During active development, use **R2 Fast CI** first for syntax/import,
  continuity, AI-first API, P2/P2.5 semantic, and directly affected
  known-material contracts.
- Do not wait for the full canonical Wave 2 before starting the next stacked
  development task when Fast CI and the task-specific scientific workflow have
  already passed.
- Before merging a completed scientific PR into `main`, require the existing
  canonical Wave 2 and any task-specific scientific workflow to pass.
- Heavy MLIP/MD work should migrate toward the free-compute backend path
  (Kaggle first; Colab as manual/fallback) rather than using GitHub CPU as the
  primary compute engine.
- Fast CI must remain bounded and must not grow into a duplicate full Wave 2.

## Canonical integration safety

- Stacked development branches may be used to continue work after Fast CI passes, but a
  merge into another worker branch is **not** a canonical merge.
- Before reporting a scientific PR as canonically merged, verify that the target branch
  is `main` or that a later explicit integration PR has synchronized the stack to
  `main`.
- Normal PRs still add exactly one checkpoint event.
- `STACK_REPAIR` is an exceptional recovery mode only for synchronizing a previously
  validated contiguous append-only checkpoint range to canonical `main`. It must bind
  the exact main SHA, base checkpoint index, and recovered checkpoint range, and it must
  never alter previously present checkpoint files.
- Never force-push or move `main` to repair a stack divergence; use a normal reviewed
  merge so both histories are preserved.

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

- Use local resources for development, Git, lightweight tests, staging and
  offline verification. Prefer verified free Kaggle CPU for scientific compute;
  use verified free Kaggle GPU only when measured cost/requirements justify it.
- Do not silently fall back to local MLIP inference, relaxation, production MD
  or convergence experiments when Kaggle is unavailable. Preserve the blocker
  and prepare a reproducible unsubmitted task. A tiny local scientific defect
  smoke test requires specific justification and authorization.
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
- Prefer already-authorized, verified free compute for heavy science while
  minimizing local hardware use. Local development and control remain supported.
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
- The owner's Rhombus 3.0 mission authorizes a new reusable BVSE research core.
  Parameter calibration and model applicability must be demonstrated before
  its static barriers can qualify or physically falsify material candidates.
  This does not authorize provider dispatch or revive old BVSE receipts.
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
