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

Canonical recovery checkpoint after PR #74:

```
main = 769c91591f7805871e67b1744011997fa24c72a1
```

If `main` has advanced beyond this SHA, inspect newer commits, open pull requests, and latest Actions runs before acting.

### Canonical B2 state at this checkpoint

- B0 and B1 are complete.
- **B2 remains active and is in its late sample-completion phase.**
- B3 has not started and is not authorized.
- `b3_split_authorized = false`.
- Candidate Supply v2 production remains paused.
- the pinned `medium-mpa-0` model-domain snapshot is retained and verified from checkpoint SHA256 `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`;
- all three epistemic/system failure controls execute and pass: `INVALID_SCIENTIFIC_INPUT`, `REPRESENTATION_UNSUPPORTED`, and `MODEL_DOMAIN_UNSUPPORTED`;
- MLIP pretraining exposure accounting is complete and conservative for all **9** B2 materials: `medium-mpa-0` is documented as trained on MPTrj + sAlex, exact benchmark-material membership remains unresolved where not publicly established, and Rhombus must not claim foundation-model-unseen generalization;
- canonical structure-resolution now includes the retained executable tetragonal LLZO reference validated by Wave 2 run #114; unresolved structure records remain governed by the same exact-binding policy;
- curated B1 truth bundles now exist for **5 materials**:
  - `li3n-crystalline` — POSITIVE; READY structure; P2.5 direct self-diffusion SUPPORTED/scorable;
  - `li2s-microcrystalline` — NEGATIVE; READY structure; P0 SUPPORTED/scorable only; P2.5 remains INSUFFICIENT;
  - `lialo2-gamma` — NEGATIVE; READY COD 1008166 structure; P0 and P2.5 SUPPORTED/scorable; direct 6Li tracer self-diffusion is ultraslow and a P2.5 `PASS` is falsifying for this negative control.
  - `libh4-phase-transition-pair` — BORDERLINE; curated phase-transition truth contributes one scoreable BORDERLINE material.
  - `llzo-tetragonal-undoped` — BORDERLINE; retained 192-atom tetragonal reference plus direct 7Li NMR self-diffusion truth with explicit 550 K phase-scope ambiguity; Wave 2 run #114 validates the executable structure.
- direct P2.5 self-diffusion truth now also includes source-bound BORDERLINE evidence where phase scope is explicitly represented rather than collapsed to PASS/FAIL.
- canonical truth-bundle catalog contains **5 CURATED_FOR_B2** materials.

The canonical B2 global blocker is exactly:

```
SAMPLE_SIZE_POWER_RULE_UNSATISFIED
```

The minimum pre-split feasibility rule is:

```
minimum scoreable materials before B3
POSITIVE   >= 2
NEGATIVE   >= 2
BORDERLINE >= 2
```

Current scoreable-role counts after PR #61:

```
POSITIVE   = 1
NEGATIVE   = 2
BORDERLINE = 2
```

Remaining deficits:

```
POSITIVE   +1
NEGATIVE   +0
BORDERLINE +0
```

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

1. inspect current `main` HEAD, open PRs, and latest Actions runs;
2. inspect or run `scripts/benchmark/audit_b2_coverage.py`; its blocker set is the canonical continuation signal;
3. require the audit to keep `b3_split_authorized = false` until **all** B2 blockers are cleared;
4. never convert infrastructure, representation, model-domain, or evidence insufficiency into a physical material FAIL;
5. never treat ionic conductivity as P2.5 self-diffusion truth;
6. never infer non-exposure to a foundation model from missing public training-membership data;
7. reuse retained structures, truth bundles, source audits, and successful old work before creating duplicate workflows or repeating expensive CI;
8. prefer blocker-reducing chunks that can complete in one CI cycle; do not create multiple speculative branches touching the same benchmark ledgers;
9. after every scoreable-material promotion, update `sample_size_assessment_v1.json`, run Wave 2, and inspect the actual canonical B2 audit instead of assuming the deficit changed;
10. only after the canonical B2 audit reaches zero blockers may B3 immutable DEV / HELD_OUT splitting begin.

### Immediate B2 work queue

The NEGATIVE axis is now complete for the minimum split-feasibility rule. The remaining work is:

1. **POSITIVE +1 — only remaining role deficit.**
   - prefer an existing B2 POSITIVE candidate if exact structure/representation closure is defensible;
   - LGPS has strong transport literature but partial Li occupancy makes an executable representation comparatively expensive;
   - cubic Al-stabilized LLZO and Li6PS5Cl remain alternatives only if their exact experimental disorder/occupancy can be represented without silently ordering the material;
   - do not choose a material merely because it is famous or highly conductive.
2. **Do not reopen the BORDERLINE axis without a new audit finding.**
   - `libh4-phase-transition-pair` and `llzo-tetragonal-undoped` already satisfy the minimum BORDERLINE count;
   - `li3ps4-nanoporous-beta` remains scientifically interesting, but surface/porosity effects must not be silently replaced by a periodic bulk proxy and it is not required for the current minimum split-feasibility deficit.
