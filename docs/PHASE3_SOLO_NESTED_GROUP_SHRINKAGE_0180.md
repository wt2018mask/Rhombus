# 0180 — Solo nested group-CV shrinkage experiment on genuine original public OBELiX TRAIN

## Research question and solo execution

A genuinely runnable no-external-help experiment: can choosing an RF/cheap-mean blending weight *inside TRAIN only* improve measured retrospective grouped original conductivity prediction relative to the earlier negative 0147 model outcome? Prior frozen 0147 actual source MAE was RF **1.94487886**, MLP **2.26334295**, ridge **2.29511512**, TRAIN fold mean **1.86702336** log10(S/cm), so RF and MLP were **worse**. Merely rerunning full RF cannot be marketed as improvement.

The 0180 code starts from `scripts/science/obelix_real_grouped_oof_0146.py` with the original pinned upstream public OBELiX commit `4eaac889809dd489e3bae468c45d5c0e02b9147a`: 478 original TRAIN, **449 eligible uncensored numeric** source observations, 29 censored excluded, 102 connected DOI/formula groups. The untouched original **121 TEST entries are never read/scored/used for tuning**. The exact original five 0146 outer folds and fixed 118 fraction descriptors are never repartitioned. Training data are public and the evaluation remains retrospective.

## Fixed before any 0180 outer validation result

For each original outer fold: use its TRAIN rows exclusively to allocate connected group IDs to three inner folds in a reproducible SHA256 identity-only hash order. Fit the unchanged original RF hyperparameters on inner training rows and compute inner heldout TRAIN-only predictions. For weights `[0, 0.25, 0.50, 0.75, 1.00]`, blend inner RF and the corresponding inner training mean. Choose the lowest **group-macro** absolute log10 residual in this private inner training calibration, with ties preferring the cheap mean. Then fit unchanged frozen 0147 RF on the entire outer TRAIN and score the selected blend on previously untouched **outer heldout** once. No observed outer test outcome, chemistry-family tuning loop, public original TEST or user-chosen posthoc weight selection enters the decision.

Immutable baseline errors must be reproduced exactly or terminate; all group identities, full source/label policy SHA provenance and failed trials are reported. Same source-DOI connected groups are not IID independently synthesized or measured pellets. Paired 512-replicate group bootstrap confidence intervals are **diagnostic**, not a physical prospective population confidence certificate.

## Explicit public benchmark decision and external truth separation

`SOLO_PUBLIC_BENCHMARK` is PASS only if measured source row MAE and connected-group macro MAE are both smaller than cheap mean AND the heuristic bootstrap 95% paired improvement interval is wholly below 0. FAIL if both row and macro scores fail to beat the cheap mean. Otherwise INCONCLUSIVE. This is a **fixed retrospective public benchmark criterion** rather than verified generalization to unseen physical materials. Code records values even if the experiment fails, and does not substitute CI execution success for model superiority. Compare to original RF and mean, report full 5-fold selected shrinkage coefficients, error/group diagnostics and evidence lineage.

Original pretrained MACE-MPA-0 may have unknown source training exposure, so it is not offered as an independently no-leak confirmation. Existing external P0-01, P0-02 and P0-03 remain BLOCKED, new experimental pellets 0, physical science NO-GO. No external lab, contributor, steward, signed manifest, paid cloud or model supplier answer is needed for this public retrospective experiment.

[Actual GitHub CPU original source workflow](../.github/workflows/phase3-solo-obelix-nested-shrinkage-0180.yml), [numerical/group leakage tests](../tests/test_phase3_obelix_solo_nested_shrinkage_0180.py), [implementation](../scripts/science/obelix_solo_nested_shrinkage_0180.py). First actual whole-source Actions execution status **PENDING**; no declared numerical gain in advance. Next 0181 after this actual result: group-heldout calibration/risk-coverage and leave-chemistry-family-out public source utility under fixed budget; document failures.
