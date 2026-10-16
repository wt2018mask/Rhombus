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
