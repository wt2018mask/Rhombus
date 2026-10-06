# Rhombus

**Rhombus** (Python package: `rudeus`) is a research pipeline for discovering and falsifying candidate solid-state ionic conductors under severe compute constraints.

Rhombus currently treats **external falsification of the scientific pipeline as the active gate before any new Candidate Supply v2 production search**.

The current canonical integration branch is `main`. Development proceeds through short-lived `worker/*` branches and pull requests; no single long-lived worker branch defines project state.

---

## Current Project State

The first frozen release is **Rhombus v1.0.0**.

That release froze the completed Wave 2 software/evidence-processing architecture and the previous canonical cohort result:

- verified P2.5 **DIFFUSIVE** candidates: **0**;
- P3-admissible candidates: **0**;
- no P3 TaskSpec was generated;
- cohort closure: `NO_P3_QUALIFYING_CANDIDATE`;
- X / N / S / Application compatibility remained `UNKNOWN`;
- `real_remote_e2e_pass = false`.

The absence of a P3 entrant is a scientific cohort result, not a software failure.

**v1.0.0 is an immutable historical baseline.** Later benchmark evidence may qualify, limit, or falsify parts of the pipeline, but must not rewrite the release history.

Release record:

- [Rhombus v1.0.0](https://github.com/wt2018mask/Rhombus/releases/tag/v1.0.0)

---

## Development Continuity / Recovery Checkpoint

This section exists so development can be resumed safely after an interrupted chat, lost local context, or an unexpected handoff. **GitHub `main` is the source of truth; chat history is not.**

Canonical recovery checkpoint after PR #120:

```
main = fd09b94fc1030fef69cba997f94e4565f48144ae
```

If `main` has advanced beyond this SHA, inspect newer commits, open pull requests, and latest Actions runs before acting.

### Canonical benchmark state at this checkpoint

- B0 and B1 are complete.
- **B2 closure is complete: the latest canonical Wave 2 #179 audit still reports `global_blockers = []`.**
- The minimum pre-split role-count rule is satisfied at POSITIVE=2, NEGATIVE=2, BORDERLINE=2.
- **B3 is frozen:** deterministic immutable DEV/HELD_OUT membership is canonical; do not reshuffle members to work around later B4 blockers.
- The B2 audit intentionally keeps `b3_split_authorized = false`; B3 authorization is a separate transition record that binds the zero-blocker B2 audit and satisfied sample-size assessment.
- the canonical B3 authorization is persisted at `data/benchmarks/known_material/b3_split_authorization_v1.json` with content hash `6a5920309685d5fc5f084480dece901816ec6d649c0cb600680566f3a50b3d94`;
- the immutable B3 split freeze is persisted at `data/benchmarks/known_material/b3_split_freeze_v1.json` with content hash `749c3c15db813a5bc4602f4095089a84951687315192694ca7880ddf97e32cea`; B4 consumes this persisted record rather than recomputing membership from later B2 state.
- Candidate Supply v2 production remains paused.
- the pinned `medium-mpa-0` model-domain snapshot is retained and verified from checkpoint SHA256 `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`;
- all three epistemic/system failure controls execute and pass: `INVALID_SCIENTIFIC_INPUT`, `REPRESENTATION_UNSUPPORTED`, and `MODEL_DOMAIN_UNSUPPORTED`;
- MLIP pretraining exposure accounting is complete and conservative for all **9** B2 materials: `medium-mpa-0` is documented as trained on MPTrj + sAlex, exact benchmark-material membership remains unresolved where not publicly established, and Rhombus must not claim foundation-model-unseen generalization;
- **B4 retained-structure provenance is closed for all 6 frozen members**; tetragonal LLZO is canonically retained with SHA256 `3ed7f425cdac1b2ab8892475501246d5baa4a1362316537689658805b09ee399`;
- curated B1 truth bundles now exist for **6 materials**:
  - `li3n-crystalline` — POSITIVE; READY structure; P2.5 direct self-diffusion SUPPORTED/scorable;
  - `li2s-microcrystalline` — NEGATIVE; READY structure; P0 SUPPORTED/scorable only; P2.5 remains INSUFFICIENT;
  - `lialo2-gamma` — NEGATIVE; READY COD 1008166 structure; P0 and P2.5 SUPPORTED/scorable; direct 6Li tracer self-diffusion is ultraslow and a P2.5 `PASS` is falsifying for this negative control.
  - `libh4-phase-transition-pair` — BORDERLINE; curated phase-transition truth contributes one scoreable BORDERLINE material.
  - `llzo-tetragonal-undoped` — BORDERLINE; retained 192-atom tetragonal reference plus direct 7Li NMR self-diffusion truth with explicit 550 K phase-scope ambiguity; Wave 2 run #114 validates the executable structure.
  - `llzo-cubic-al-stabilized` — POSITIVE; retained COD 7215448 fractional-occupancy reference; P0 SUPPORTED/scorable only. The canonical execution representation is now an 8-member / 2-cell exact-rational-weight ordered ensemble that preserves the retained marginal occupancies without claiming unresolved configurational correlations.
- direct P2.5 self-diffusion truth now also includes source-bound BORDERLINE evidence where phase scope is explicitly represented rather than collapsed to PASS/FAIL.
- canonical truth-bundle catalog contains **6 CURATED_FOR_B2** materials.

The canonical B2 global blocker set is now empty:

```
global_blockers = []
```

The minimum pre-split feasibility rule is:

```
minimum scoreable materials before B3
POSITIVE   >= 2
NEGATIVE   >= 2
BORDERLINE >= 2
```

Current minimum scoreable-role counts:

```
POSITIVE   = 2
NEGATIVE   = 2
BORDERLINE = 2
```

Remaining deficits are zero for all three roles.

This is a **split-feasibility rule**, not a B6 qualification threshold. No sensitivity/specificity/power claim is authorized from the current small counts.

### Current canonical scientific references

- alpha-Li3N executable structure:
  `data/benchmarks/known_material/structures/literature/alpha-li3n-rabenau-1976-v1.cif`
- alpha-Li3N truth bundle:
  `data/benchmarks/known_material/truth_bundles/li3n-crystalline-v1.json`
- Li2S executable structure:
  `data/benchmarks/known_material/structures/cod/9009060-latest-freeze-v1.cif`
- Li2S truth bundle:
  `data/benchmarks/known_material/truth_bundles/li2s-microcrystalline-v1.json`
- gamma-LiAlO2 executable structure:
  COD 1008166 retained at `data/benchmarks/known_material/structures/cod/1008166-latest-freeze-v1.cif`
  with SHA256 `94aa55ef4b1a2aeb94c5c07ddd7cdc18201ac752546a283c8543cb8faa05f589`
- gamma-LiAlO2 tracer source audit:
  `data/benchmarks/known_material/source_audits/lialo2-gamma-tracer-2016-v1.json`
- gamma-LiAlO2 truth bundle:
  `data/benchmarks/known_material/truth_bundles/lialo2-gamma-v1.json`

### Important stale-work warning

PR #46 (`worker/b2-li2s-first-truth-bundle`) is obsolete and must not be merged as-is. Its scientifically reusable Li2S content was already ported onto current `main` through PR #56.

Historical bot/worker branches used to create already-merged evidence are not canonical project state. Always compare against current `main` before reusing them.

### Recovery protocol

After an interrupted development session:

1. inspect current `main` HEAD, open PRs, and latest Actions runs before changing benchmark state;
2. preserve the frozen B3 DEV / HELD_OUT membership exactly; never reshuffle a member to work around a B4 representation blocker;
3. inspect the canonical B4 provenance, structure-resolution, representation-policy, and executable-readiness state before materializing blind ingress;
4. never convert infrastructure, representation, model-domain, or evidence insufficiency into a physical material FAIL;
5. never treat ionic conductivity as P2.5 self-diffusion truth;
6. never infer non-exposure to a foundation model from missing public training-membership data;
7. reuse retained structures, truth bundles, source audits, deterministic realization code, and successful CI evidence before creating duplicate workflows or repeating expensive compute;
8. prefer blocker-reducing chunks that complete in one CI cycle and keep representation-policy evidence fail-closed;
9. preserve the canonical cubic Al-LLZO SATISFIED representation evidence and exact-weighted ensemble semantics; do not replace it with a single ordered proxy or infer source-unresolved configurational correlations;
10. treat repository-visible reverse bindings from execution identifiers to material identity/truth as blinding contamination; opaque remapping cannot repair prior exposure;
11. keep any future qualification cohort identity/truth state externally sealed through B6/B7, and do not execute the current v1 HELD_OUT as qualification evidence or authorize Candidate Supply v2.

### Immediate B4 work queue

1. preserve the now-closed 6/6 retained-structure provenance, **6/6 executable readiness**, and persisted B3 authorization/freeze artifacts as historical v1 evidence;
2. treat the canonical v1 blinding-integrity audit as a hard blocker: the public B3 material keys, public truth-bundle bindings, and public execution-visible structure-hash bindings mean the current HELD_OUT cohort is not eligible for strong blind qualification;
3. do **not** provision a real v1 legacy→opaque map or materialize a production v1 blind package merely to rename already exposed identities;
4. define a versioned qualification-cohort repair that keeps held-out material identity and truth bindings outside repository-visible state until after the science freeze and one-shot evaluation; do not silently rewrite the v1 B3 freeze;
5. keep the existing v1 cohort available for DEV/diagnostic falsification where its public identity/truth status is explicitly acknowledged;
6. do not run the current v1 HELD_OUT as qualification evidence, tune held-out-facing scientific thresholds, or authorize Candidate Supply v2.


v1.0.0 remains immutable throughout recovery. Do not rewrite historical release evidence to make later benchmark results look cleaner.

---

## Canonical Pipeline

```
E → G → P0 → P1 → P2 → P2.5 → P3 → X → N → S
→ Application compatibility → Final Claim Vector → OUT
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
- **N** — final novelty assessment
- **S** — synthesis-oriented assessment
- **Application compatibility** — versioned application-profile claims
- **Final Claim Vector** — deterministic conjunction of mandatory claims
- **OUT** — conservative terminal evidence output

Downstream contracts are documented in [Downstream claims](docs/DOWNSTREAM_CLAIMS.md).

### Hard interpretation rules

These are project invariants:

- **P2 PASS does not imply ionic diffusion.**
- Only **P2.5 DIFFUSIVE** candidates may enter P3.
- Ionic conductivity is not interchangeable with self-diffusion truth.
- Brownian or synthetic calibration does not authorize a real-material diffusion claim.
- Unsupported chemistry, species, model domain, or representation must become **UNKNOWN / INDETERMINATE / unsupported**, not a false material failure.
- Tool limitations must never be converted into claims about nature.
- Missing evidence must never be promoted to PASS.
- Historical frozen results are never silently reinterpreted.
- Raw novelty alone is not a valid scientific optimization target.

---

# Active Scientific Gate: Blind Known-Material Falsification Benchmark

Before Rhombus resumes new Candidate Supply v2 production, the downstream scientific filters must demonstrate that they behave sensibly on **known real materials whose identities and expected scientific behavior are independently evidence-bound**.

This benchmark intentionally bypasses generation:

```
known reference material
        ↓
       P0
        ↓
       P1
        ↓
       P2
        ↓
      P2.5
        ↓
       P3
        ↓
     X → N → S → Application
```

**G is not under test in this benchmark.**

The purpose is not to prove that Rhombus is correct. It is to make the pipeline easier to falsify before additional discovery compute is spent.

## Benchmark roadmap

```
v1.0.0 frozen baseline
        ↓
B0 Scientific Benchmark Contract                ✅ merged
        ↓
B1 Source-bound Truth Record Contract            ✅ merged
        ↓
B2 Literature / Structure / Truth Curation       ✅ closed
        ↓
B3 Immutable DEV / HELD_OUT Split                 ✅ frozen
        ↓
B4 Blind Benchmark Ingress + Provenance            ← CURRENT
        ↓
B5 DEV Execution + Falsification
        ↓
B6 Science Freeze
        ↓
B7 One-shot HELD_OUT Evaluation
        ↓
B8 Unblind + Qualification Report
        ↓
QUALIFIED?
   ├─ yes → Candidate Supply v2 production may resume
   └─ no  → recalibration/new held-out set or pipeline blocked
```

Candidate Supply v2 production is therefore **paused**, not abandoned.

---

## B0 — Benchmark Contract

B0 freezes the benchmark rules before any held-out evaluation.

Implemented in:

- [Known-material benchmark contract](docs/KNOWN_MATERIAL_BENCHMARK.md)
- `rudeus/science/known_material_benchmark.py`

Key properties:

- known materials bypass G and enter at P0;
- DEV may be used for diagnosis/calibration;
- HELD_OUT cannot be used for tuning;
- HELD_OUT membership becomes immutable at B3;
- unblinding occurs only after blinded results are frozen;
- unsupported regimes must remain unresolved rather than being extrapolated;
- evaluation is stage-wise, not collapsed into one scalar score;
- B0 defines no arbitrary numerical qualification threshold.

Possible final qualification outcomes are limited to:

- `QUALIFIED`
- `RECALIBRATION_REQUIRED`
- `PIPELINE_BLOCKED`

---

## B1 — Source-Bound Truth Records

B1 defines how literature/reference evidence becomes stage-specific benchmark truth.

Implemented in:

- [Known-material truth records](docs/KNOWN_MATERIAL_TRUTH_RECORDS.md)
- `rudeus/science/known_material_truth.py`

Important semantics:

- every truth statement must be bound to retained evidence/provenance;
- exact phase and structure identity matter;
- publication count is not evidence independence;
- two papers derived from the same underlying dataset remain one evidence family;
- only `SUPPORTED` truth can falsify pipeline behavior;
- `CONFLICTING`, `INSUFFICIENT`, and `NOT_APPLICABLE` truth is explicitly non-scorable;
- conductivity evidence cannot substitute for P2.5 self-diffusion truth;
- every benchmark material must explicitly account for every stage, including unresolved stages.

---

## B2 — Literature-Grounded Material Universe

B2 is closed for the minimum pre-split gate. Wave 2 #118 reports zero global blockers, MLIP exposure accounting and all three failure controls are satisfied, and the scoreable role counts are POSITIVE=2, NEGATIVE=2, BORDERLINE=2. B3 now owns immutable DEV/HELD_OUT split construction; B2 evidence contracts remain unchanged.

The first source-screened universe is implemented in:

- [Known-material universe](docs/KNOWN_MATERIAL_UNIVERSE.md)
- `rudeus/science/known_material_universe.py`
- `data/benchmarks/known_material/b2_universe_intake_v1.json`

The current intake spans multiple chemistry and failure modes, including:

- Li10GeP2S12 (LGPS)
- cubic Al-stabilized LLZO
- tetragonal LLZO
- phase-resolved LiBH4
- crystalline Li3N
- microcrystalline Li2S
- nanoporous beta-Li3PS4
- Li6PS5Cl argyrodite
- gamma-LiAlO2

These are **curation candidates or curated controls**, not benchmark execution outcomes.

DEV/HELD_OUT membership is now frozen in B3. B2 records remain evidence inputs and must not be used to reshuffle that frozen split.

### Exact-structure binding

A DOI, paper, database page, or downloadable CIF link is not enough to make a benchmark structure executable.

The structure-binding layer is implemented in:

- [Known-material structure binding](docs/KNOWN_MATERIAL_STRUCTURE_BINDING.md)
- `rudeus/science/known_material_structure_binding.py`
- `data/benchmarks/known_material/b2_structure_binding_v1.json`

A structure is not considered closed until Rhombus has:

1. exact phase/composition identity;
2. traceable artifact provenance;
3. explicit disorder / partial-occupancy treatment;
4. verified redistribution rights for repository retention;
5. the retained artifact;
6. a SHA256 binding of the retained bytes;
7. validation that the artifact actually represents the intended phase/composition.

Current structure records remain intentionally unresolved where those conditions have not been met.

B2 minimum pre-split closure is complete. Exact retained structure provenance remains a B4 ingress prerequisite for each frozen member; a missing artifact blocks ingress and is never converted into a material FAIL.

---

## What B2 Must Not Do

B2 must not:

- assign DEV or HELD_OUT membership;
- invent opaque benchmark IDs intended for blind execution;
- run the benchmark;
- tune scientific thresholds;
- use conductivity as a substitute for self-diffusion;
- silently turn ordered proxy structures into disordered experimental phases;
- treat a periodic bulk structure as equivalent to a surface/porosity-dominated material;
- retain publisher supplementary artifacts without verified rights;
- authorize Candidate Supply v2 production.

Those operations belong to later benchmark phases or require explicit evidence closure.

---

# Candidate Supply v2 — Paused Production Track

Candidate Supply v2 remains an important part of Rhombus, but its **production use is gated by the known-material benchmark**.

The redesign was motivated by the previous 0-DIFFUSIVE result and by confirmed weaknesses in the old generation path:

- uncompensated vacancy/interstitial operations frequently violated neutrality;
- global all-site displacement damaged host frameworks;
- legacy novelty matching had a primitive-cell reduction asymmetry;
- one shared RNG stream coupled operator selection to perturbation details;
- aggregate audit records were insufficient for reconstructing candidate-level decisions.

Work already implemented includes:

- deterministic parent × operator scheduling;
- operator-scoped RNG identities;
- parent P0 neutrality guards;
- lossless candidate-level evidence;
- corrected same-cell novelty semantics;
- species-neutral `mobile-ion-displace-v2`;
- reproducible multi-seed diagnostic panels;
- broader Candidate Supply v2 scheduling and audit infrastructure.

These artifacts remain valid engineering work. They do **not** authorize a new production cohort until benchmark qualification.

---

## Corrected Novelty Semantics

Candidate Supply v2 introduced:

```
novelty-matcher-v2-same-cell
```

For same-cell displacement semantics, primitive reduction is skipped during matching.

On the frozen ordered-72 cohort at legacy `sigma = 0.05 Å`:

- legacy novelty: 24 novel / 38 rediscovery
- corrected same-cell novelty: **0 novel / 62 rediscovery**

The prior apparent size bias was therefore largely a matcher artifact rather than evidence of meaningful structural exploration.

---

## Historical mobile-ion-displace-v2 Diagnostic

The first species-neutral experimental operator is:

```
mobile-ion-displace-v2
```

It perturbs only the configured mobile species while leaving the host atoms and lattice fixed.

The historical paired diagnostic used:

```
sigma = [0.30, 0.35, 0.40] Å
seeds = [42, 43, 44, 45]
```

Each run requested 72 parents, with 10 blocked by the parent P0 neutrality guard and 62 generated children.

Observed useful-count means were:

| sigma | mean useful / 62 |
|---:|---:|
| 0.30 | 25.75 |
| 0.35 | 28.25 |
| 0.40 | 24.75 |

Observed mean geometry failures were:

| sigma | mean geometry failures / 62 |
|---:|---:|
| 0.30 | 17.75 |
| 0.35 | 23.25 |
| 0.40 | 31.00 |

These results remain **observational diagnostics**.

They do not prove that `0.35 Å` is globally optimal, do not activate the operator in production, and do not constitute downstream transport validation.

---

# Development Order From Here

The current order is:

1. keep the persisted B3 DEV/HELD_OUT split immutable;
2. preserve the closed B4 retained-structure provenance and 6/6 executable-readiness state;
3. repair the qualification-cohort blinding design without rewriting the historical v1 B3 freeze;
4. keep future held-out identity/truth bindings externally sealed until after the science freeze and one-shot evaluation;
5. execute and falsify on the explicitly non-blind DEV/diagnostic cohort in B5;
6. freeze science/acceptance logic in B6 before any replacement qualification cohort is evaluated;
7. execute only an uncontaminated, versioned HELD_OUT qualification cohort exactly once in B7;
8. unblind and issue the qualification result in B8;
9. resume Candidate Supply v2 production **only if qualification permits it**.

No large new production cohort or heavy benchmark campaign should be launched before the relevant evidence and benchmark gates authorize it.

---

## Compute Strategy

Rhombus is designed around scarce compute.

### Local machine

Use for:

- Git and code review;
- unit tests;
- provenance/evidence curation;
- JSON/audit analysis;
- small deterministic CPU diagnostics;
- orchestration.

### Kaggle / Colab CPU

Use for:

- StructureMatcher-heavy diagnostics;
- larger CPU-bound audit workloads;
- reproducible batch validation where useful.

### External GPU

Reserve for stages that materially benefit from acceleration:

- MLIP relaxation;
- MD;
- P1/P2/P2.5/P3 scientific workloads.

The benchmark should consume expensive compute only after evidence and ingress contracts justify it.

---

## Repository Areas

Current benchmark work is primarily under:

```
rudeus/science/
data/benchmarks/known_material/
docs/KNOWN_MATERIAL_*
```

Candidate Supply v2 implementation remains primarily under:

```
rudeus/generation/
```

Historical artifacts and frozen release evidence remain authoritative for the state they record and should not be silently overwritten.

---

## Scientific Status Summary

As of `main = fd09b94fc1030fef69cba997f94e4565f48144ae`:

- Rhombus v1.0.0 remains the frozen historical baseline;
- Candidate Supply v2 production remains paused;
- B0 and B1 are complete;
- **B2 is closed** with six CURATED_FOR_B2 truth bundles, role counts POSITIVE=2 / NEGATIVE=2 / BORDERLINE=2, and zero canonical global blockers;
- **B3 is frozen** with immutable deterministic DEV/HELD_OUT membership, persisted authorization hash `6a5920309685d5fc5f084480dece901816ec6d649c0cb600680566f3a50b3d94`, and persisted freeze hash `749c3c15db813a5bc4602f4095089a84951687315192694ca7880ddf97e32cea`;
- **B4 retained reference-structure provenance is 6/6 and executable readiness is now 6/6**;
- cubic Al-LLZO is canonically `ENSEMBLE/READY`: the retained COD source remains the reference identity, while execution uses the 8-member / 2-cell exact-rational-weight ordered ensemble bound by visible composite structure hash `0ce55065f464292b34919e31bab12947cddea8c26bf2521323fd3f8714d5e475`;
- the fractional-occupancy strategy preserves Li1=0.54, Al1=0.06530, and Li2=0.37 marginal occupancies exactly and explicitly makes no claim about source-unresolved cross-sublattice configurational correlations;
- the canonical representation evidence entry is SATISFIED with content hash `f91e629b8d2d925b74182ef0dd12ea3950a137bd53563f6f81d60efd20f22d8a`;
- the REPRESENTATION_UNSUPPORTED failure control is now an independent synthetic missing-strategy fixture and still passes fail-closed;
- Wave 2 now runs the complete `tests/test_known_material_*.py` suite, preventing B3/B4 test coverage drift;
- the B4 opaque-ID/common-protocol amendment and composite DIRECT/PHASE_SET/ENSEMBLE structure-hash contracts are canonical;
- the B4 package builder remains useful for contract tests, but a new blinding-integrity gate detects that the v1 frozen split, truth bundles, and execution-visible structure hashes are already repository-visible and reverse-bindable to material identity;
- **production B4 blind-package materialization is now fail-closed** for the current v1 cohort; a new opaque permutation cannot restore strong blinding after those identity/truth bindings were published;
- **B4 is blocked on methodology repair**: the current v1 HELD_OUT members may remain diagnostic/reference evidence, but they must not be used to claim strong blind held-out qualification;
- no B5 DEV execution, B6 science freeze, B7 HELD_OUT execution, B8 unblinding, or qualification decision has occurred;
- no benchmark result authorizes Candidate Supply v2 production.

---

## Project Rule

**Rhombus should search broadly, validate conservatively, and record enough evidence that every scientific conclusion can be reconstructed, falsified, and challenged.**
