# Phase 3 science checkpoint 0134 — censor-aware TRAIN-label policy

## Why this is now the highest-priority science correction

The [actual frozen OBELiX source check](https://github.com/wt2018mask/Rhombus/actions/runs/38104837290)
confirmed original `raw.xlsx` has **37 experimentally censored upper
bounds** whose inequalities were replaced with artificial numeric
`1e-15` in the upstream `processed.csv`. The 37 consist of **29
original TRAIN** and **8 original TEST**. The original TRAIN limits
are 28 `<1E-10` and 1 `<1E-8` S/cm.

Checkpoint 0134 implements the **safe diagnostic label policy**, not
model accuracy or scientifically accepted performance.

## Policy invariants

- `UPPER_BOUND_EXCLUSIVE`: preserve the actual original strict upper
  bound, e.g. `sigma < 1E-10 S/cm`. The original processed
  `1e-15` stand-in is **never an exact regression target** and is
  removed from the point-metadata field.
- `SOURCE_NUMERIC_UNVERIFIED`: original positive numeric source
  metadata may be retained for an independently governed future
  experiment review, but it is **not automatically verified physical
  ground truth**. Temperature, structural phase, bulk vs total
  conductivity, defects, sample identity, DOI and MACE selected training
  frames remain unverified.
- `SOURCE_NONNUMERIC_UNRESOLVED`: no numeric scientific target without
  resolving the original source.
- `point_estimate_benchmark_scoring_permitted=false` for **every
  source record** until independent experimental verification exists.
  The scientific trial is not automatically approved simply because
  the data appears in a public experiment table.
- All 478 official TRAIN records are output once; **no official TEST
  record ID or measurement appears** in the developer worklist. Original
  official TEST 121 and censored TEST 8 remain available only as
  aggregates, not a newly independent secret blinded trial.
- Original 0133 evidence is **recomputed directly** from a clean
  pinned OBELiX Git checkout and verified by exact equality against
  previously persisted 0133 files and SHA256. Tampered reviewed
  values, previous science summaries and stale raw files fail closed.

## Interval violation semantics — diagnostic only

Given *positive* predicted conductivity `s` and original exclusive
upper limit `u` (in **S/cm**):

```text
satisfies_exclusive_bound = (s < u)
diagnostic_violation_log10 = max(0, log10(s / u))
```

At exact equality `s = u`, the distance is zero but
`satisfies_exclusive_bound = false` because the original source
used a strict `<`. The distance is a numeric **constraint
diagnostic**, not a scientific material score, loss to silently combine
with pointwise residuals, or estimate of held-out generalization. This
distinction is regression-tested. No diagnostic value can confer a
scientific PASS, regardless of how many samples satisfy their limits.

Code: `scripts/science/obelix_censor_aware_policy.py`.
Regressions:
`tests/test_phase3_obelix_censor_aware_policy.py`.
Run:

```powershell
py -3.11 scripts/science/obelix_censor_aware_policy.py `
  --obelix-checkout "C:\\path\\to\\OBELiX" `
  --evidence-dir "C:\\path\\to\\obelix-0130-evidence" `
  --raw-lineage-dir "C:\\path\\to\\obelix-0133-raw-censor" `
  --output-dir "C:\\path\\to\\obelix-0134-evidence"
```

Task-specific workflow
`.github/workflows/phase3-obelix-real-source.yml`
runs the *actual* pinned source through 0127–0134, requires 478
TRAIN policies, **29 censored inequality constraints**, **449
other original numeric but independently unauthenticated source
records**, and 0 scientific point targets, then uploads a separate
14-day SHA-bound GitHub Actions artifact
`obelix-0134-train-censor-aware-policy`.

## First real pinned-source 0134 execution — verified

The task-specific [original-source workflow run #38105809420](https://github.com/wt2018mask/Rhombus/actions/runs/38105809420)
**PASSed** on Rhombus SHA
`7711ac88f84350e27fae0049b177cc68edefbc36`.

The actual `obelix-0134-train-censor-aware-policy` evidence artifact
(ID `11689796637`) was downloaded and independently rehashed:

- **478** TRAIN source policy records, all retaining the original ID.
- **29** original strict upper-bound constraints, never exact scored points.
- **449** numeric values that remain **unverified experimental metadata**.
- **121** public official TEST records (including **8** censored) represented
  **only in aggregate**.
- **0** independently qualified point targets or scientifically approved
  materials.

Exact JSONL SHA-256:
`9d6b64195058b48286f24ba0ec29605888855dfc9b3399a67dfeca3db7757f2c`.

ZIP SHA-256:
`d7bf2669424b3c7ba3e81293610ed36279434fe1042691a0f1f8da53fc942d79`.

The final PR head must still pass the full CI set before merge. This
is a correct source-label *policy run*, **not** a scientific transport
accuracy or generalization measurement.

## Larger benchmark, without scientific shortcuts

This correction is necessary before scaling to multiple datasets:
all external records should use the same distinctions between
censored observations, original reported numeric observations,
incompatible physical quantities and independently authenticated
experimental truth. **Number of records, number of structures,
number of resolved source samples and independently qualified
materials are four different denominators.**

Next checkpoint (**0135**) should build a bounded source-neutral
multi-dataset intake contract and cross-source paper/temperature/
phase identity review as an independent small PR. It must not
merge OBELiX with LiIon/Shon–Min records without their individual
source hashes, measurement quantity and temperature requirements.
Statistical sample-size and external blind-study gates remain P0
blockers. **Scientific verdict is INDETERMINATE / NO-GO.**
