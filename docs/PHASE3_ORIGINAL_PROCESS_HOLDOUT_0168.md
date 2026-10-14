# 0168-A — genuine original-publisher same-chemistry manufacturing-conditioned conductivity prediction

## Falsifiable question

Does knowing **preparation heat-treatment temperature** improve conditional prediction of source **25°C ionic conductivity** over a model restricted to stoichiometry, given exactly the same nominal Li6PS5Br across six records? It is physically incorrect to use heat-treatment T as the conductivity measurement T or call six process conditions six independent new materials.

**Real primary source:** Yubuchi et al., 2019 RSC Advances DOI [10.1039/C9RA00949C](https://doi.org/10.1039/c9ra00949c), deposited XML via original PMC/Europe PMC mirror PMC9064144. Existing SHA/authenticated original JATS table parser `scripts/science/original_sulfide_measurement_table_0166.py` validates DOI, original six heat treatments, 720 MPa compaction, 25°C conductivity values and units. [Initial 0168 original primary source GitHub Actions #38565237436](https://github.com/wt2018mask/Rhombus/actions/runs/38565237436) **SUCCESS**. No source XML/label rows uploaded in this PR; aggregate errors and source fingerprints only.

## Fixed algorithms, exact evaluation policy

Before each of six **leave-one-processing-condition-out** runs, fit **only five other processing conditions**. The **stoichiometry-only** baseline is the median of five log10 σ(S/cm) source labels: as all nominal chemical formulas are identical, it cannot distinguish the six conditions. The process-aware candidate is **one-variable OLS** with intercept on training (heat-treatment temperature °C, log10 σ(S/cm)), using each heldout condition's preparation temperature to predict conductivity. Both rules fixed, no random seed, no search/tuning of hyperparameters, no heldout label in its own fold fit. The two extreme heldouts necessarily use **linear extrapolation**, and this is not verified outside the observed process-temperature range. One paper, one nominal material, 6 correlated process settings, not independent material cross-validation. Critical: the same paper/labels were already inspected in 0166/0167, hence model selection/design is **retrospective exploratory**, not prospective preregistered validation.

| Fixed rule on original 6 source conditions | LOO log10(S/cm) MAE |
| --- | ---: |
| Five-training-label median (stoichiometry-only) | **0.55728689** |
| Five-training-label OLS on preparation temperature | **0.13095762** |
| Observed conditional MAE reduction | **76.50%** |

This **0.5573** is a heldout-by-condition six-fold diagnostic. It must never be silently confused with 0167's **0.37447227** source-retrospective *all-six-label* optimal constant, which uses heldout labels to choose one number. Original crystal fraction, defects, grain morphology and electrode preparation likely covary with heat treatment; it is therefore **not a causal effect of T**, not verified knowledge of independent pellets and not evidence of neural MLIP transport improvement.

## Controls and reproducibility

- Source numerical table and measured T vs preparation T are verified on live publisher-deposited JATS original; refuse changed DOI, compaction, physical pellet admission, measured 25°C identity, source values or number/order of records.
- Reject nonfinite conductivity, duplicated experimental processing conditions, invented independently attested specimens or official P0 success.
- Scientific experiment: [0168 original source LOO script](../scripts/science/original_process_holdout_0168.py); [negative tests](../tests/test_phase3_original_process_holdout_0168.py); [original source GitHub CPU workflow](../.github/workflows/phase3-original-process-condition-0168.yml).
- Only aggregate log-MAE, source SHA and gates retained; public original measurements never become official OBELiX TEST answers, independent material labels or new sealed blinding.

**Milestones:** A within-source manufacturing/process information **diagnostic** meaningful but no generalization certified; B same-pellet phase/geometry and original specimen sample numbers **0**; C real converged finite-T transport **not run here**; D no source-independent UQ claim; E no same-budget discovery benefit proven. P0-01/02/03 **BLOCKED**, SCIENTIFIC **NO-GO**.

**Next 0169-B:** Seek at least two independent experimentally traceable material/sample papers with reported process/phase and genuine individual specimen σ to evaluate transfer across **papers**, not random conditions within a known paper. Independent blind sample steward and selected MACE training-frame provenance remain parallel gates.
