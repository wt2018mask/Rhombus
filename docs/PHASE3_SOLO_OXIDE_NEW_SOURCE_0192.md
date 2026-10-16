# Checkpoint 0192 — Newly sourced six-hour Ta/Ga LLZO manufacturing choice

## Scientific scope

Rhombus must demonstrate a candidate selection/rejection advantage at equivalent free compute. Checkpoint 0191's manufacturing temperature/time Ridge improved two-paper MAE but achieved only 1/2 correct paper-level top-one manufacturing choices. Checkpoint 0192 evaluates **a new original-author published DOI**, not reusing either DOI to fit manufacturing residuals.

New genuine original author source: [ACS Omega 2022, DOI 10.1021/acsomega.2c06544](https://doi.org/10.1021/acsomega.2c06544), first-party JATS PMC9773338. The author prose reports two **6-hour** conditions, **1050°C and 1100°C**, each for five different nominal LLZO/Ta/Ga formulas with explicit total ionic conductivities in 10^-4 S/cm: 10 experimental preparation/reference conditions, five nominal formulas and ONE independent author DOI. **Crucially, the authors report EIS at ROOM TEMPERATURE without a measured numeric temperature. This new DOI is therefore NOT eligible for the exact-25°C endpoint benchmark.** These labels are public, now exposed and **not prospective sealed blind**.

### Precommitted admissibility controls

- Exclude *all* 12-hour source rows because the original authors add a mother-powder cover for that procedure, confounding a simple change in time/temperature. Preserve the excluded population (10 conditions), do not silently collapse to training.
- Verify actual publisher JATS DOI/PMCID, original authored numeric prose values and order, first-party room-temperature EIS scope (not exact 25°C) and TOTAL observable context, BOTH units of 10^-4 S/cm in the prose, 6h source treatment and author original conductivity table presence. Original rendered Table 1 S/m versus text S/cm may be inconsistent: **derive exact target values only from the clear author prose** and explicitly record this source limitation, without converting from Table 1.
- Original OBELiX TRAIN fixed 478 entries/449 numeric; connected DOI+formula embargo now includes new source, original publisher TEST 121 never decoded. Learn frozen 0191 temperature/time Ridge(alpha=1) residual correction on 2018 + 2020 original-author conditions only. New 2022 DOI not used to fit or tune. Compare to frozen O_ONLY RF and source-training residual mean.
- Evaluate 10 heldout conductivity predictions and five **within-same-formula** binary 1050/1100 temperature decisions. Report author-out MAE, paired success, abstention, log-conductivity regret, and compare **the trivial always-choose-1100°C rule**. All five observed authors' paired sources favor 1100°C; any model scoring five successes is therefore not proof of better decisions than the heuristic.
- Flag 5/10 candidate conditions at 1050°C as lower than both older training-paper domains (minimum 1100°C). Temperature-range OOD predictions are not automatically deployable.

This remains a one-new-DOI, retrospectively published, non-physically independent evaluation. Physical P0-01/02/03 BLOCKED, O_ONLY router OFF, no science GO.

## Code and execution

Original author intake and frozen heldout evaluator: [0192 science module](../scripts/science/obelix_solo_oxide_new_source_0192.py). Hostile source tests: [0192 adversarial tests](../tests/test_phase3_obelix_solo_oxide_new_source_0192.py). Real-source CPU workflow: [0192 Actions](../.github/workflows/phase3-solo-oxide-new-source-0192.yml).

Next 0193: source-distinct studies that feature differing manufacture-temperature optima; meaningful candidate decision baselines beyond a trivial hotter-rule and out-of-range abstention. If original author source cannot be authenticated, record the failure and leave scientific qualification INCONCLUSIVE.

## Executed original publisher scientific output and admissibility — 2026-10-16

[Actual new-DOI original-source GitHub Actions #38903725237](https://github.com/wt2018mask/Rhombus/actions/runs/38903725237) SUCCESS. Nine source-hostile/regression tests passed. Re-fetched 2022 ACS DOI 10.1021/acsomega.2c06544, PMCID PMC9773338, author JATS SHA256 4bb985cb2ee115598bb2ed57c938b5939eb72aae4b466b9d1730b09526bd5c75; exact artifact 12047114107 ZIP SHA256 73fdedab7551bf0097d2877ffde64834fc161e03b0e7c8adc41e62e81111d24e.

| Comparator on author-reported RT conditions | MAE log10(S/cm) | Correct 1050 vs 1100 choice pairs | Abstentions |
| --- | ---: | ---: | ---: |
| Frozen O_ONLY RF | 0.41275082 | 0/5 | 5 |
| Prior-paper residual mean | 0.39214508 | 0/5 | 5 |
| Source-trained process-temperature/time Ridge | **0.23260347** | **5/5** | 0 |
| Trivial always choose 1100°C | Not a numeric predictor | **5/5** | 0 |

The model's numerical source MAE decreased, but it did NOT outperform the free, trivial always-hotter candidate-choice policy: all five true author pairs favor 1100°C. This is one retrospective, already-exposed public DOI, not independent source replication. Moreover, this author's methods explicitly state EIS **at room temperature**, without an authenticated exact 25°C numerical measurement: **strict exact-25°C admitted sources = 0** for this paper. Do NOT pool or present its scores as validation against the exact 25°C cohort from 0191.

Training-source connected DOI/composition embargo left 238 original O_ONLY usable TRAIN rows from the original 449 numeric; five TRAIN source identity matches and one connected TRAIN group excluded. Original official OBELiX TEST 121 unread. Five 1050°C reference conditions lie below the source-training domain. Ten 12h powder-covered conditions excluded. Source table-unit mismatch is not silently repaired; original paper explicit prose targets are used. P0-01, P0-02, P0-03 remain BLOCKED, O_ONLY production disabled, scientific GO false.

[Versioned numerical evidence](../data/development/phase3_solo_oxide_new_author_0192_evidence_v1.json). Next research should seek exact 25°C author EIS original-source controls with **nonmonotonic** manufacturing winners, and validate candidate-choice improvement beyond the trivial monotonic rule.
