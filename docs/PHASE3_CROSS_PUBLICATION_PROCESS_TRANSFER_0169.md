# 0169-B — cross-publication process-temperature transfer, actual original papers

## Objective and source identity

**Question:** Under fixed identical nominal Li6PS5Br chemistry, does the one-feature processing-temperature fit on an original source paper better predict measurements from an entirely different paper than its source-trained chemistry-only constant?

- **Source A:** Yubuchi et al. RSC Advances 2019, DOI [10.1039/C9RA00949C](https://doi.org/10.1039/C9RA00949C), 6 original deposited-JATS source heat-treatment conditions (150–550 °C), solution preparation, conductivity measured **25°C**.
- **Source B:** Yu et al. J. Mater. Chem. A 2019 DOI [10.1039/C9TA02126D](https://doi.org/10.1039/C9TA02126D), TU Delft [original 20-page accepted manuscript](https://pure.tudelft.nl/ws/portalfiles/portal/53254729/C9TA02126D.pdf), **physical PDF page 11 / author paper page 9 Figure 4** and immediately below author-written exact numerically listed S/cm measurements for **8 original anneal temperatures** 250–600 °C; solid-state processing with 10 h annealing. University manuscript is not necessarily the edited published version.
- **Important:** Both sources report **Li6PS5Br**, not two independent new material chemistries. The synthesis routes are different. Yu reports *room temperature* but numeric exact measurement T of 25°C across the series is **unverified**. Each prepared sample's pellet/phase/contact identity, per-condition geometry and independently repeated measurement are **not certified**. Figure 4 includes 450°C treatment even though another preparation paragraph omits it; keep this source inconsistency open.

## Model and control

For each direction: fit ONLY the first paper, evaluate ALL observations of the second, then swap papers. No rowwise random split, no target-paper refitting or hyperparameter search, no OBELiX TEST exposure. The two frozen rules are training-paper median of log10 sigma(S/cm) (stoichiometry-only constant) versus 1D OLS with intercept of log10 sigma on the PAPER'S heat-treatment temperature (NOT measured conductivity temperature).

| Whole training paper → complete heldout paper | Source training conditions | Test conditions | Median MAE log10(S/cm) | Process OLS MAE log10(S/cm) |
|---|---:|---:|---:|---:|
| Yubuchi → Yu | 6 | 8 | **0.37480574** | **0.20572061** |
| Yu → Yubuchi | 8 | 6 | **0.37793339** | **0.22463230** |

**Verification status at first draft:** above exploratory numerical calculations are made from real original author-reported numeric series but **[actual original PDF/JATS primary execution SUCCESS](https://github.com/wt2018mask/Rhombus/actions/runs/38570682715) with 16/16 hostile/continuity scientific fixture tests passing**. The public papers and labels were inspected before designing the test, therefore this is NOT preregistered, sealed or prospective blind prediction. Paper-level holdout is better separated than within-paper 0168, but only two preselected studies, shared chemistry and non-identical measured temperature/phase/preparation context. Not proof of generality, causal effect or comparable sample-level transport.

## Implementation, source restrictions and follow-up

[Script](../scripts/science/original_cross_paper_transfer_0169.py) retrieves one exact TU Delft manuscript URL bounded to PDF size, verifies DOI/20 pages/Figure 4 numeric eight pairs and hashes the downloaded original; reuses the 0168 original-authenticated JATS parser. [Falsification tests](../tests/test_phase3_original_cross_paper_transfer_0169.py) enforce original DOI/data identity, fold separation and nonfinite rejection. [Actual GitHub workflow](../.github/workflows/phase3-original-cross-paper-0169.yml) records aggregate-only errors/source digest, not the original copyrighted manuscript or measurement rows. Never claim this represents permission to redistribute the TU Delft manuscript.

Original paper notes impurities at low temperatures and decomposition at 600°C; structure/phase observations do NOT certify physical identity of EIS pellets. **2 public papers / 14 heat conditions / 1 composition / 0 individually attested samples.** Independent external blindness, MACE selected training-frame lineage, material-level validation remain P0 BLOCKED (0/3), no finite-T MD, **SCIENTIFIC NO-GO**. Next **0170-B** should add a third truly separate original tabulated condition series with exact measurement T and ideally per-pellet phase/geometry before any qualified transfer/scientific decision claims.
