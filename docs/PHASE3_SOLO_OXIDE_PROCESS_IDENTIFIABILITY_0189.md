# 0189 — O_ONLY manufacturing-state identifiability falsification

Scope: **No new author source is admitted in this checkpoint.** This is an intentional scientific diagnostic on the already verified 0188 five-DOI / 22-reference-condition 25°C **TOTAL** log10(S/cm) cohort. 0188's actual numeric experiment and 52/52 CI succeeded before canonical merge. New unexamined author DOI groups remain the next acquisition target (0190). This avoids inventing unverified original pellets or treating source-pooled rows as independently measured chemistry.

Key scientific issue: one nominal formula often has **multiple real author conductivity outcomes** across different sintering temperatures, schedules, Li precursor excess or synthetic routes. Any composition-only model (POOLED_RF, O_ONLY_RF, Ridge, or mean) must output an identical value for an identical reduced formula, so the model cannot in principle fit all processing states simultaneously.

Use only original first-party author JATS sources from the frozen 0188 five DOI study:
- 2025 RSC Ta/Ga pristine 2 states: 10.1039/d5ra03917g
- 2022 Nanomaterials Li-precursor Al vs Al/Ga/Ta x states: 10.3390/nano12172946
- 2020 Materials Li6.6La3Zr1.6Nb0.4O12 five sintering states: 10.3390/ma13030560
- 2018 RSC Li6.4Al0.2La3Zr2O12 five sintering states: 10.1039/c8ra01329b
- 2021 Materials same nominal Li6.4Al0.2La3Zr2O12 four synthesis routes: 10.3390/ma14226809

Re-fetch original JATS and verify each source table and numeric endpoint, fit only original publisher OBELiX TRAIN 478 (449 usable) with 121 official TEST unread, preserve connected DOI/raw/reduced-composition overlap embargo and the same frozen 0188 four model predictions. Then independently derive the optimal possible **constant prediction per reduced nominal formula** for the 22 already visible public measurements.

Mathematical negative control: for each repeated nominal formula, compute the sample-median minimizer of sum of absolute log10-conductivity deviations. This yields the **smallest attainable in-sample row-weighted MAE for any composition-only constant model**. A second floor uses the DOI-balanced objective (each of the five papers gets equal weight); use weighted medians, weights 1/n_DOI per observation, and divide final loss by five. Check both are below actual 0188 MAEs, and report count of repeated nominal groups, observations in variable nominal groups, cross-paper repeated formulas, and maximum within-formula log-conductivity range.

Important: **the medians are fit using the evaluation answers. They are a mathematical retrospective oracle, NOT an executable predictor or a valid claim that supplying manufacturing variables will attain those errors.** A gap between an RF and the oracle is not proven to be due solely to missing manufacturing data; model generalization and nominal-vs-final pellet identity also matter. Numeric source rows are *22 reference conditions, not 22 independent pellets*. Six 2022 formulas derive from nominal theoretical Li precursor and are NOT measured final Li chemistry. EIS↔XRD physical same-pellet linkage remains unauthenticated. No model or hyperparameter can be selected using this already exposed cohort and then called independently validated.

Source module: [0189 real source and exact mathematical bound](../scripts/science/obelix_solo_oxide_process_identifiability_0189.py), [negative tests](../tests/test_phase3_obelix_solo_oxide_process_identifiability_0189.py), [actual original GitHub workflow](../.github/workflows/phase3-solo-oxide-process-identifiability-0189.yml). Results pending real original execution. Physical scientific P0-01,02,03 remain BLOCKED, source group N=5 underpowered, O_ONLY production model OFF.

After 0189: seek new primary DOI 25°C TOTAL sources, freeze specimen/process descriptors based on **TRAIN-only** evidence, assess future cohorts without adjusting to these 22 observed outcomes. 0190 is the prospective source-qualification and process-input protocol milestone, not a newly certified solver.

## 0189 ACTUAL original-author five-DOI evaluation (source test PASS, not production model)

[GitHub Actions #38875869876](https://github.com/wt2018mask/Rhombus/actions/runs/38875869876) SUCCESS, 11 source/math regression tests PASS. [Aggregate-only original evidence artifact #12035785738](https://github.com/wt2018mask/Rhombus/actions/runs/38875869876/artifacts/12035785738), ZIP SHA256 \`4ad47e0b46e94aae94872f25a574c4e4163645938756ec88e5a447794e1a996d\`.

The re-fetched five original public author JATS papers and original OBELiX publisher TRAIN confirm 22 measured 25°C TOTAL conditions, **10 distinct reduced nominal formulas**. Exactly **two nominal-formula groups have different 25°C total conductivity outcomes**; they account for **14/22 published processing/reference observations**. One repeated nominal formula spans two independently published DOI papers. Largest same-formula log10 outcome span = **1.32835312** (factor about 21.3). This is not 14 authenticated distinct physical pellets.

| Mathematical diagnostic (log10 S/cm) | Frozen O_ONLY RF MAE | Optimal truth-selected formula-constant in-sample lower bound | Gap to in-sample oracle |
| --- | ---: | ---: | ---: |
| All 22 rows equal | 0.41167292 | 0.22980839 | 0.18186453 |
| Five author DOI groups equal | 0.41396469 | 0.20741491 | 0.20654978 |

**Scientific interpretation:** Composition alone cannot match all distinct manufacturing-state outputs for the same nominal formula. However these oracle values are computed *after observing all the answers*. They are not reproducible predictive validation performance, a learned processing-aware ML model, or evidence that all gap-to-oracle error is attributable to missing process features. Real final pellet composition can differ from nominal labels. New DOI count **zero** this checkpoint. P0-01/02/03 all BLOCKED; production O_ONLY model OFF; original publisher official TEST 121 unopened. Next 0190: independent source acquisition and source-truth-separated process-feature evaluation.
