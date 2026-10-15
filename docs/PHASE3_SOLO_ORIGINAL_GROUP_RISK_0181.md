# 0181 — Solo genuine OBELiX TRAIN source group risk and group-size sensitivity

## Aim and source boundary

The one-person execution path from [Issue #349](https://github.com/wt2018mask/Rhombus/issues/349) requires **numeric evidence, not partner recruitment or source metadata checkpoint growth**. Earlier source runs 0146–0180 revealed opposite row and DOI/formula-connected-group error conclusions, so this 0181 original-source study asks whether a **prediction-only** RF tree-disagreement score can identify riskier original heldout source groups under **predeclared equal group review budgets**, without pretending they represent independent physical specimens.

[Code](../scripts/science/obelix_solo_group_risk_0181.py), [CI original data experiment](../.github/workflows/phase3-solo-group-risk-0181.yml) and [negative tests](../tests/test_phase3_obelix_solo_group_risk_0181.py) reuse upstream [NRC-Mila OBELiX](https://github.com/NRC-Mila/OBELiX) exact commit `4eaac889809dd489e3bae468c45d5c0e02b9147a`: 478 original public TRAIN, 121 official TEST entirely reserved and unread, 449 uncensored eligible numeric original TRAIN source records, 29 censored excluded and 102 connected source DOI/formula groups. The five original 0146 heldout folds and the fixed 0147 RF with 50 trees are unchanged. We validate original RF row log10 MAE 1.94487886 and fold mean 1.86702336 and connected-group RF macro 1.90046024 vs mean 2.26818583. All original source row IDs and labels remain ephemeral.

## Freeze before live outcome and anti-leakage

For each original outer fold, train RF only on complementary public TRAIN source groups. Predict heldout group rows, compute standard deviation across the 50 individual RF tree predictions, but **do not use outer truth** to calculate uncertainty or selection rank. For each heldout connected DOI/formula identity, aggregate the row-level tree standard deviations (mean) into one proxy. Sort increasing uncertainty, break ties by the source group identifier, select **ceil(0.6×102)=62** and **ceil(0.8×102)=82** source groups. Only then examine heldout original true numeric conductivity source labels to compute each selected group's MAE. The same selected groups are also evaluated using the frozen cheap fold mean; random baselines use **128** SHA256 deterministic pseudo-blind uniform group priorities per coverage, not source-row shuffling.

Also stratify all connected source groups by **1 row, 2–5 rows, and ≥6 rows**, report group and source-row counts, their separate macro errors and five largest group concentration. Report Spearman rank association of tree dispersion vs absolute prediction errors at the *source connected group* level. A high disagreement is a **heuristic model diversity proxy, not validated measurement uncertainty or calibrated physical confidence**. These are retrospective **exploratory** diagnostics because the earlier 0180 source outcomes motivated this task.

A narrow public diagnostic is PASS iff both 60% and 80% selected-group macro MAE are below full-group macro MAE and the average of 128 matched group-random priorities, with positive dispersion/error Spearman. This was authored before the live 0181 result. Other cases are FAIL or INCONCLUSIVE, but NO result can grant historical external/physical independent-science GO.

## Actual original source execution and raw metrics

[GitHub Actions #38719549508](https://github.com/wt2018mask/Rhombus/actions/runs/38719549508) **SUCCESS**, 38 anti-leakage/scientific fixture tests and actual source model computation. [Public aggregate-only artifact #11963803220](https://github.com/wt2018mask/Rhombus/actions/runs/38719549508/artifacts/11963803220) ZIP SHA256 `50b41656c2c14b732f72d23a42532d7f14385960520cc8414c5ef863130ce4ce`. All numbers below from that original machine-computed JSON.

| Fixed source-group review budget | Selected groups | Source rows inside selected groups | RF group macro log10 MAE | Cheap mean on same selected groups | Blind group-random mean MAE (128 draws) | Blind draws with ≤ achieved RF risk |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 100%, no rejection | 102 | 449 | 1.90046024 | 2.26818583 | N/A | N/A |
| 80% | 82 | 411 | 1.72116918 | 2.17336811 | 1.90938029 | 0.015625 |
| 60% | 62 | 268 | 1.64083379 | 2.10047985 | 1.91185783 | 0.0390625 |

**Group-wise Spearman tree disagreement → actual heldout error: 0.30418262**. This positive but moderate relation should not be described as strong calibration. Fixed diagnostic = **`PASS_RETROSPECTIVE_GROUP_RISK_SIGNAL_ONLY`**, not universal predictor superiority. The 80% group selection covers 411/449 source rows (91.5%); the 60% group selection covers 268/449 (59.7%). This asymmetry demonstrates why no percentage may be described without denominators.

Group-size evidence: **61 one-row groups** (61 source rows, RF macro 2.00816747, mean 2.38985688); **31 two-to-five-row groups** (77 rows, RF macro 1.62591898, mean 2.02006953); **10 groups with ≥6 rows** (311 rows, RF macro 2.09452412, mean 2.29515293). Largest one contains **107** source rows; five largest account for **266 of 449 (59.24%)**. This source concentration plausibly contributes to the apparent source-row vs equal-group disagreement and deserves future out-of-publication uncertainty study.

## Science limitation and next solo-only experiment

The whole data source is public and previously inspected; multiple related source rows share experimental lineage. None is an attested independent physically identical pellet, true prospective blind or externally audited MPA-0 training exposure. **P0-01/02/03 remain BLOCKED; original external physical science NO-GO.** Only the retrospective, original-public-data group risk signal criterion can PASS here. Published original 121 TEST are not a new hidden test set to optimize on.

For 0182 prioritize a same-budget source-/chemistry-family-out uncertainty and abstention test, with a frozen model, train-only threshold choices and failure counts. It remains solo/free-compute. Avoid external laboratory involvement as a required next step.
