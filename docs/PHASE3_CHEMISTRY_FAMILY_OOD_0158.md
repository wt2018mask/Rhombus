# 0158-A/D — actual original OBELiX unseen chemical-family transfer falsification

**Goal:** Falsify whether 0157's genuine but retrospective public TRAIN 0146 DOI/formula-group OOF RF MAE gain (1.62526468→1.48588191) generalizes when the **entire chemical family is absent from training**, even though only source group training data were previously held out.

**Source, code, protocol:** Original immutable `NRC-Mila/OBELiX@4eaac889809dd489e3bae468c45d5c0e02b9147a`: 478 official TRAIN, 121 official TEST reserved-unread, 29 upper bound labels excluded, 449 valid numeric TRAIN source rows in 102 connected DOI/formula groups. [0158 original source CPU Action](https://github.com/wt2018mask/Rhombus/actions/runs/38148543442) actually cloned this commit and executed [script](../scripts/science/obelix_family_ood_weighted_rf_0158.py) with synthetic negative tests. Reused exact 0150 anion-proxy heldout-family definitions and group embargo. Compared unchanged 0150 RandomForestRegressor to frozen 0157 inverse-sqrt connected-group TRAIN weight with **same features, model, hyperparameters, and training folds**. Included cheap mean from *outside* the family. No heldout label used in fitting, tuning, weighting, or imputation; no public TEST label/feature parsed.

## Actual numerical observations (log10 conductivity MAE; lower is better)

| Entire family excluded from training | Source TRAIN label rows heldout | Original 0150 unweighted RF | 0158 frozen group-balanced RF | Balanced vs original MAE (positive = worse) | Balanced vs outside-family cheap TRAIN mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| O_ONLY | 307 | 1.53510261 | 1.54580638 | **+0.01070377** | −0.15513882 |
| S_ONLY | 117 | 3.32781812 | 3.66335436 | **+0.33553624** | **+1.39442714** |
| HALIDE_NO_O_S | 14 | 1.60502714 | 1.65080353 | **+0.04577639** | **+0.09566185** |
| OTHER_NO_O_S_HALIDE | 11 | 1.41318765 | 1.44332988 | **+0.03014223** | −0.42463466 |
| O_AND_S | 0 | excluded | excluded | N/A | N/A |

**Result: negative in all four eligible unseen-family tests.** The weighted 0157 model learned useful relationships for original mixed-chemistry source-group CV, but **its improvement does not transfer to whole unseen chemistry-family exclusion**. S_ONLY transfer is substantially worse than cheap outside-family mean. Source group sizes, source paper correlations, dopant composition, phase, conductivity labels and chemistry proxies complicate interpretation; the diagnostic does not identify causality.

**Strict scientific verdict:** Do not promote 0157 balanced RF to the default for novel chemistry, nor claim its retrospective performance was invalid or falsely measured. Keep the original 0157 same-fold improvement as an explicitly scoped source TRAIN diagnostic and the new 0158 external-chemistry negative results simultaneously. Actual experimental independent material samples **zero**, P0-01/02/03 BLOCKED, no MLIP-MD transport, no science GO.

**Next 0159-D:** Test risk/coverage, within-TRAIN calibrated error prediction and abstention for family-source OOD; report bad coverage, abstention rates and cheap-baseline advantage/failure, not another unchecked RF-weight search. Do not touch original public TEST or reuse heldout labels in model fitting.
