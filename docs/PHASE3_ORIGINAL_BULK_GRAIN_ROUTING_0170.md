# 0170-B — original Li6PS5Br 2017 BULK vs grain transport scope

## Genuine original third paper and experimental design

[Yu et al., Journal of Materials Chemistry A, 2017 DOI 10.1039/C7TA05031C](https://doi.org/10.1039/C7TA05031C); [TU Delft original open publisher publication PDF, 12 pages](https://repository.tudelft.nl/file/File_9dd14ba3-3c77-4f77-8383-0918de3062a6). Study includes X-ray/neutron diffraction and impedance for three preparation pathways of same nominal Li6PS5Br: ball-milled only (8 h 500 rpm), ball-milled then 300°C 5h annealed (AN), AN then 450 rpm 4h re-milled (AN-BM). Electrochemical tests used stainless steel contacts on 10mm diameter pellets (paper page 2). Original PDF physical page 5, journal page 4 (zero-index page 4), scientific paragraph by Figure 1c explicitly contains **three fitted R_bulk, three fitted R_grain-boundary including error parentheses and three ROOM-TEMPERATURE BULK ionic conductivities**. These are not three temperatures and not author-tabulated total conductivity.

## Fixed quantitative science and falsifiable outcome

Check full original PDF source identity + original author quantities (read manuscript live), then compute independent *point estimate* Rgb/Rbulk per named route, and σbulk·Rbulk/(Rbulk+Rgb) as a constrained **series-equivalent-circuit proxy only**. This assumes the fitted Rbulk and Rgb represent resistive paths in series and share a geometrical factor within a single sample, and assumes sigma_bulk itself is comparable. The paper explicitly cautions that fitted bulk vs grain resistance separation is difficult; do not treat series-derived values as physically measured total conductivity.

| Author processing route | Reported fitted Rbulk Ω | Author-fitted Rgb Ω | Reported bulk sigma S/cm | Derived nominal series proxy S/cm |
|---|---:|---:|---:|---:|
| Ball-milled only | 924.8 | 3.02×10^6 | 6.20×10^-4 | 1.89801×10^-7 |
| Annealed at 300 °C (5h) | 516.8 | 619.9 | 1.11×10^-3 | 5.04661×10^-4 |
| Annealed then re-milled | 381.7 | 686.8 | 1.38×10^-3 | 4.92977×10^-4 |

Quoted table is a narrow research audit, not an experimental training dataset to be copied to public benchmark outputs. **New computed physical fact:** author-reported bulk σ point estimates would rank re-milled above annealed (ratio 1.243×). Series-path proxy estimates rank annealed above re-milled (ratio ≈1.0237×), BUT uncertainty ranges from reported resistance fit bounds **overlap**; sigma_bulk uncertainty and inter-run correlations unknown; numerical rank reversal is **NOT statistically demonstrated**. No numeric author-measured sigma_total is authenticated.

## Scientific scope gate / applicability

This source is the THIRD genuine original paper, but Yu is also on 2019 Yu original paper. It cannot be considered a third independent research *group*, blinded prospective source, material chemistry family, physically independent specimen cohort, or heldout annealing-temperature regression series. There is just one annealing temperature in this preparation pathway set; a second milling process is not a second anneal temperature. Exact numeric room measurement temperature, individual pellet thickness, matching diffraction-vs-impedance specimen, replicate count and statistical power are unverified.

The outcome directly stresses the core *transport quantity* and potentially reverses low-cost material selection decisions depending on whether we rank BULK only or fit-proxy TOTAL. The source of the discrepancy is the huge grain boundary resistance in the as-milled state and contrasting resistance between annealed and remilled states. These are in-paper diagnostics, not MLIP improvements or independently validated novel material decisions.

## Code and provenance

Executable [strict original-source PDF reader + bounded numeric diagnostic](../scripts/science/original_bulk_grain_routes_0170.py), [scientific false-promotion tests](../tests/test_phase3_original_bulk_grain_routes_0170.py), [original live CPU workflow](../.github/workflows/phase3-original-bulk-grain-routes-0170.yml). The workflow must download the exact RSC PDF hosted by TU Delft and verify source DOI, physical pages, original fitted resistance quantities and BULK σ, then recompute derived aggregate. Original PDF and source numeric table never uploaded, only aggregate results and SHA. Keep historic 0169 errors frozen.

**[Live original PDF Actions #38574606008](https://github.com/wt2018mask/Rhombus/actions/runs/38574606008): SUCCESS.** Real archived TU Delft 12-page PDF was fetched and parsed, the journal DOI and original resistances/bulk conductivity passed source-value tests; the actual derived diagnostic was reproduced and passed an explicit NO-GO unit audit. Primary original aggregate-only [artifact #11900175223](https://github.com/wt2018mask/Rhombus/actions/runs/38574606008/artifacts/11900175223), SHA256 of archive `614d9dd18093790d7936680384219cd94c1e539cca488e45732e64a1a62f8cfb`. Actual source test suite: 16/16 pass. This is computational and journal source verification; the physical pellet's exact measured identity remains unverified. **Qualified physical specimen 0**, independent blind 0, finite-T MLIP conductivity 0, P0 0/3 BLOCKED, SCIENTIFIC **NO-GO**. Next 0171-B: physically traceable exact sample measurement / adequate independent specimens with model-choice and observable bulk/total predeclared before scoring; choose a **new research group** for external replication rather than treating Yu 2017 as group independent of Yu 2019.
