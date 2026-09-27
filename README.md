# Rhombus

**Rhombus** (Python package: `rudeus`) is a research pipeline for discovering and falsifying candidate solid-state ionic conductors under severe compute constraints.

The project is currently in a **candidate-supply redesign phase**. The previous Li-centered perturb-and-filter workflow reached a canonical result of **0 P2.5 DIFFUSIVE candidates**, so the present bottleneck is not downstream MD capacity; it is the quality, diversity, and scientific neutrality of candidate generation at **G**.

The current development branch is:

```
worker/g/candidate-supply-v2
```

The guiding objective is to evolve Rhombus from a narrow Li-centered perturbation pipeline into a **bias-aware, species-neutral discovery engine with explicit species/profile-specific scientific validation**.

---

## Current Scientific Position

The canonical pipeline is:

```
E → G → P0 → P1 → P2 → P2.5 → P3 → X → N → S → OUT
```

Where:

- **E** — empirical anchors / source materials
- **G** — candidate acquisition and generation
- **P0** — static existence and basic physical plausibility
- **P1** — MLIP relaxation and structure/energy sanity
- **P2** — finite-temperature structural stability
- **P2.5** — ionic-transport regime screening
- **P3** — transport MD
- **X** — independent-model cross-check
- **N** — negative-control / falsification layer
- **S** — synthesis-oriented assessment
- **OUT** — conservative final evidence output

### Hard interpretation rules

These are project invariants, not suggestions:

- **P2 PASS does not imply ionic diffusion.**
- Only **P2.5 DIFFUSIVE** candidates may enter P3.
- Published conductivity is acquisition/priority provenance only, not P2.5 truth.
- Brownian calibration does not authorize a real-material diffusion claim.
- Unsupported species or chemistries must be marked unsupported/unvalidated, not treated as failed materials.
- Tool limitations must never be converted into claims about nature.
- Raw novelty is not a sufficient optimization target.

---

## Why Candidate Supply v2 Exists

The previous canonical evidence transition completed with:

- 5 final P2.5 candidates
- 5 **NONDIFFUSIVE**
- 0 **DIFFUSIVE**
- 0 P3 entrants

That result is frozen. The project does **not** extend those five final NONDIFFUSIVE candidates, blindly rerun the old frozen cohort, or reinterpret P2 structural survival as transport evidence.

The failure shifted the research question upstream:

> Can G generate materially different, physically plausible candidates without introducing hidden structural, chemical, species, family, or implementation bias?

The old generation path had several problems:

- uncompensated vacancy/interstitial operations frequently violated neutrality;
- global all-site displacement damaged host frameworks as amplitude increased;
- legacy novelty matching had a primitive-cell reduction asymmetry that falsely made large structures appear more novel;
- one shared RNG stream coupled operator selection to perturbation details;
- aggregate audit records were insufficient for reconstructing every candidate-level decision.

Candidate Supply v2 is designed to make those failure modes explicit and auditable.

---

## Candidate Supply v2: Design Principles

### 1. Separate discovery mechanics from validation profiles

Rhombus is moving toward two conceptually separate layers:

**Discovery Engine**
- species-neutral where scientifically reasonable;
- does not hard-code Li as the definition of a mobile species;
- generates candidates and records provenance;
- exposes uncertainty, applicability, and bias.

**Scientific Validation Profiles**
- may remain species-specific;
- own species-specific calibration, transport assumptions, model support, and validation limits;
- return explicit unsupported/unvalidated states when a profile does not exist.

The goal is not “zero bias,” which is impossible. The goal is to make bias **visible, measurable, and non-authoritative**.

### 2. Deterministic parent × operator scheduling

Candidate Supply v2 records explicit scheduling states such as:

- `SCHEDULED`
- `INAPPLICABLE`
- `DISABLED_BY_POLICY`
- `DEFERRED_PENDING_DESIGN`
- `BLOCKED_BY_PARENT_P0`

A parent that fails the P0 neutrality guard is blocked before generation.

### 3. Operator-scoped RNG

Each parent/operator/version receives a stable RNG identity derived from deterministic inputs rather than cohort position.

This prevents:

- operator-selection draws from perturbing child geometry;
- cohort reordering from changing a parent's random stream;
- blocked/inapplicable predecessors from changing later candidates.

### 4. Lossless evidence before aggregate metrics

Candidate-level raw evidence is authoritative.

Summaries must be reconstructible from persisted rows. A summary counter is not allowed to become a second source of truth.

---

## Corrected Novelty Semantics

A major legacy artifact was found in `StructureMatcher` usage.

For displaced structures, a parent could primitive-reduce while a slightly symmetry-broken child stayed in the full cell. Default matching could then report false novelty simply because cell reduction differed.

Candidate Supply v2 introduced:

```
novelty-matcher-v2-same-cell
```

For same-cell displacement semantics, structure reduction is skipped during matching.

On the frozen ordered-72 cohort at the legacy `sigma = 0.05 Å`:

- legacy novelty: 24 novel / 38 rediscovery
- corrected same-cell novelty: **0 novel / 62 rediscovery**

