# 0166-B — second original paper, actual temperature-dependent Li-argyrodite bulk resistance

**Actual first-party source:** Kraft et al., 2018 JACS paper DOI [10.1021/jacs.8b10282](https://doi.org/10.1021/jacs.8b10282). Original 23-page author Supporting Information is publicly served by [University of Bath](https://purehost.bath.ac.uk/ws/files/187666868/Supporting_Information.pdf). Source numeric Table S17 is PDF page **20** (author print page S19). This is a different scientific paper from the LAGP Figure7 group-mean plot.

## Observed original numbers, first verified real CI

[Original CPU Actions #38197782436](https://github.com/wt2018mask/Rhombus/actions/runs/38197782436) successfully fetched and actually parsed the 23-page author SI: **10 nominal Ge substitutions** x, **10 sample-thickness entries**, **12 temperature rows including two at 298 K**, and **120 experimental fitted bulk resistance entries (Ω)**. Eleven distinct temperature values cover **253–333 K**.

- Median absolute relative difference of the two published 298 K resistance rows across 10 nominal x columns: **3.91568%** (range **1.79104%–9.90664%**). These are two author-published table rows, **not** independently certified different pellets, replicates or an experimental SD.
- Ordinary least-squares fit of log of bulk resistance vs inverse temperature, using the first 11 distinct-temperature rows separately per composition: median *apparent resistance activation energy* **0.226805 eV** (range **0.200880–0.360360 eV**) and median regression R² **0.999490**. It is NOT a direct diffusion coefficient, tracer jump rate or experimental ionic conductivity.
- The SI cautions that bulk processes become difficult or impossible to separately fit at **higher nominal Ge x**, so high regression linearity DOES NOT rescue uncertain measurement component assignment.
- Original Table S17 gives thickness by composition; the original source does not yet prove the exact electrode area, measured pellet/geometry, individual temperature trace identity, sample-to-neutron-CIF identity or independence of two 298 K entries. Thus there is **no independently qualified physical pellet truth in S/cm**. Conversion would require σ = d/(R_bulk×A) with authenticated cell geometry and reliable bulk arc.

**Primary source byte-science integrity:** the Bath institutional PDF front page includes downloaded-on metadata/cover that may change, so the first real download SHA256 **419b5680ab9c01703a5b34bab9f7a78fe216f22971af4225a8cc38eff9e03b45** is a run receipt, NOT a promised universally stable full-file fingerprint. We separately normalize exact 10 x, 10 thicknesses and 12×(T+10 R) source table numeric cells, then enforce reproducible scientific-content hash **1eb7ad5527b18040239b341ba6171aad3453113c700c2edf4ca271a1eba84d7d** in code and GitHub Actions. A changed input numerical cell must trigger rejection. This source is restricted to institutional HTTPS, 23 pages, byte and text bounds, and Table S17 exact sections/column counts.

**Copyright/data hygiene:** PDF and raw table numbers are transient inputs only, NEVER committed/copied to public Artifacts; Actions report source digest, aggregate statistics and sample qualification blockers only. Earlier OBELiX original public TEST source fields are neither parsed nor trained on in this experiment.

**Scientific gates:** 120 original numeric values ≠ 120 new materials, two rows at one T ≠ independent experimental replicates; experimental measurement origin and bulk Ω ≠ σ S/cm. New physically attested independent samples **0**, MACE exact chosen training-frame lineage unavailable, new sealed blind cohort unavailable, **RT-P0-01/02/03 BLOCKED**, C finite-temperature ion transport not executed; SCIENTIFIC NO-GO. No claim of model accuracy lift.

## Reproduction and follow-through

Executable: scripts/science/obelix_kraft_original_tabular_impedance_0166.py.
Negative tests: tests/test_phase3_kraft_original_table_s17_0166.py.
Original-source workflow: .github/workflows/phase3-real-kraft-original-table-0166.yml.

**0167-B priority:** first read original author main-text/sample setup methods and identify per-composition electrode area and the experimental meaning of two 298 K rows; attempt same measured pellet to actual refined diffraction structure binding. If no primary data for that mapping exists, keep Table S17 as a genuine temperature-resistance reference diagnostic and broaden other SI tabulated actual-source papers in parallel. Never keep inflating GitHub evidence counts instead of physical measured truth.
