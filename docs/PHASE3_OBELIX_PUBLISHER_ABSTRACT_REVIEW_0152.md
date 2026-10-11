# 0152-B — First-party publication abstract evidence for ten real OBELiX TRAIN CIF candidates

This experiment uses the *actual* 0151 GitHub Actions artifact [#38130478891](https://github.com/wt2018mask/Rhombus/actions/runs/38130478891), whose reproducible aggregated JSON SHA256 is `960cf078fcac71b244a087f0e73d781614aa515d38e6964dcfffcd654f90070a`. This contains **10 distinct exact-Match TRAIN source-CIF rows but only eight DOI papers**; `10.1039/c7ta08581h` and `10.1021/acsami.8b00842` each occur twice. That distinction is scientifically important.

We actually inspected publisher-public article **title and abstract** information for all eight DOI papers on **2026-10-11** using ACS and RSC publisher-indexed pages, preserved minimal DOI-specific finding codes and the precise publisher DOI URLs in `data/development/phase3_original_paper_abstract_review_0152_v1.json`. **We did not inspect inaccessible paywalled full text or supporting documents.** Reading an abstract is NOT authorizing paper-level, specimen-level, phase-specific, structure-specific or numeric measurement-level approval. Some abstracts report whole *composition series* rather than the CIF's precise doping value; their conductivity temperatures/pressure/phase cannot be assigned to the ten individual source records without direct table/supplementary lookup.

## Actual reproducible source join

1. Recheck original pinned `NRC-Mila/OBELiX@4eaac889809dd489e3bae468c45d5c0e02b9147a`. Re-run 0151's original **478 TRAIN** CIF audit with 121 official public TEST reserved-unparsed, verify deterministic 0151 aggregate SHA256 *byte-for-byte* to match the recorded actual Actions artifact.
2. Match **all ten** `0151` queue entries by exact upstream DOI. For each, retain source-row identity, original linked-CIF SHA256 and publisher article's abstract-level experimental context only. Fail closed if any source DOI, row, CIF hash, queue size or upstream original source count changes. Do not download full papers or source-labeled TEST data in CI.
3. Define a controlled set of **publisher-abstract-only risk flags**: variable composition / phase-series ambiguity, occupancies/disorder, known secondary-phase or grain-boundary effects, measurement-method mismatch risk, temperature or pellet processing specificity. These are literature-level scope flags, **not** judgments on the individual CIF as a measured specimen.
4. Publish only aggregate: 10 joined source-CIF rows, 8 distinct reviewed indexed publisher abstract DOIs, duplicate DOI counts, publisher-observed methods, abstract source URLs, per-row paper-review *scope* and unresolved requirements. Ensure the counts for full primary papers actually read, CIF-to-specific-experimental-phase independently confirmed, source-paper table exact conductivity/temperature matched, distinct independent physical specimens, MACE transport evaluated are **all zero**.
5. These eight abstracts are an initial genuine source-literature **triage** rather than the synthetic 'paper review queue generated' checkpoint 0151. Milestone B requires future original full text/SI and row-specific sample-phase-temperature adjudication before any MD transport validation.

## Actual publisher-abstract facts vs unsupported conclusions

- `10.1021/ic400577v`: published neutron diffraction study of LATP Al substitution in a **100–500 K structural analysis**; **not** authorization to assign each CIF a 100–500 K conductivity label.
- `10.1039/c7ta08581h`: RSC abstract describes Li argyrodite Si-for-P substitution monitored by X-ray/neutron diffraction and impedance; no sample-specific value linked to either queue row.
- `10.1021/acsami.8b00842`: ACS abstract reports LAGP Al substitution and diffraction plus impedance, and points to supplementary experimental CIF files. **Two queue rows with the same DOI still need distinct phase/sample mappings.**
- `10.1021/acs.inorgchem.6b02274`: paper abstract explicitly reports secondary LiScO2/LiScP2O7 phases and sample-specific bulk conductivity for **x=0.2 at room temperature**, but **does not establish whether queued CIF `0o6` is x=0.2**; no label is imported from abstract.
- `10.1021/jacs.7b06327`: argyrodite Cl/Br/I fractional halide occupation is an experimental study variable, not a license to fix arbitrary ion site occupancies for a CIF.
- `10.1021/acs.chemmater.8b00266`: LGPS Ge/Sn substitution series; performance changes with composition; no exact row annotation.
- `10.1021/acs.inorgchem.8b02443`: argyrodite S/Se substitution, anion structure changes and conductivity trends; no row-specific activation or measured value.
- `10.1021/jacs.8b10282`: Ge-for-P argyrodite doping with reported **cold-pressed vs sintered conductivity separation**, demonstrating processing dependence; no automatic transfer of those values into record `1m8`.

## Scientific stop lines

**Abstract-reviewed DOI count = 8; full-paper-read count = 0; independently sample/phase/temperature-qualified materials = 0; P0-01/02/03 BLOCKED; SCIENTIFIC_NO_GO.** Direct full source PDF/SI examination and phase-to-CIF matching can follow as 0153-B, bounded by legal publication access and source rights. Do not fabricate missing lab provenance. The agreed A→B→C→D→E evidence-first priorities remain unchanged.