The prior apparent size bias was therefore largely a matcher artifact, not evidence of meaningful structural exploration.

---

## Current Experimental Operator: mobile-ion-displace-v2

The first species-neutral operator under Candidate Supply v2 is:

```
mobile-ion-displace-v2
```

Properties:

- perturb only the configured mobile species;
- leave host atoms fixed;
- leave lattice fixed;
- accept arbitrary configured species rather than a Li/Na allowlist;
- deterministic under an operator-scoped RNG;
- preserve full provenance;
- explicitly reject/inapplicable when the configured target species is absent.

Examples in tests include Li, Na, and Mg targets.

This operator is **not activated in the production scheduler**. It is currently an observational G-level research operator.

---

## Current Diagnostic Evidence

The frozen ordered-72 OBELiX cohort is used as the first calibration/evidence cohort for the current Li validation profile. This does **not** define the long-term search scope of Rhombus.

A paired multi-seed diagnostic was run for:

```
sigma = [0.30, 0.35, 0.40] Å
seeds = [42, 43, 44, 45]
```

Each run has:

- 72 requested parents
- 10 blocked by parent P0 neutrality
- 62 generated children

### Run-level useful yield

`useful` means:

```
novel under corrected novelty semantics
AND
P0 PLAUSIBLE
```

Observed useful counts:

| sigma | seed 42 | seed 43 | seed 44 | seed 45 | mean |
|---:|---:|---:|---:|---:|---:|
| 0.30 | 26 | 26 | 30 | 21 | 25.75 |
| 0.35 | 31 | 31 | 28 | 23 | 28.25 |
| 0.40 | 27 | 28 | 24 | 20 | 24.75 |

Observed geometry-failure means:

| sigma | mean geometry failures / 62 |
|---:|---:|
| 0.30 | 17.75 |
| 0.35 | 23.25 |
| 0.40 | 31.00 |

Interpretation:

- mobile-species-only displacement is substantially more promising at P0 than global all-site displacement;
- `0.30–0.35 Å` is currently an interesting exploration regime;
- `0.40 Å` increases novelty but damages geometry enough that useful yield falls;
- `0.35 Å` is **not declared globally optimal**;
- no scheduler activation or downstream scientific superiority claim is authorized from these data.

### Persistence

With a persistent-useful threshold of at least 3 of 4 seeds:

- `sigma = 0.30`: 20 persistent useful parents
- `sigma = 0.35`: 22 persistent useful parents

Persistence appears across multiple chemical families and site counts, but the source cohort itself remains Li-centered and compositionally biased. Family-level comparisons therefore remain diagnostic rather than universal claims.

---

## Reproducible Diagnostic Panels

Rhombus now contains a reproducible panel layer for mobile-ion displacement diagnostics.

The panel:

- executes the full sigma × seed Cartesian product afresh;
- persists ordered, lossless per-parent rows;
- derives all run, sigma, parent, family, and site-count summaries from those rows;
- records cohort identity, operator/version, novelty matcher version, target species, threshold, and diagnostic configuration;
- writes deterministic JSON atomically;
- explicitly carries non-authorization metadata.

Canonical status:

```
OBSERVATIONAL_DIAGNOSTIC
```

It does **not** authorize:

- scheduler activation;
- P1 eligibility;
- downstream scientific superiority claims.

Global per-parent frequency semantics use the number of actually generated sigma × seed observations as the denominator. Blocked and inapplicable observations are excluded.

---

## Current Engineering Gate: Kaggle Scientific E2E

The immediate engineering goal is to prove the full scientific execution path without manual copy/paste of prompts, commands, logs, or result files.

Target flow:

```
current local workspace snapshot
→ Kaggle CLI CPU submission
→ bounded polling
→ automatic log collection
→ 864-row diagnostic panel generation
→ deterministic rerun
→ scientific validation
→ report + panel download
→ SHA256 verification
→ PASS / SCIENTIFIC_VALIDATION_FAIL / INFRA_FAILURE
```

The first real E2E workload is the `mobile-ion-displace-v2` diagnostic panel:

```
72 parents × 3 sigma values × 4 seeds = 864 requested rows
```

Required checks include:

- exact 864-row accounting;
- all 12 sigma × seed runs present exactly once;
- global frequencies constrained to `[0, 1]`;
- raw-row reconciliation of counts and frequencies;
- correct per-sigma persistence denominators;
- observational/non-authorization assertions;
- deterministic byte-identical rerun;
- identical SHA256 on rerun;
- protected historical artifact integrity;
- environment and workspace provenance.

Current automation status is immediately before the first real scientific Kaggle E2E execution. The last host-side compatibility blocker is Windows PowerShell 5.1 relative-path handling in staging.

After that compatibility fix, the target entry point is:

```powershell
.\scripts\run.ps1 kaggle-mobile-ion-e2e
```

A successful end-to-end run will establish the first practical version of Rhombus scientific execution automation.

---

## Development Plan

### Phase 1 — Freeze failure lessons as invariants

Completed / ongoing:

