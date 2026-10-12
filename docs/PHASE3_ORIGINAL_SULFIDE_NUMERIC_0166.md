# 0166-B — actual additional original-paper Li6PS5Br process-condition conductivity table

## Motivation and ORIGINAL measured numbers

Previous 0164/0165 proved one LAGP paper's Figure 7 reports means ± SD from multiple nominally identical pellets, but its actual author's PDF 16th page had 4 image XObjects and 0 vector drawing paths. Without calibrated digitization and exact replicate n, no trustworthy numeric single-pellet truth could be extracted. More repetitions of those page indicators will not improve scientific benchmark coverage.

A **different genuinely OPEN original experimental paper**: [So Yubuchi et al., "Quantitative analysis of crystallinity in an argyrodite sulfide-based solid electrolyte synthesized via solution processing," *RSC Advances* 2019 DOI 10.1039/C9RA00949C](https://doi.org/10.1039/C9RA00949C) deposited in [PMC9064144](https://pmc.ncbi.nlm.nih.gov/articles/PMC9064144/). This is **not** one of the frozen original OBELiX eight DOI review targets and must not be misdescribed as an existing CIF-joined source paper.

Original paper Table 1 reports these actual *publication* cell values:

| Source heat-treatment temperature (°C) — **not measurement T** | 150 | 200 | 300 | 400 | 500 | 550 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Conductivity measured at **25°C** (mS cm−1) | 0.19 | 0.20 | 0.53 | 1.49 | 1.23 | 1.94 |
| Activation energy (kJ mol−1) | 42.3 | 40.3 | 38.3 | 31.2 | 27.7 | 34.9 |

Original table says **720 MPa green compacts**. All six entries represent differing PROCESS CONDITIONS for argyrodite nominal Li6PS5Br (solution synthesis), not six different independent material compositions, prospectively blind samples, or one-to-one neutron diffraction CIFs. Diffraction discussion describes varying crystallinity and other phases including LiBr/Li2S under processing conditions; phase-bound sample identity unresolved. Do not count these as six scientifically admitted independent materials. These are 6 *public process-condition numerical observations* only, with sample-level population/uncertainty unresolved.

## Actual original source experiment

Code [original public archived JATS extractor](../scripts/science/original_sulfide_measurement_table_0166.py) uses only stdlib and an exact PMCID/DOI, primary Europe PMC deposited-JATS endpoint `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9064144/fullTextXML` plus an exact official NIH PMC E-utilities `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=9064144&rettype=xml` fallback. Real source JATS must bind publication DOI/title, unique conductivity+activation table caption, 720MPa preparation, exactly six process columns/condition counts, numeric conductivity unit at **25°C in mS/cm**, activation kJ/mol and expected original six source cell values. The accepted SOURCE archive XML SHA and actual delivered archive URL are recorded. No other domain, arbitrary third-party/unsourced table or "normal" number near a graph can be treated as original experimental truth. For experimental observation cells, convert actual mS/cm to S/cm by dividing by 1000. Freeze original data values to avoid source drift.

Test [adversarial original table typing](../tests/test_phase3_original_sulfide_table_0166.py) rejects wrong DOI, wrong heat-treatment vs measurement-temperature semantics, wrong 720MPa, censored '<', changed numeric labels, absent activation energy and false measurement. [Actual source GitHub Actions workflow](../.github/workflows/phase3-original-sulfide-table-0166.yml) fetches and verifies original archived real XML and writes only the numeric condition-level evidence JSON; **REAL ORIGINAL ARCHIVED JATS SCIENCE SUCCESS:** GitHub Actions [#38198114371](https://github.com/wt2018mask/Rhombus/actions/runs/38198114371) successfully downloaded exact live Europe PMC publisher-deposited original paper XML, publication DOI/title and quantitative table accepted, with first-source archive SHA256 `23622f238820379e615c2732af8c430c458382fcc96e57cd0d10f72f9c9e3338`. Earlier transient 503 and deceptive XML/HTML archive responses were rejected (rather than silently counting them); NIH eFetch is a scientific official archive fallback, not another independent paper. Source-only 6-row actual evidence [artifact #11724840512](https://github.com/wt2018mask/Rhombus/actions/runs/38198114371/artifacts/11724840512), no copyrighted full-paper reproduction.

**Scientific qualification:** This study can deliver 6 OPEN experimental PROCESS records, **0** exact measured **individual physical pellets linked to a CIF**, **0** new truly independent BLIND materials, **0** MLIP finite-T ion-transport runs, P0 0/3 CLOSED, SCIENTIFIC NO-GO. These six are a potential future diagnosis of processing microstructure impact, *not* an E milestone same-budget discovery or A independent validation cohort.

## 0167 strategy

Seek more truly primary public numerical tables and Rietveld sample IDs from several DOI publications in parallel, including candidate paper series already audited in 0152 (Sc NASICON, Ge-for-P argyrodites and RSC Si-doped argyrodites). Require exact pellet preparation, phase/occupancy, measured T and bulk/total classification; keep source-paper and sample hierarchy separate. For actual independent blind prospective experiments, human external custodian still required.

## First ACTUAL independent primary publication quantitative retrieval result

[True original archive API source action #38198114371](https://github.com/wt2018mask/Rhombus/actions/runs/38198114371) **SUCCESS**, actual original source URL `https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9064144/fullTextXML`, source SHA256 `23622f238820379e615c2732af8c430c458382fcc96e57cd0d10f72f9c9e3338`. The paper DOI and title, uniquely matched table caption and source conditions were verified from the **actually downloaded original scientific JATS**. All **six** values in the first paper table reproduced; arbitrary browser previews/figures were not substituted for actual original table cells. Source license permits archival inspection; Rhombus records the six numerical *measurement facts* and source hash rather than redistributing article text or file.

The observed SOURCE data at 25°C are 0.00019, 0.00020, 0.00053, 0.00149, 0.00123, 0.00194 **S/cm** (conversion factor mS/cm × 0.001). Heat treatment at 150, 200, 300, 400, 500 and 550 °C is the **process temperature**, while conductivity measurement is 25°C. All were green compacted at 720 MPa; activation energy values in kJ/mol are paired with same six preparation conditions, not diffusion coefficients.

Scientific accounting: **public numeric experimental condition count +6**, **different primary paper DOI count +1**, **physically independent bulk/total specimen-to-source-CIF admitted count +0**, **blind independent material count +0**, **verified performance lift +0**, **actual MD runs +0**. This is real incremental B source data progress without misleading public literature records into new sampled materials. Continue searching for tables with explicit same-sample CIF/phase and measured impedance conditions as next highest-impact path.
