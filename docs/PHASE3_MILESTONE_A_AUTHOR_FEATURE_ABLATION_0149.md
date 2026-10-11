# Milestone A — checkpoint 0149: fixed-fold publisher-feature ablation (exploratory)

**Approved question:** Do the missing original author's raw stoichiometric features and published lattice/space-group fields explain the failure of fixed composition-only RF/MLP on original uncensored public OBELiX TRAIN? This is a **hypothesis-generating post hoc feature ablation**, not fresh blind validation, not original-paper replication, and not scientific GO.

## Frozen experimental protocol — no test tuning

- Original public OBELiX source commit `4eaac889809dd489e3bae468c45d5c0e02b9147a`, 599 original rows, 478 official TRAIN, 121 original public TEST reserved; original raw workbook identifies 29 strict upper bound labels, never treated as numeric point truths. 449 numeric TRAIN source rows scored.
- Reconstruct exactly the same **102 connected DOI/reduced formula groups** and **five heldout folds** as 0146/0147. Zero official TEST rows may be used for feature construction or model training; source ID-only whitelist is used to filter CSV before any feature field parsing.
- Compare the already frozen original **normalized fractional 118-element** RF/MLP/mean/ridge scores to exactly two predeclared **additional feature arms**, no grid search: (i) raw *stoichiometric atom counts*, (ii) raw stoichiometric atom counts **plus seven publisher available metadata columns** `Space group number`, `a`, `b`, `c`, `alpha`, `beta`, `gamma`. Missing geometry uses **train-fold-only median imputation**, with missingness indicators (never hide missing fractions). Experiment-family conditions are **not** independently verified.
- Reuse **identical fixed RF/MLP hyperparameters, seeds and original official uncensored labels** as 0147. For MLP fit all feature scaling on training-fold only; for RF keep raw features, with geometry-only train-median imputation. No hyperparameter selection on heldout error.
- The source checksum must equal the 0146 attested processed.csv digest. Exactly the `source_entry_id` 449 model input rows are admitted. Missing/unknown geometry may be imputed for a *purely predictive* control, not interpreted as a physical structure and not used for atomistic MACE.
- Report per-model OOF MAE and RMSE, fold counts and errors, group-macro delta versus mean, feature missingness, and source/TEST inclusion boundaries. No per-row predictions/labels/DOIs/chemical formula/physical identifiers in output.
- Read publisher `benchmark/parse.py`, `RF.py`, `MLP.py` and compare the exact features/behavior. Publisher's implementation uses raw stoichiometry and available lattice parameters plus space-group; **their CV grids, processed target values and original TRAIN/TEST policy are materially different**. This experiment is NOT an exact recreation of the publisher paper's results.

## Stop condition

Prior real 0147 original source-row group-OOF log10 MAE: **mean 1.86702336**, RF **1.94487886**, MLP **2.26334295**, Ridge **2.29511512**. If one predeclared new arm performs better, label as **retrospective exploratory improvement on repeatedly examined groups**, not an independently estimated generalization gain; require future sealed/fresh or genuinely held-out chemistry-family assessment to qualify. If none beats the mean, preserve negative results, investigate paper/measurement conditions before expensive physics. **All Red Team P0-01/02/03 remain BLOCKED.**

## Prior 0148 scientific findings

Largest connected source group has 107 original TRAIN numeric rows and the largest five groups contain 59.24% of the 449 source entries. Record and equal-group macro scoring reverse the RF-vs-mean direction; these are non-IID public source connected components and cannot establish true independent physics.

**Next 0150:** review whether 0149 feature comparison showed a *reproducible* signal, document group/chemistry error and source missingness; continue Milestone A or start Milestone B only after stating negative and unqualified outcomes. Keep approved A→B→C→D→E evidence-first priorities in `README`, `CURRENT`, `HANDOFF`.
