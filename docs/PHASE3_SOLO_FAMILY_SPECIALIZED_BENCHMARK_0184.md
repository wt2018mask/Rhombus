# 0184 — Original public OBELiX O_ONLY / S_ONLY specialists vs pooled predictor

Rhombus now explicitly explores **narrow, evidence-backed application domains** rather than claiming one global predictor works for every material. User's SOLO operating constraint Issue #349 holds. Earlier 0182 O_ONLY failures were cross-family zero-shot transfer, NOT O_ONLY specialist tests. O_ONLY has 307 numeric TRAIN observations in 64 connected DOI/formula source groups and S_ONLY 117 in 21. Others remain excluded from operational admission, with all counts visible. These families are derived from oxygen/sulfur element PRESENCE, not actual independently identified crystal phases.

## Predeclared design

Actual original source: NRC-Mila OBELiX pinned upstream `4eaac889809dd489e3bae468c45d5c0e02b9147a`; original 478 official TRAIN, 449 uncensored numeric usable, 29 censored not treated as points, 102 connected DOI/formula TRAIN groups, 121 original official TEST **never read or used**. For both chosen source families, five deterministic row-balanced DOI/formula connected-GROUP-heldout folds. Pooled RF excludes the heldout family groups across ALL source TRAIN families; specialist RF and Ridge and family TRAIN mean use only other eligible original source rows of that same family. The same 118 element-fraction descriptors and 50-tree frozen 0147 RF hyperparameters serve pooled and specialist RF. Ridge alpha 10, scaler fit on specialist TRAIN only. Output only aggregate score receipts (no raw source rows/targets).

Each family is independently reported: record MAE, equal-connected-group macro MAE, p90/worst group error, exact 5-fold group/row coverage, 512-draw paired heuristic group bootstrap differences of specialist RF vs pooled RF and family mean. Group bootstrap is **not** IID physically independent experiment uncertainty. Predeclared strict research gate: family RF better than both pooled RF and family TRAIN mean on both row and group macro errors, paired group bootstrap 95% upper bound below 0 for both, and absolute group macro log10 MAE <=1.0. A numerical gain here is a retrospective public source study only: earlier public TRAIN had already been analyzed heavily. **The operational production router remains disabled even if the criterion passes.** Other chemistry source classes explicitly deferred rather than fabricated into a success denominator.

[Executable](../scripts/science/obelix_solo_family_specialists_0184.py), [original CPU workflow](../.github/workflows/phase3-solo-family-specialists-0184.yml), [source anti-leakage tests](../tests/test_phase3_obelix_solo_family_specialists_0184.py). [Real GitHub Actions original-source run #38737725457](https://github.com/wt2018mask/Rhombus/actions/runs/38737725457) SUCCESS (38 source and hostile tests). [Aggregate first-party numerical artifact #11974028748](https://github.com/wt2018mask/Rhombus/actions/runs/38737725457/artifacts/11974028748) ZIP SHA256 `b7a3e2690e1e6b2807c0d9f31fac8c8240783c6545dd120148c56215ad0b2a73`. Actual outcomes include explicit negative results: For genuinely stronger verification, 0185 freezes the chosen model and domain BEFORE retrieving a different chronological/source original PUBLIC dataset's labels. No external lab is a prerequisite. Historical external physical P0-01/02/03 remain BLOCKED, physical science NO-GO.

## ACTUAL numerical family-specialist evaluation (original source)

| Family | Source observations/groups | Model | Row MAE log10(S/cm) | Equal-source-group macro MAE |
| --- | --- | --- | ---: | ---: |
| O_ONLY | 307 / 64 | FAMILY_RF | **1.86224593** | **1.90778897** |
| O_ONLY | 307 / 64 | POOLED_RF | 1.88917663 | 1.93806015 |
| O_ONLY | 307 / 64 | FAMILY_RIDGE | 2.88890100 | 2.69812491 |
| O_ONLY | 307 / 64 | FAMILY_TRAIN_MEAN | 2.03328886 | 2.38751836 |
| S_ONLY | 117 / 21 | FAMILY_RF | **1.61127838** | 2.02533747 |
| S_ONLY | 117 / 21 | POOLED_RF | 1.98310436 | **1.79410968** |
| S_ONLY | 117 / 21 | FAMILY_RIDGE | 2.61131802 | 3.29443087 |
| S_ONLY | 117 / 21 | FAMILY_TRAIN_MEAN | 1.80337200 | 2.65308689 |

Paired source-group bootstrap: O_ONLY specialist−pooled macro difference **−0.03027118**, 512-resample heuristic 95% interval **[−0.18729239,+0.11321639]**, 29 source groups improved and 35 worse. Versus family mean **−0.47972939**, interval **[−0.72196336,−0.25790218]**. S_ONLY specialist−pooled **+0.23122779**, interval **[−0.02354645,+0.45733760]**, 7 source groups improved and 14 worse. Versus family mean **−0.62774941**, interval **[−1.04406924,−0.24100027]**.

These are public connected-source-group heuristic bootstrap intervals, **not** independent physical-pellet confidence intervals. O_ONLY's small paired gain has a CI crossing zero, while S_ONLY row and group metrics disagree strongly. Both have source-group macro MAE above the 1.0 log10 bound. **Neither O_ONLY nor S_ONLY specialist reaches the predeclared strict research-priority flag, and no model is activated for production or claimed to generalize.** Other bins O_AND_S (0), HALIDE_NO_O_S (14), OTHER_NO_O_S_HALIDE (11) remain explicitly deferred. Next 0185 must freeze any chosen domain/model before a new public source/time cohort is examined.
