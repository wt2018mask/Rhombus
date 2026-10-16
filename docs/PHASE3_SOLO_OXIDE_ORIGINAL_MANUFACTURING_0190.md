# 0190 — O_ONLY original Sn-garnet synthesis-choice diagnostic

## Why this advances Rhombus's long-term objective

The end goal is superior evidence-bound **candidate selection and rejection** at equal compute budget, not only lower paper-row conductivity MAE. Checkpoint 0189 demonstrated that composition-only prediction cannot distinguish multiple manufacturing states. This checkpoint creates a NEW source-bound diagnosis of the same failure in a distinct chemical class and quantifies the resulting candidate-choice ambiguity before any process-aware model is trained.

Original article: Zimmermann et al., *ACS Organic & Inorganic Au* (2025), DOI [10.1021/acsorginorgau.5c00021](https://doi.org/10.1021/acsorginorgau.5c00021), original deposited PMC12142435 author JATS Table 2. It reports eight **25°C TOTAL** lithium-ion-conductivity values from four nominal Sn-containing high-entropy garnet formulations with TWO manufacturing paths each: dual-step DS1–DS4 and mono-step MS1–MS4.

- Predeclared external author DOI: 10.1021/acsorginorgau.5c00021, not any of the five 0188 DOI papers.
- Target: **25°C TOTAL ionic conductivity S/cm**, not bulk-only, activation energy, density, or extrapolated transport.
- Eight reference conditions, **four distinct nominal formulas, one paper**, not eight independent novel compositions, laboratory sources, authenticated physical pellets or an independently blinded challenge.
- Manufacturing descriptor: categorical **DUAL_STEP versus MONO_STEP** only. Do not quietly impute sintering temperature/time or measured final stoichiometry from nominal batch preparation; observed XRD/EDS are not certified as the identical EIS physical pellet.
- All author labels are already public, and the new source has been manually seen while identifying candidates. This is retrospective, **not a pristine prospective blind**.
- Keep model configuration immutable (RF_PARAMS, RIDGE_ALPHA), train only from original publisher OBELiX 478 TRAIN / 449 numeric labels after transitive DOI/raw/reduced-composition group embargo including censored entries; do not parse official TEST 121 attributes.
- Compare pooled RF, O_ONLY RF, O_ONLY Ridge, and O_ONLY TRAIN mean on the same eight values; record all losses and sample pairs. Models are refit after the new source embargo but configurations are unchanged.
- Scientific candidate-selection falsification: each fixed formula has two processing options. All four composition-only models are mathematically tied within each pair; they cannot rank the two options. The author-revealed route winner is an oracle *diagnostic only*, never a trained processing decision model or evidence of discovery utility.

The deliberate 0190 gate is to add executable original-source/model evidence, not claim an invented external generalization gain. One DOI cannot supply an independent-paper confidence interval, even if an observed MAE looks smaller. No new functional manufacturing-aware predictor is supplied or approved. The official original publisher TEST 121 is still reserved unread. External physical P0-01/02/03 are BLOCKED and production router remains OFF.

Implementation: [0190 source + real-model experiment](../scripts/science/obelix_solo_oxide_original_manufacturing_0190.py), [negative and tamper tests](../tests/test_phase3_obelix_solo_oxide_original_manufacturing_0190.py), [original CPU workflow](../.github/workflows/phase3-solo-oxide-original-manufacturing-0190.yml).

Next 0191: collect training-eligible **process descriptors** using published TRAIN-only source groups, define missingness and allowed feature timing (never use post-EIS answer or author inferred target as input), fit a process-aware baseline using grouped cross-validation, then test it once on source-separated data; compare **same-budget choice utility** with random and composition-only tie choice. If required source feature coverage is insufficient, record INCONCLUSIVE rather than inventing processing features.
