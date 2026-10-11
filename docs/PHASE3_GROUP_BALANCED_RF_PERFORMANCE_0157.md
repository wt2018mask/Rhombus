# 0157 — Real original-source predictive performance improvement experiment

**Objective:** Change actual Rhombus predictive behavior and measure whether it reduces errors on known public OBELiX TRAIN grouped CV. This is deliberately not another CIF/paper checkpoint. Per [approved A–E scientific roadmap](SCIENTIFIC_EVIDENCE_MILESTONES_A_E_0147.md), science GO requires genuine unknown-material selection benefit under equal compute, far beyond public TRAIN retrospective gain.

## Single falsifiable change

The [0150 original real-source stress](https://github.com/wt2018mask/Rhombus/actions/runs/38129121068) found negative out-of-chemistry generalization. Five largest connected source groups cover about **59.24%** of the source rows. This creates a clear inductive hypothesis: imbalance during model fitting may affect the geometry-assisted RF's source transfer.

Reuse actual original `NRC-Mila/OBELiX@4eaac889809dd489e3bae468c45d5c0e02b9147a`: **478 TRAIN**, **121 public TEST reserved-unparsed**, **29 censored upper bounds excluded**, **449 original legitimate uncensored numeric source records**, and **102 DOI/composition-transitively-connected groups**. Frozen five heldout splits from 0146 unchanged. Exactly the same original source raw elemental counts and seven-spacegroup/unit-cell geometry fields and fold-TRAIN-only missingness imputation as 0149; **unchanged RF parameters** (50 trees, max_depth=12, max_features=sqrt, min_samples_leaf=2, random_state=147). The one intervention is **TRAIN-only source group row weight** `w_i ∝ 1/sqrt(N_group_in_outer_training_fold)`, normalized to average weight 1. Never use heldout groups, heldout labels or public TEST rows to compute fit statistics.

## Actual performance comparisons, fixed

- Existing [0146 group-holdout fold TRAIN mean](https://github.com/wt2018mask/Rhombus/actions/runs/38122882464): log10 MAE **1.86702336**.
- Existing [0149 original raw-counts + source-geometry RF](https://github.com/wt2018mask/Rhombus/actions/runs/38127945076): log10 MAE **1.62526468**, public TRAIN retrospective only.
- New 0157 group-balanced same RF: **PENDING ACTUAL SOURCE CPU RUN**. Report paired change in row-weighted log10 MAE; equal connected group macro MAE, fixed group bootstrap interval (NOT independent physical confidence), five heldout fold errors, original anion-family proxy slices, negative results and computation identity. **Do not modify weights to chase result or declare model superiority from inspecting this retrospective fivefold set.**

Report explicit improvement only if numerical paired comparison is positive; no change to P0, original TEST or external blind status. Next **0158-A** should use fixed independent chemical family heldout to test whether any gain survives genuine source shift; if worse than prior 0149/0150, reject the model rather than tuning on the same evaluation rows.

## First actually executed numerical result — 0157 real original source

[Actual original OBELiX TRAIN source GitHub Actions #38146722873](https://github.com/wt2018mask/Rhombus/actions/runs/38146722873) **SUCCESS** at head `b1bee34d626760a57b9f538e204ceb5e2a2698af`, using exact pinned source commit and frozen 0146 five heldout source DOI/formula groups. The [source-bound published aggregate artifact](https://github.com/wt2018mask/Rhombus/actions/runs/38146722873/artifacts/11704867927) is ZIP SHA256 `554f66c799436c171bcd2086c3f58e4f0489c9d31980bbf91f495731185584be`, and contains **aggregate metrics only**, no actual original source-row labels or feature values.

| Actually evaluated frozen source model | Source-record-weighted log10 MAE (lower better) | Equal-source-group macro log10 MAE |
| --- | ---: | ---: |
| 0146 training-fold mean baseline | 1.86702336 | 2.26818583 |
| 0149 same-feature unweighted RF | 1.62526468 | 1.66954551 |
| **0157 predeclared TRAIN source-group-balanced RF** | **1.48588191** | **1.64649874** |

Actual paired improvement on the 449 scored source TRAIN rows is **0.13938277 log10 MAE**; relative to 0149 RF this is approximately **8.6%**. The improvement occurred within all five original fixed heldout fold row-weighted MAEs. Fold one had a **single 107-row connected group**, making row-weighted results strongly source-group-weighted: the macro paired group advantage is just **0.02304677**. A 512-resample *heuristic* connected source-group paired-delta bootstrap yielded **[−0.10568478, +0.06600920]** and includes zero. It is **not** a confidence interval over independently authenticated experimental material specimens.

### Chemistry-family negative result

| Original composition-anion proxy | Original source records | 0149 RF log10 MAE | 0157 balanced RF log10 MAE | Verdict within public TRAIN OOF |
| --- | ---: | ---: | ---: | --- |
| O_ONLY | 307 | 1.61038498 | 1.47219120 | Improved |
| S_ONLY | 117 | 1.63160629 | 1.45167472 | Improved within mixed outer source-fold setting; **not** proof of genuine leave-S-only-family-out transfer |
| HALIDE_NO_O_S | 14 | 1.83174291 | **1.94413273** | **Worsened**, also worse than cheap mean 1.50061445 |
| OTHER_NO_O_S_HALIDE | 11 | 1.71030137 | 1.64858895 | Improved on 11 public source records |
| O_AND_S | 0 | unavailable | unavailable | No source sample |

**Result:** source-group balancing is a promising, quantitatively improved **retrospective public TRAIN regression candidate**. It has **not** passed an independent prospective or blind benchmark. It has **not** passed the previously concerning 0150 **genuine leave-S-only-chemistry-family-out training** test; S_ONLY improvement in the old source-group folds cannot substitute for that test. The halide reversal, very small equal-group gain and bootstrap interval crossing zero are meaningful red-team warnings. Do **not** adopt it as an unqualified default/inference production winner; next checkpoint 0158-A should evaluate frozen independent chemistry-family shift in train-only source-group-balanced retraining against original 0150 unweighted RF with exact joint group embargo. No TEST access, no hyperparameter search on heldout, no P0 closure, no scientific GO.
