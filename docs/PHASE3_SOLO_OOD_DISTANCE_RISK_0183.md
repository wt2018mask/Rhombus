# 0183 — Solo original OBELiX public chemistry OOD risk mechanism comparison

## Why this analysis is needed

0181 verified lower retrospective source-group macro errors after RF ensemble-tree-disagreement ranking within five frozen group folds. 0182 tested strict harder whole **anion-element-presence proxy** family shift and found **O_ONLY** (307 rows, 64 connected DOI/formula groups) MAE **2.37930278** full, **2.66037906** at 60% source-group selection and **2.53356077** at 80%, all actual original source values. This is a negative finding: the RF-tree variance score can be overconfident about errors on a family never represented in training. S_ONLY, halide and OTHER did not all behave consistently. Public chemical proxies are not XRD-authenticated phases or independently validated specimens.

This 0183 test is a *post-failure explanatory* original-source experiment. Because 0182 public O_ONLY outcome was seen before choosing the new distances, no result here is a new confirmatory untouched blind benchmark. We must preserve that distinction even if a competing score happens to beat previous RF selectivity.

## Fixed source, embargo and three predeclared comparators

[Original implementation](../scripts/science/obelix_solo_ood_distance_risk_0183.py), [negative regression suite](../tests/test_phase3_obelix_solo_ood_distance_risk_0183.py) and [real CPU original-source workflow](../.github/workflows/phase3-solo-ood-distance-risk-0183.yml). Original NRC-Mila OBELiX upstream commit `4eaac889809dd489e3bae468c45d5c0e02b9147a`, 478 original public TRAIN (449 uncensored numerical, 29 censored excluded), 121 official TEST **never read, scored, or used for policy tuning**, 102 connected DOI/formula original TRAIN groups. Exactly the 0182 source family bins, 0158 **train-versus-entire-family AND group-identity embargo**, the unchanged original 0147 50-tree 118 fraction-only RF and fixed group budgets 60% and 80%. No external person, research lab, model weights, GPU or paid compute needed.

Compute on each eligible heldout source family (at least 10 rows, 3 unique connected groups, 20 embargo-safe training rows) three distinct **prediction-only** source-group risk rankings. First: RF standard deviation across its 50 trees on heldout rows, averaged within group, unchanged from 0182 and verified numerically. Second: nearest training fraction vector based on Euclidean distance across all 118 composition components, each difference scaled by **standard deviation computed from training source rows ONLY**, floored at **0.02** in fractional unit space to avoid zero-spread feature invisibility. Batch distance computation at 64 rows per block bounds memory. Third: **equal ordinal rank fusion 50/50** of the first two measures inside the particular heldout family (no fitted coefficient, no error-trained thresholds). All ranking/tie rules fixed before current 0183 experiment output.

For each method, keep **ceil(60% / 80% of DOI/formula source groups)** starting from lowest purported risk. Compute group macro original log10 conductivity MAE after sorting has been frozen, compare full family RF and cheap training-fold mean on exact same selected groups, plus **128** deterministic SHA256 blind uniform group selections at the same source-group coverage. Report every family including absent O_AND_S and thin cohorts. Original TEST remains quarantine. For smaller 6-group cohorts a rank correlation is deliberately NOT estimated and reported `null`.

## Admission and interpretation

0183 test is explanatory, **not eligible for a confirmatory GO decision**. Even if novel distance/fusion ranks reduce public source error, no newly adopted predictor, no calibrated uncertainty, no peer experimental verification or unique physical sample can be asserted. P0-01/P0-02/P0-03 remain BLOCKED and external physical science NO-GO, regardless of the sign of MAE change. Original model and publisher source hashes must be unchanged; any source-group overlap or numerical failure must FAIL CI rather than silently substitute synthetic labels.

**Actual original upstream public source Actions [#38731714276](https://github.com/wt2018mask/Rhombus/actions/runs/38731714276) SUCCESS**, science tests 12/12. [Aggregate-only scientific result artifact #11970196626](https://github.com/wt2018mask/Rhombus/actions/runs/38731714276/artifacts/11970196626) ZIP SHA256 `d79730da037592f6d8e2f1597ebc1ed187fb9aaee193fad76bbe4d370b358936`. No individual per-row conductivity values, source IDs, or model-selected test/heldout roster are publicly uploaded. Next 0184 should seek a separately published, chronologically newer or different-source **public** untouched benchmark cohort (available autonomously) to evaluate a newly *frozen* risk rule without scanning its answer first. No outside research participant is required.

## First-party original public TRAIN numerical results, including failures

Exactly 478 original TRAIN rows, 449 usable uncensored numeric, 29 censored excluded, 121 official TEST never read, 102 DOI/formula connected groups. All scored chemistry bins and their original 0182 group boundaries remained unchanged. This reproduces the original 0182 RF baseline for each scored family; only the *prediction-only* source-group review ranking changes.

| Anion-presence source class | Rows/groups | RF full macro | RF tree std rank 60% / 80% | TRAIN nearest-composition rank 60% / 80% | Fixed 50/50 rank fusion 60% / 80% |
|---|---|---:|---:|---:|---:|
| **O_ONLY** | **307 / 64** | **2.37930278** | 2.66037906 / 2.53356077 | **2.35845151 / 2.47303929** | **2.17761439 / 2.53767744** |
| S_ONLY | 117 / 21 | 2.35933897 | **1.91994298 / 2.30698472** | 2.76210036 / 2.52079592 | 2.28423457 / 2.39764836 |
| HALIDE_NO_O_S | 14 / 11 | 1.59042696 | **1.45482414 / 1.73860523** | 1.89882740 / 1.58190030 | 1.87771683 / 1.73860523 |
| OTHER_NO_O_S_HALIDE | 11 / 6 | 2.01306731 | **1.85468499 / 1.81930298** | 2.39211287 / 2.07071872 | 2.39211287 / 2.07071872 |
| O_AND_S | 0 / 0 | Not scored | Not scored | Not scored | Not scored |

All numeric risks are **DOI/formula-group-macro log10(S/cm) absolute errors**, lower is better. A fixed 60% O_ONLY fusion score **2.17761** is better than full O_ONLY **2.37930** and the predeclared 128-draw equal-group random mean **2.36652**. But at 80% it deteriorates to **2.53768**, worse than full and random mean **2.36615**. Nor does the same technique transfer to S_ONLY or HALIDE. A distance-only O_ONLY 60% risk **2.35845** improves only marginally relative to full; at 80% it also worsens.

**Strongest scientific consequence:** previously observed public chemistry-shift failure led to this distance choice. These values are exploratory diagnostics on *already inspected public data*; they are neither a fresh holdout for score comparison nor a basis to adopt a supposedly superior hybrid risk model. Original P0-01/02/03 remain BLOCKED, external physical GO remains NO-GO, all 121 official TEST remain unread. 0184 must freeze any contender BEFORE a different chronological/source-origin public evaluation cohort is used.