3. after each new scoreable material:
   - update the truth bundle catalog;
   - update sample-size observed counts and deficits;
   - update MLIP exposure coverage if the universe changes;
   - run Wave 2;
   - inspect `global_blockers` and `b3_split_authorized`.
4. when counts reach at least POSITIVE=2 / NEGATIVE=2 / BORDERLINE=2, require a fresh canonical B2 audit. Only a zero-blocker audit may authorize B3.

Do **not** assign DEV/HELD_OUT membership, run the benchmark, tune acceptance thresholds, unblind anything, or authorize Candidate Supply v2 while `SAMPLE_SIZE_POWER_RULE_UNSATISFIED` remains.

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
B2 Literature / Structure / Truth Curation       ← CURRENT
        ↓
B3 Immutable DEV / HELD_OUT Split
        ↓
B4 Blind Benchmark Ingress + Provenance
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

B2 is the current active phase.

The failure-control subtrack is closed, MLIP exposure accounting is complete, and executable/truth closure now exists for Li3N, Li2S, and gamma-LiAlO2. The NEGATIVE minimum is satisfied. The only canonical B2 blocker is the unsatisfied sample-size / split-feasibility rule, with the remaining deficit POSITIVE +1. B2 work should now close that deficit without weakening structure, evidence, or representation contracts.

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

No DEV/HELD_OUT membership has been assigned.

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

B2 is **not complete** until exact structures and sufficient B1 truth bundles are closed for a scientifically defensible benchmark universe.

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

1. satisfy the only remaining B2 scoreable-role deficit: **POSITIVE +1 / NEGATIVE +0 / BORDERLINE +0**;
2. keep the two curated BORDERLINE controls fixed unless a canonical audit exposes a new defect;
3. for every added scoreable material, require exact phase/composition identity, lawful retained structure evidence, and at least one source-bound scorable stage truth;
4. prefer reuse of the existing B2 universe before adding new materials, but add a new material when it removes a deficit more cheaply and more defensibly than forcing a scientifically poor representation;
5. update `sample_size_assessment_v1.json` from canonical truth-bundle state rather than by informal sample-adequacy judgment;
6. rerun Wave 2 after each promotion and inspect the canonical audit;
7. once counts are at least POSITIVE=2 / NEGATIVE=2 / BORDERLINE=2, require the canonical B2 coverage audit to report **zero blockers**;
8. only then freeze an immutable DEV / HELD_OUT split in B3;
9. construct blind ingress in B4;
10. execute and falsify on DEV in B5;
11. freeze science/acceptance logic in B6;
12. execute HELD_OUT exactly once in B7;
13. unblind and issue the qualification result in B8;
14. resume Candidate Supply v2 production **only if qualification permits it**.

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

As of `main = 769c91591f7805871e67b1744011997fa24c72a1`:

- Rhombus v1.0.0 remains the frozen historical baseline;
- the previous canonical production campaign produced 0 verified P2.5 DIFFUSIVE candidates;
- Candidate Supply v2 engineering exists, but production remains paused;
- B0 benchmark protocol and B1 source-bound truth contracts are implemented;
- B2 literature universe, structure binding, artifact retention, representation policy, coverage audit, model-domain snapshot, MLIP exposure accounting, and sample-size assessment infrastructure are implemented;
- the B2 universe now contains **9** source-grounded materials spanning **8** chemistry families;
- the pinned `medium-mpa-0` domain is retained and verified with 89 supported elements;
- all three canonical epistemic/system failure controls execute and pass;
- `li3n-crystalline` is a READY POSITIVE with curated P2.5 direct self-diffusion truth;
- `li2s-microcrystalline` is a READY NEGATIVE with conservative P0-only scoreability;
- `lialo2-gamma` is a READY NEGATIVE with curated P0 and P2.5 truth; direct 6Li tracer diffusion makes P2.5 `PASS` a falsifying false-positive classification;
- truth-bundle catalog contains **5 CURATED_FOR_B2** materials;
- direct P2.5 truth now includes the curated LiBH4 and tetragonal-LLZO BORDERLINE controls in addition to the earlier positive/negative controls;
- scoreable-stage counts are **P0=2 / P2.5=2**, all other stages currently 0;
- scoreable-role counts are **POSITIVE=1 / NEGATIVE=2 / BORDERLINE=2**;
- the only canonical B2 blocker is `SAMPLE_SIZE_POWER_RULE_UNSATISFIED`;
- remaining scoreable-role deficits are **POSITIVE +1 / NEGATIVE +0 / BORDERLINE +0**;
- `b3_split_authorized` remains false;
- no DEV/HELD_OUT benchmark split exists yet;
- no known-material benchmark execution has occurred yet;
- no qualification decision has been issued.

---

## Project Rule

**Rhombus should search broadly, validate conservatively, and record enough evidence that every scientific conclusion can be reconstructed, falsified, and challenged.**
