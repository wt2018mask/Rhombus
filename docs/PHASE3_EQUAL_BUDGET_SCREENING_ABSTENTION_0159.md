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
