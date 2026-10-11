# 0159-D/E original OBELiX equally budgeted screening and label-blind abstention

## Why change the metric?

Checkpoint 0157's public TRAIN group OOF RMSE/MAE gain (RF 1.62526468 → weighted RF 1.48588191 log10 MAE) was falsified for fully unseen anion proxy families at 0158: the weighted model had worse MAE in all four eligible source chemistry heldouts, S_ONLY 3.32781812 → 3.66335436. A lower mean regression loss need not mean useful material decisions. The approved scientific milestone E requires equal-compute candidate selection utility, while milestone D requires quantified OOD abstention.

## First-party frozen source test

- Immutable source NRC-Mila/OBELiX@4eaac889809dd489e3bae468c45d5c0e02b9147a; 478 official TRAIN, 121 public TEST completely reserved, 29 censored upper bounds excluded, 449 public TRAIN source rows with numeric log10 conductivity, 102 connected DOI/formula identity groups. Do not treat distinct source rows as independently certified physical specimens.
- Exact 0150/0158 original anion-proxy whole-family holdout and cross-family source-identity embargo. Refit same 0150 unweighted RandomForestRegressor and 0157 TRAIN-only group-balanced RF (same raw stoichiometry, source geometry, training-only imputation and RF_PARAMS).
- Fixed unknown-candidate *review budget* 10% and 20% of each genuinely withheld source chemistry class. Rank by source TRAIN-predicted log10 conductivity; baseline pre-frozen SHA-ranked blind random selection. Record mean actual measured-source label among selected candidates, oracle true top-budget hit count and recall. This is a retrospective source-label ranking simulation, not experimentally discovered material.
- For unchanged RF, freeze 25%, 50%, 75% acceptance by three entirely label-blind ranks: maximum cosine similarity of heldout elemental fractions to permitted training elemental fractions; lowest across-tree RF prediction disagreement; and SHA-seeded blind random acceptance. Evaluate accepted and abstained RF log10 MAE only after acceptance masks are fixed.
- Avoid score leakage: heldout labels are only used for postranking/offline source evaluation, never for building or selecting model, ranking, thresholds, or acceptance. No new model selection based on this previously studied source TRAIN set.

## Failure/qualification gates

Preserve unsupported families and negative screening outcomes. A good top-10% result on public TRAIN is a preliminary selection signal, not a prospective independent scientific discovery. If abstention does not reduce risk versus blind matched coverage, do not declare uncertainty effective. Default RF promotion remains prohibited after 0158 whole-family stress. P0-01/02/03 still BLOCKED, original public TEST completely untouched, no MLIP transport evidence, science NO-GO.

**Initial real-source Actions status:** PENDING first source job and final-head CI; see [original 0159 workflow](../.github/workflows/phase3-obelix-budget-selective-0159.yml).

## Executed original 0159 results — genuine original source job, not a mock fixture

[Actual pinned source GitHub Action #38150068258](https://github.com/wt2018mask/Rhombus/actions/runs/38150068258) succeeded with original public 449 numeric TRAIN rows, 102 connected DOI/formula groups, 121 public TEST unparsed. Source aggregate was published [here](https://github.com/wt2018mask/Rhombus/actions/runs/38150068258/artifacts/11705569479). The first execution's fixed uniform random order is a *single blind control*, NOT statistically sufficient evidence that random ranking always beats RF. We added an exact analytic uniform-random expectation: with N heldout source rows and top review K, expected oracle overlap K²/N and expected oracle recall K/N.

| Entire family excluded | N | Fixed top-10% review K | 0150 RF oracle hits | 0157 weighted RF hits | Blind uniform chance expected hits | Single SHA-blind draw hits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| O_ONLY | 307 | 31 | 2 | 2 | 3.13 | 2 |
| S_ONLY | 117 | 12 | 0 | 1 | 1.23 | 1 |
| HALIDE_NO_O_S | 14 | 2 | 0 | 0 | 0.29 | 1 |
| OTHER_NO_O_S_HALIDE | 11 | 2 | 0 | 0 | 0.36 | 1 |

**Interpretation:** At this strict unseen-family source holdout, no tested RF outperformed the analytic chance expectation in any of four families at the 10% top-conductivity budget. A source-row oracle overlap is not an independently measured future discovery; the 14-/11-row families' expected hits and observed successes are highly variable. More repeated independent blinded cohorts and group-aware sampling are required before claims about superior candidate selection.

### Fixed 50% acceptance and selective RF error

| Entire family excluded | Original RF all accepted MAE | Similarity-ranked accepted MAE | RF tree-disagreement ranked accepted MAE | One seeded blind 50% accepted MAE |
| --- | ---: | ---: | ---: | ---: |
| O_ONLY | 1.5351 | 1.7585 | 1.7810 | 1.2957 |
| S_ONLY | 3.3278 | 3.1082 | 3.2646 | 3.2182 |
| HALIDE_NO_O_S | 1.6050 | 1.0796 | 1.3026 | 1.6808 |
| OTHER_NO_O_S_HALIDE | 1.4132 | 1.7247 | 1.5646 | 1.3071 |

**Verdict:** chemistry similarity helps 50%-coverage MAE for S and halide in this retrospective source stress, but harms oxide and OTHER; ensemble-tree disagreement improves only halide compared with the one seeded random comparator. These results do **not** validate a universal error uncertainty score or reliable automatic abstention strategy. No method was selected by looking at these heldout labels. Next 0160-E should compare repeated blinded/randomized budgets and group-deduplicated candidate selection on a genuinely independent source corpus, keeping all original public TEST labels reserved.
