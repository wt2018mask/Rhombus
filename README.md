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

Canonical recovery checkpoint after PR #81:

```
main = b4b8d163532cc698f229ef72837ab646866a3cd8
```

If `main` has advanced beyond this SHA, inspect newer commits, open pull requests, and latest Actions runs before acting.

### Canonical benchmark state at this checkpoint

- B0 and B1 are complete.
- **B2 closure is complete: the canonical Wave 2 #118 audit reports `global_blockers = []`.**
- The minimum pre-split role-count rule is satisfied at POSITIVE=2, NEGATIVE=2, BORDERLINE=2.
- **B3 is frozen:** deterministic immutable DEV/HELD_OUT membership is canonical; do not reshuffle members to work around later B4 blockers.
- The B2 audit intentionally keeps `b3_split_authorized = false`; B3 authorization is a separate transition record that binds the zero-blocker B2 audit and satisfied sample-size assessment.
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
  - `llzo-cubic-al-stabilized` — POSITIVE; retained COD 7215448 fractional-occupancy reference; P0 SUPPORTED/scorable only, with no ordered executable proxy asserted.
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

### Immediate B4 work queue

1. preserve the now-closed 6/6 retained-structure provenance without changing frozen B3 membership;
2. close executable representation for cubic Al-stabilized LLZO without silent occupancy rounding or a single arbitrary ordered proxy;
3. continue the evidence-bound small-cell ensemble path: deterministic integer site assignment is canonical, while shared Li/Al-site mutual exclusion is the current implementation step;
4. harden blind execution with opaque benchmark IDs and explicit benchmark-protocol-hash binding before real execution;
5. define phase-set hashing/materialization semantics for LiBH4 rather than arbitrarily selecting one phase artifact;
6. do not run HELD_OUT, tune acceptance thresholds, unblind labels, or authorize Candidate Supply v2 during B4.## Scientific Status Summary

As of `main = 742eeda60e082ecbec0393de9b6ba522eeca9a90`:

- Rhombus v1.0.0 remains the frozen historical baseline;
- Candidate Supply v2 production remains paused;
- B0 and B1 are complete;
- **B2 is closed** with six CURATED_FOR_B2 truth bundles, role counts POSITIVE=2 / NEGATIVE=2 / BORDERLINE=2, and zero canonical global blockers;
- **B3 is frozen** with immutable deterministic DEV/HELD_OUT membership;
- **B4 is active**: all 6 frozen members have retained reference-structure provenance, while executable readiness is **5/6**;
- the sole current representation blocker is `llzo-cubic-al-stabilized`, whose retained COD structure contains fractional Li/Al occupancy and must not be silently converted to one ordered proxy;
- canonical B4 work includes a fail-closed fractional-occupancy strategy contract, exact-integrality/error/cost diagnostics, small-cell ensemble averaging diagnostics, ensemble-diversity requirements, and deterministic site assignment;
- literal refined occupancies require 1,250 conventional-cell replicas for exact integer realization, so the project is evaluating an explicit small-cell ensemble representation;
- PR #93 is the current follow-up implementing mutually exclusive Li/Al allocation on their shared crystallographic site pool; it is not canonical until CI passes and it is merged;
- no B5 DEV execution, B6 science freeze, B7 HELD_OUT execution, B8 unblinding, or qualification decision has occurred;
- no benchmark result authorizes Candidate Supply v2 production.

---


