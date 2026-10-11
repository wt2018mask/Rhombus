# Milestone A checkpoint 0148 — why all fixed baselines failed

**Study question:** what explains the observed [0147 real source-train grouped results](https://github.com/wt2018mask/Rhombus/actions/runs/38125387307) on original OBELiX: mean log10 MAE **1.86702336** versus RF **1.94487886**, MLP **2.26334295**, Ridge **2.29511512**? Find useful falsifying evidence before changing models, tuning, predicting official TEST, or expanding expensive MD.

## Pre-registered descriptive audit (read-only with respect to models)

1. Re-run the exact source-bound original 478 TRAIN / 121 reserved TEST, reconstruct original **449 numerical uncensored TRAIN labels**, and 102 connected DOI/raw+reduced formula identity groups, with original 0146 deterministic five folds. **No new split, no tuning, no resampling to obtain a better result.**
2. Re-run identical 0147 fixed RF/MLP and 0146 Ridge/fold-mean, retain row-level original labels and predictions in **temporary memory only**. Produce small aggregate-only artifacts; never upload raw labels, identifiers, per-record predictions, private specimen identity, source records or model binary.
3. Audit **record-weighted vs group-macro scoring** and group size concentration (largest connected source group; top-5 group fraction; Kish group effective count). Source groups are leakage barriers, NOT scientifically independent experiment units. All confidence-like intervals are **descriptive heuristic cluster-resampling**, NOT sample-level statistical generalization claims.
4. For each fixed model and mean, report paired, group-macro model-minus-mean **absolute-error difference** plus fixed-seed 512-resample heuristic interval. Do not adjust frozen models based on this retrospective audit; an interval crossing zero is an unresolved diagnostic result, not proof of equivalence.
5. Report model MAE for **predeclared mutually exclusive chemical-anion proxy bins**, based solely on elemental composition: `O_AND_S`, `O_ONLY`, `S_ONLY`, `HALIDE_NO_O_S`, `OTHER_NO_O_S_HALIDE`. These are descriptive covariates, NOT experimentally authenticated structural families. Each bin's scores are revealed only with >=10 source records AND >=3 connected groups; otherwise suppress model metrics and state exclusion.
6. Report all-five-fold spread of target log10 value, mean/baselines and full coverage. Do not claim source recorded room-temperature values have identical real Kelvin, bulk/total or standardized measurement conditions.

## Publisher implementation gap (verified from exact upstream source)

[Official OBELiX parse.py](https://github.com/NRC-Mila/OBELiX/blob/4eaac889809dd489e3bae468c45d5c0e02b9147a/benchmark/parse.py) uses **raw elemental stoichiometric amount** vectors with observed-element columns plus **space-group number and six cell parameters**; [RF.py](https://github.com/NRC-Mila/OBELiX/blob/4eaac889809dd489e3bae468c45d5c0e02b9147a/benchmark/RF.py) and [MLP.py](https://github.com/NRC-Mila/OBELiX/blob/4eaac889809dd489e3bae468c45d5c0e02b9147a/benchmark/MLP.py) use publisher-tuned/grid-searched hyperparameters under their original CV approach, standardized cell geometry columns and source `processed.csv` label transforms. They do **NOT** implement the 0146 identity-connected group folds; there is no basis for comparing their published error numbers to 0147/0148 directly. Original `processed.csv` includes transformed/censored values; 0146–0148 exclude original 29 strict upper-bound records from point-MAE, so targets differ too. The independent source evidence is a pinned upstream Git checkout and read-only audit of exact source scripts, never evaluating original TEST.

## Scientific stop lines

- Same holdout group per model; no train/test DOI/composition leakage; no official 121 public TEST label read or score.
- Genuine original source and models fixed; publisher scripts inspect-read-only; no exact paper reproduction, no new model quality claims, no independent physical sample count from source groups.
- P0-01 new independent blind, P0-02 exact MACE-MPA-0 selected training-frame exposure and P0-03 adequate independently paper/phase/temperature-audited physical samples remain **BLOCKED**.
- A is not closed by this checkpoint if all models remain worse than fold mean. Next `0149-A` should challenge whether richer *training-only* publisher-inspired features or measurement inconsistency explain failure, without a posteriori claiming scores of retuned models are unbiased.