- freeze canonical P2.5 transition evidence;
- preserve 0-DIFFUSIVE result without reinterpretation;
- fix operator RNG coupling;
- correct same-cell novelty semantics;
- add parent P0 guard;
- add lossless Candidate Supply v2 audit structures;
- add reproducible multi-seed diagnostic panels.

### Phase 2 — Validate the first species-neutral operator

Current:

- complete scientific Kaggle E2E;
- freeze reproducible mobile-ion diagnostic evidence;
- keep `mobile-ion-displace-v2` observational until explicit promotion criteria are met;
- do not tune sigma indefinitely against one cohort.

### Phase 3 — Build an operator portfolio

Planned operator classes:

1. mobile-sublattice perturbation;
2. site/hop-informed relocation;
3. charge-balanced defect generation;
4. framework-preserving local distortion;
5. later, composition- and prototype-changing generation.

Each experimental operator should have predefined:

- applicability rules;
- deterministic RNG provenance;
- cheap P0 failure controls;
- multi-seed persistence diagnostics;
- family/size/species bias audit;
- promotion and stop conditions.

### Phase 4 — Bias-aware operator tournaments

Compare operators on the same parent cohorts using paired deterministic experiments.

Metrics should include:

- candidate yield;
- corrected structural novelty;
- useful yield;
- downstream survival;
- diversity coverage;
- compute efficiency;
- failure concentration;
- family / size / prototype / species applicability.

Do not rank operators by raw novelty alone.

### Phase 5 — Explicit exploitation and exploration lanes

The discovery policy should eventually separate:

- **exploitation** — search around empirically productive regions;
- **exploration** — deliberately cover underrepresented families, prototypes, species, and mechanisms.

Selection should move toward multi-objective / Pareto reasoning rather than one scalar score.

### Phase 6 — Broaden source-data scope

OBELiX is useful but Li-centered. Rhombus must not generalize its coverage into a universal materials claim.

Future acquisition should add broader source lanes while preserving profile-specific validation. A species may be discoverable before a validated downstream transport profile exists; such candidates should remain explicitly unvalidated rather than rejected.

### Phase 7 — Species/profile-specific red-team validation

For each supported validation profile, build:

- positive controls;
- negative controls;
- hard negatives;
- out-of-domain controls;
- calibration and uncertainty checks.

Only then should a profile authorize stronger scientific conclusions.

### Phase 8 — Closed-loop discovery

Long-term target:

```
Generate
→ cheap filters
→ diversity / uncertainty selection
→ MLIP / MD
→ failure analysis
→ update search policy
→ repeat
```

The loop should consume failures as information rather than merely discard failed candidates.

---

## Promotion Rules

No experimental G operator should be promoted because it produced a visually interesting structure or a high novelty count.

Promotion should require evidence such as:

- deterministic reproducibility;
- useful-yield persistence across seeds;
- acceptable geometry-failure rate;
- no obvious family/size/species artifact;
- auditable provenance;
- comparison against independent operator hypotheses;
- downstream survival when P1/P2 testing becomes justified.

Likewise, failure to support a chemistry because a validation profile is unavailable must be reported as a validation limitation, not as evidence that the chemistry is poor.

---

## Compute Strategy

Rhombus is intentionally designed around scarce compute.

### Local machine

Use for:

- Git and code review;
- unit tests;
- JSON/audit analysis;
- small deterministic CPU diagnostics;
- orchestration.

### Kaggle / Colab CPU

Use for:

- repeated StructureMatcher-heavy cohort diagnostics;
- multi-seed panel generation;
- larger CPU-bound audit workloads.

### External GPU

Reserve for stages that materially benefit from GPU acceleration:

- MLIP relaxation;
- MD;
- later P1/P2/P2.5/P3 workloads.

Cheap CPU stages should eliminate weak candidates before expensive GPU stages.

---

## Current Repository Focus

The active research area is primarily:

```
rudeus/generation/
```

Key concepts currently implemented there include:

- Candidate Supply v2 scheduler/audit contracts;
- deterministic operator RNG identity;
- parent P0 guard;
- corrected same-cell novelty classification;
- `mobile-ion-displace-v2`;
- standalone cohort diagnostics;
- reproducible multi-seed diagnostic panels.

Legacy generation behavior is retained where needed for regression/history but should not be confused with the current scientific direction.

---

## Scientific Status Summary

As of the current development state:

- the previous canonical transport campaign produced **0 P2.5 DIFFUSIVE** candidates;
- G is the current bottleneck;
- legacy novelty contained a confirmed structural-matching artifact;
- simple global all-site Gaussian displacement is not an adequate Candidate Supply v2 solution;
- species-neutral mobile-ion displacement is a reproducible, empirically promising **observational G operator**;
- it is not yet scheduler-activated;
- no P1/P2/P2.5 superiority claim has been made;
- Kaggle scientific E2E automation is the immediate engineering gate;
- the next scientific expansion is an independent operator portfolio, followed by paired bias-aware tournaments.

---

## Project Rule

**Rhombus should search broadly, validate conservatively, and record enough evidence that every scientific conclusion can be reconstructed and challenged.**
