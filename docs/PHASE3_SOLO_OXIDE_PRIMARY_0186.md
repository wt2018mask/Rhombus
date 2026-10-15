# 0186 — First-party 2025 O_ONLY 25°C TOTAL conductivity with manufacturing-state falsification

Scientific task: improve **measurement comparability** relative to 0185's historically compiled LLZO material rows (no row-specific T or bulk/total). Only O_ONLY is active; S_ONLY and other proxy chemistries are deferred.

[Primary original author 2025 publication — Kang et al. RSC Advances DOI 10.1039/d5ra03917g](https://pmc.ncbi.nlm.nih.gov/articles/PMC12315797/), first-party publisher deposited [PMC JATS](https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12315797/fullTextXML). The original article reports two nominal garnet formulations, **Li6.5La3Zr1.5Ta0.5O12** and **Li6.4Ga0.2La3Zr2O12**, and explicitly describes 25 °C AC impedance with fitted combined bulk+grain pellet resistance and **TOTAL ionic conductivity** (not a bulk-only measurement). From the source's own paragraph: pristine Ta/Ga **2.32×10^-4 / 7.14×10^-4 S/cm**; after contact with lithium-silicon alloy, Ta/Ga **2.86×10^-4 / 3.29×10^-4 S/cm**. The post-contact specimens might have chemically altered surface or phase: *do not promote them to the same unchanged physical phase*.

Actual computer science experiment: freeze 0147 model hyperparameters and 0184 four-model comparison; take original OBELiX 478 TRAIN (449 numeric), *never decode official 121 TEST attributes*. Before training any model, embargo **all connected DOI/raw/reduced-formula TRAIN groups**, including censored bridges, overlapping either O_ONLY nominal formula or original article DOI. Fit pooled RF, specialist O_ONLY RF, specialist Ridge(alpha=10) and O_ONLY TRAIN log-conductivity mean; each composition gets one frozen prediction. Score the **two unmodified specimen** 25°C TOTAL outcomes separately from the **two after-contact** outcomes, all recorded as measurements from **ONE** publicly known paper. Report four-state average, source-group count=1, full failures, model ranking and the exact composition-only irreducible processing-state log10 MAE lower bound. No bootstrap, confidence interval, independent group count >1, prospective blind or specimen authentication claim.

A key falsification: if both treatment states use identical nominal composition-only model input, the model must output the same conductivity, yet original author evidence reports different 25°C TOTAL values; this is a limitation of feature identifiability, not a reason to forge model improvements. Both genuine primary numerics and model metrics are diagnostics only, because the article is public and known, *two chemistries from the same laboratory are insufficient for generalization*, XRD↔EIS same individual pellet is not verified, and the 2025 corpus may overlap the source of other studies.

Only execute the [bounded original JATS reader and real frozen model evaluation](../scripts/science/obelix_solo_oxide_primary_0186.py) with [source falsification tests](../tests/test_phase3_obelix_solo_oxide_primary_0186.py) and [GitHub CPU workflow](../.github/workflows/phase3-solo-oxide-primary-0186.yml). If the live original source differs or cannot be fetched, fail closed without reporting fabricated scores. Original experimental MLIP training-frame provenance remains unverified; physical P0-01/02/03 remain BLOCKED and O_ONLY production router DISABLED.

NEXT 0187: source-qualified independent DOI external O_ONLY 25°C TOTAL measurements on more **independent source groups**, with strict source/time/specimen separation, before any model qualification.

## 0186 ORIGINAL LIVE author JATS and quantitative evaluation — executed

[Real original first-party JATS GitHub Actions #38749223830](https://github.com/wt2018mask/Rhombus/actions/runs/38749223830) **SUCCESS** with **11/11 hostile source tests**. Exact [aggregate source artifact #11980685954](https://github.com/wt2018mask/Rhombus/actions/runs/38749223830/artifacts/11980685954), artifact ZIP SHA256 `50cee29da713c8ec7a3994ea1d60434d433896ce936f5e26869fea3b07640e0e`.

All 449 original eligible OBELiX TRAIN records (307 O_ONLY) remained after embargoing all connected TRAIN source DOI/formula groups; **zero** matched the two primary paper's nominal formulas or DOI in publisher TRAIN. The official 121 TEST were NOT read or scored. Actual author original source confirmed exactly 25°C **TOTAL** conductivity for pristine Ta0.5/Ga0.2 LLZO and post-Li-Si contact conditions. The four-condition composition-only minimum possible log10 MAE from paired target variation is **0.10684509** under unchanged nominal descriptors (not an achievable generalization guarantee).

| Frozen predictor | Pristine two-composition MAE log10(S/cm) | Post-contact two-composition MAE log10(S/cm) |
| --- | ---: | ---: |
| O_ONLY_RF | **0.47304100** | **0.35022887** |
| POOLED_RF | 0.60002847 | 0.47721634 |
| O_ONLY_RIDGE | 0.83117648 | 0.70836435 |
| O_ONLY_TRAIN_MEAN | 1.77548021 | 1.65266807 |

This is only **TWO nominal materials, ONE paper**. The O_ONLY RF has lower MAE on both paired treatment endpoints but cannot provide source-group independence or estimate generalization uncertainty. Post-contact may modify phase/surface chemistry, and observed same-input prediction nonidentifiability cannot be eliminated by simply tuning a composition-only RF. **No strict public independent cohort PASS, physical P0 0/3 BLOCKED, original 121 TEST unread, O_ONLY production router remains OFF.** Next 0187 must recruit more *publicly published* independent DOI/measurement-qualified O_ONLY 25°C TOTAL evidence, no outside human partnership required.
