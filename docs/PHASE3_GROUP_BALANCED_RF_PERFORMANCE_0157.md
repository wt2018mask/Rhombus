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
