# 0165-B — can the original LAGP Figure 7 yield auditable quantitative conductivity population statistics?

## What actual primary published data offer

[Weiss et al., ACS Applied Materials & Interfaces 2018, DOI 10.1021/acsami.8b00842](https://doi.org/10.1021/acsami.8b00842) Figure 7 reports room-temperature **bulk σ and total σ** as a function of **nominal** Al/Li composition x, together with activation energies. The Figure 7 caption is explicit: the plotted conductivity and uncertainty are **means and SD from multiple measured samples at identical nominal composition**. The 0164 first-party accepted author PDF pinned SHA `e5fc22ec69db52f403f8776cbcf10e11ed771d6abf69b3c3ac610bb30edfe368` confirms Figure 6 representative *inverse resistance* PDF page 15, Figure 7 marker PDF page 16 and multi-sample mean/standard-deviation caption PDF page 17. The publisher's Rietveld CIFs are structural/phase leads, not confirmed measured pellets.

The original public source includes no certified machine-readable raw **pellet-by-pellet conductivity table** in Rhombus' pinned materials. The plotted Figure 7 coordinates/error bars have not been digitized, the exact replicate **n** for each nominal x is unverified, and specific plotted point-to-OBELiX original source labels `0fh`/`1dm` is unverified. Do **not** infer that the original TRAIN processed-source contrast +0.76937121 log10 S/cm equals Figure 7's total or bulk x0.6/x0.2 group-mean contrast.

## 0165 genuinely executable primary-source numeric readiness experiment

Run exact frozen `NRC-Mila/OBELiX@4eaac889809dd489e3bae468c45d5c0e02b9147a` original TRAIN-exclusive 0163 source path (478 TRAIN CSV decoded, 121 TEST ID prefixes only, 0 TEST formula/DOI/conductivity cells parsed, mixed-file raw TEST bytes passed over). Recheck original pinned publisher eight-CIF archive, accepted author PDF and Rietveld SI. Use bounded `pypdf==5.9.0` on accepted author PDF **pages 15, 16 and 17**, count **image and form XObject resources, explicit image-paint operations, vector drawing paths, graphics colors, text-render operations, and unclassified number-shaped PDF text tokens**, and retain only counts, bounds, page indices and original source SHA. No PDF image, paper text, plot bitmap, raw compound row, TEST values or figure numbers copied to committed data or Actions artifact.

The source PDF and original text types may be **raster graphics, vector strokes or merely axis labels**. The experiment does not silently infer a conductivity curve or data points from typography: 0 *qualified numerical group means/error bars/replicate values* until explicit source calibration independently verifies graph axes (including log10 conductivity), color-to-bulk/total channel, x-value, marker and SD endpoints. If visually digitized, provide repeat extraction uncertainty and cross-validation against original author-provided raw table; if not feasible, seek corresponding-author source data rather than perform arbitrary pixel-based MAE.

Code: [original-source graphics inspection](../scripts/science/obelix_lagp_figure7_numeric_0165.py), [falsification tests](../tests/test_phase3_lagp_figure7_numeric_0165.py), [actual CPU workflow](../.github/workflows/phase3-original-figure7-quantitative-0165.yml). Original first-party source science experiment **SUCCESS** [GitHub Actions #38193859927](https://github.com/wt2018mask/Rhombus/actions/runs/38193859927); final exact PR HEAD general checks separate.

## Exact semantic fail criteria

Uncalibrated axes, optical number tokens, two overlapping color series, number of independent pellets unknown, unverifiable numerical SD, sintering temperature vs actual measured T, and unknown original Rietveld-CIF-to-impedance-sample identity **block** any physically qualified individual experimental truth. Population diagnostic may eventually be scientifically meaningful, but must be distinguished from physical single-structure transport benchmark and cannot close independent-blind P0. Even with perfect graph calibration and invented replica metadata, a population mean is not the measurement of one independently authenticated neutron-refined pellet.

Next **0166-B** depends on actual observed PDF graphic format: if vector data permit rigorously calibrated extraction, run the extraction with independent ambiguity/error checks; if plot only raster with uncertain scaling, seek original author numerical dataset, source plotting script, specimen methods and independent external custodian. Hard science state remains B individual sample 0, A/D source-only, C no finite-temperature physics, P0 0/3 closed, NO-GO.

## Real original first-party source computational result

[Actual original pinned accepted-manuscript and official TRAIN-only source action #38193859927](https://github.com/wt2018mask/Rhombus/actions/runs/38193859927) completed **SUCCESS**. Exact PDF SHA pinned, all page rendering/drawing contents inspected via the original `pypdf` PDF content-stream operator API, 0 numeric point coordinates or copyrighted figure images republished.

| Real original accepted PDF page | Source image XObjects | Vector drawing path operations | Extracted number-like *text* tokens | Scientifically validated σ mean±SD |
| --- | ---: | ---: | ---: | ---: |
| p15 — Figure 6 context | 5 | 0 | 92 | **0** |
| **p16 — Figure 7 title/plot context** | **4** | **0** | **74** | **0** |
| p17 — Figure 7 text/caption | 0 | 0 | 78 | **0** |

Actual p16 graphic operator count **416**, image paint calls **4**, and vector drawing paths **0**: original Figure 7 is on a page with **embedded image objects rather than direct vector drawing curves** in the content stream. Image objects on a page are not necessarily all from Figure 7; do not infer their count equals line/point traces or image-subplots. Axis and ordinary article text produce numerical-looking tokens and must not be interpreted as calibrated conductivity values. Actual p15 operator count 509 and p17 count 348; original page data is present and bounded. **No original Figure 7 physical data point, group SD, replicate n or single-pellet truth was extracted**, so 0 are eligible for an accuracy metric or MD comparison.

**Decision supported by original data:** Source image-aware raster digitization would require identifying which image is Figure 7, its axis pixel bounds, log10 conductivity axis, bulk/total color channel, nominal-x markers, SD bounds, graph-to-table cross-validation and uncertainty due to pixel resolution. Until those independent checks exist, the evidence supports only **group mean±SD semantics**, not any numeric comparison. Prefer first-party author-provided plotted numerical table and individual original specimen data. Source scientific B remains 0; 0166 should attempt calibrated graphics extraction with refusal on ambiguity *or* acquire raw original measurement tables from the authors.
