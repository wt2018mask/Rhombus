# Checkpoint 0192 — Newly sourced six-hour Ta/Ga LLZO manufacturing choice

## Scientific scope

Rhombus must demonstrate a candidate selection/rejection advantage at equivalent free compute. Checkpoint 0191's manufacturing temperature/time Ridge improved two-paper MAE but achieved only 1/2 correct paper-level top-one manufacturing choices. Checkpoint 0192 evaluates **a new original-author published DOI**, not reusing either DOI to fit manufacturing residuals.

New genuine original author source: [ACS Omega 2022, DOI 10.1021/acsomega.2c06544](https://doi.org/10.1021/acsomega.2c06544), first-party JATS PMC9773338. The author prose reports two **6-hour** conditions, **1050°C and 1100°C**, each for five different nominal LLZO/Ta/Ga formulas with explicit total ionic conductivities in 10^-4 S/cm: 10 experimental preparation/reference conditions, five nominal formulas and ONE independent author DOI. These labels are public, now exposed and **not prospective sealed blind**.

### Precommitted admissibility controls

- Exclude *all* 12-hour source rows because the original authors add a mother-powder cover for that procedure, confounding a simple change in time/temperature. Preserve the excluded population (10 conditions), do not silently collapse to training.
- Verify actual publisher JATS DOI/PMCID, original authored numeric prose values and order, 25°C TOTAL observable context, BOTH units of 10^-4 S/cm in the prose, 6h source treatment and author original conductivity table presence. Original rendered Table 1 S/m versus text S/cm may be inconsistent: **derive exact target values only from the clear author prose** and explicitly record this source limitation, without converting from Table 1.
- Original OBELiX TRAIN fixed 478 entries/449 numeric; connected DOI+formula embargo now includes new source, original publisher TEST 121 never decoded. Learn frozen 0191 temperature/time Ridge(alpha=1) residual correction on 2018 + 2020 original-author conditions only. New 2022 DOI not used to fit or tune. Compare to frozen O_ONLY RF and source-training residual mean.
- Evaluate 10 heldout conductivity predictions and five **within-same-formula** binary 1050/1100 temperature decisions. Report author-out MAE, paired success, abstention, log-conductivity regret, and compare **the trivial always-choose-1100°C rule**. All five observed authors' paired sources favor 1100°C; any model scoring five successes is therefore not proof of better decisions than the heuristic.
- Flag 5/10 candidate conditions at 1050°C as lower than both older training-paper domains (minimum 1100°C). Temperature-range OOD predictions are not automatically deployable.

This remains a one-new-DOI, retrospectively published, non-physically independent evaluation. Physical P0-01/02/03 BLOCKED, O_ONLY router OFF, no science GO.

## Code and execution

Original author intake and frozen heldout evaluator: [0192 science module](../scripts/science/obelix_solo_oxide_new_source_0192.py). Hostile source tests: [0192 adversarial tests](../tests/test_phase3_obelix_solo_oxide_new_source_0192.py). Real-source CPU workflow: [0192 Actions](../.github/workflows/phase3-solo-oxide-new-source-0192.yml).

Next 0193: source-distinct studies that feature differing manufacture-temperature optima; meaningful candidate decision baselines beyond a trivial hotter-rule and out-of-range abstention. If original author source cannot be authenticated, record the failure and leave scientific qualification INCONCLUSIVE.
