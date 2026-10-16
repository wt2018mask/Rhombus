# 0191 — Actual process-aware original-paper-out experiment

Rhombus's goal is **scientifically defensible candidate choice at equal free compute**, not just smaller published MAE. Checkpoint 0190 documented that composition-only models cannot choose between manufacturing routes of an identical nominal composition. This step fits a first, deliberately simple process-aware residual predictor to REAL author sintering-temperature and hold-time inputs.

## Frozen protocol

- Two distinct public original-author studies: [2018 RSC Xue et al.](https://doi.org/10.1039/c8ra01329b), original JATS PMC9079727 Table 1 process + Table 3 total conductivity; [2020 Materials Nb-LLZO](https://doi.org/10.3390/ma13030560), original JATS PMC7040616 Table 2 process plus 25°C total conductivity. Five manufacturing conditions per paper and one nominal formula per paper: **10 conditions, only 2 DOI groups and 2 nominal chemistries**.
- Before seeing 0191 numeric results, freeze two process-only inputs: (temperature °C −1150)/100 and log10(hold time minutes/60), and Ridge(alpha=1). No exploratory hyperparameter tuning on source heldout truths.
- The frozen OBELiX composition-only O_ONLY RF trains only on publisher TRAIN (478 entries, 449 numeric before connected DOI/reduced-formula embargo), official publisher TEST 121 **untouched**.
- In each of two folds, train a linear residual correction on **one source DOI's five observed numeric conditions only**; assess on all five measurements of the other DOI. Compare composition RF, constant train-source residual correction, and temperature/time Ridge correction. Report both per-DOI MAE and each-paper top-1 correct choice or abstention.
- Features allowed at candidate choice time: declared sintering temperature and duration. Explicitly forbid post-measurement EIS, XRD, density, activation energy, measured final pellet composition, and outcome-target proxy features.
- A separate original 2025 Sn-garnet paper introduces different categorical DUAL_STEP and MONO_STEP manufacturing routes; these are **not compatible numeric** temperature/duration differences. Explicitly abstain on its four route pairs, never impute.
- All three source studies are already publicly visible. No newly sealed blind, no independent pellet-phase/EIS identity, no material-discovery GO, and all P0-01/02/03 remain BLOCKED. With 2 papers, any apparent top-1 win is unstable and only diagnostic.

[Executable source/predictor](../scripts/science/obelix_solo_oxide_process_transfer_0191.py), [hostile scientific tests](../tests/test_phase3_obelix_solo_oxide_process_transfer_0191.py), [real GitHub Actions](../.github/workflows/phase3-solo-oxide-process-transfer-0191.yml).

Next 0192: new **compatible** process source DOIs, data eligibility and reported uncertainty; if evidence is too sparse, record INCONCLUSIVE rather than claim a transferable manufacturing-selection policy.

## 0191 actual original source experiment — 2026-10-16

[0191 GitHub real source run #38899828332](https://github.com/wt2018mask/Rhombus/actions/runs/38899828332) **SUCCESS**. Original author JATS from 2018 and 2020 validated (temperature/holding time values linked to original 25 °C TOTAL EIS conductivity). Direct adverse process tests plus inherited 0190 tests: **12 passed**. GitHub original output artifact ID `12045328896`, archive ZIP SHA256 `1a8f39fbfc82a07baa84b628546c4e76e6d7b12f44ba38de3e3aed368f26172f`.

| 2 original DOI out-of-paper folds | Frozen composition O_ONLY RF MAE | Train-paper mean residual MAE | Train-paper temperature/time Ridge MAE | True best | Process-selected |
| --- | ---: | ---: | ---: | --- | --- |
| Train 2018 RSC → TEST 2020 Materials | 0.43361004 | 0.49570929 | **0.39158546** | SL2 | SL2 (correct) |
| Train 2020 Materials → TEST 2018 RSC | 0.39586190 | 0.46038163 | **0.36579967** | LLZALO-4 | LLZALO-5 (wrong) |
| Equal-paper macro | **0.41473597** | 0.47804546 | **0.37869257** | | |

**Interpretation:** The fixed process-residual Ridge lowered mean log10(S/cm) error by approximately 8.69% relative to the composition RF across these two already-public papers, but selected the best five-condition manufacturing option in only **1 of 2** heldout DOI studies. It incorrectly recommended LLZALO-5 instead of source-reported LLZALO-4 in the RSC paper. The composition-only RF abstained on both top-one preparation choices (all five within each source share nominal composition). The 2025 Sn-garnet categorical DUAL_STEP versus MONO_STEP 4 process pairs also **abstained**, because this model only describes varying numeric peak sintering temperature and hold time. No manufacturing-selection utility advantage is established; paper N=2, author measurements publicly known, within-paper conditions not independent pellets. Original OBELiX TEST 121 unread, P0 0/3 BLOCKED, production OFF, scientific NO-GO.

[Aggregate executed evidence](../data/development/phase3_solo_oxide_process_transfer_0191_evidence_v1.json).
