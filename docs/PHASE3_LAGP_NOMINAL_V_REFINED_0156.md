# 0156-B original publisher LAGP CIF nominal versus refined x and paper context

**Scientific goal (Milestone B):** For the **two** 0155 original source-verified OBELiX TRAIN crystals whose geometry fits an actual publication Rietveld crystal, determine which actual publisher-distributed original CIF file each match corresponds to and compare the publisher **nominal series x** from that file name with independent crystal **refined-site composition x**. Avoid the frequent invalid inference that geometric fitting alone certifies an experimental specimen's measured conductivity.

## Previous frozen scientific sources

- [Original real 0155 crystal experiment](https://github.com/wt2018mask/Rhombus/actions/runs/38137695018): eight original publisher LAGP neutron-refined CIF, two DOI-linked original OBELiX TRAIN CIF, 16 attempted geometry comparisons, 15 broad composition-compatible and 2 permissive crystallographic fits.
- Actual accepted public author manuscript `https://www.osti.gov/servlets/purl/1434719`, SHA256 `e5fc22ec69db52f403f8776cbcf10e11ed771d6abf69b3c3ac610bb30edfe368`.
- Actual first-party publisher original Rietveld PDF SHA256 `db747a82235860cdcd21a798ad51d2fd0d22b906d3a213cd31e9ea9af72d94d3`; actual publisher CIF ZIP SHA256 `dc88a0a83857b172ebe7a8194eb1b50148f117d6cddb39f1adbb628ac7d1c382`.
- Original `NRC-Mila/OBELiX@4eaac889809dd489e3bae468c45d5c0e02b9147a`; reserve public TEST 121 entirely.

## New real source computation

[CPU experiment](../.github/workflows/phase3-original-lagp-nominal-0156.yml) downloads exact source bytes and redoes 0155 source authenticity, then reads original **ZIP member filenames** and their hashes. For each 0155 geometry match, record the actual filename nominal stoichiometric series, and calculate refined x three ways, from Al occupancy, Li occupancy and Ge occupancy by normalizing P=3. These values must not be silently equated with nominal x: solubility limit, partial occupancy and synthesis can generate differences. Extract page numbers containing transport/measurement terminology from the actual full accepted paper and Rietveld supporting PDF. Numeric string/page co-occurrences are **not sufficient specimen evidence** and are not interpreted as verified individual measured temperature, phase or bulk/total conductivity.

**Admission stop line:** no source specimen-level conductivity match, no independent qualified material, no zero-cost external blind, no ordered MACE geometry from disordered CIF, no transport-MD and all P0 3 BLOCKED. A/other milestone status remains as in [the approved scorecard](SCIENTIFIC_MILESTONE_SCOREBOARD_0155.md). Next 0157-B should directly adjudicate actual per-sample paper/SI text/table/figure source with exact sample/process/phase/measurement type and source-row identity, or report excluded/unverified.

**At commit time:** actual 0156 source calculations still PENDING task-specific GitHub Actions; do not state nominal links as executed until exact-head source test successfully runs.

## Actual first real manuscript/SI result

[Initial real GitHub scientific execution #38143192408](https://github.com/wt2018mask/Rhombus/actions/runs/38143192408) fetched the original 8-member publisher CIF ZIP, recomputed original 0155 pinned TRAIN source geometry, downloaded both independently SHA-pinned primary PDFs, and completed its **scientific negative-claim assertion**. The first workflow failed only during the final upload step because a copied 0155 artifact path was stale; the path has been corrected on PR #324 and a new exact-head full CI must pass.

Actual two source crystal↔published CIF filename/nominal label correspondences from original file members:

| Original OBELiX TRAIN record | Original publisher neutron CIF member | Publisher nominal Al series x | Crystal refined Al x | Refined minus nominal x |
| --- | --- | ---: | ---: | ---: |
| `0fh` | `lagp-1.2.cif` | 0.2 | 0.242 | +0.042 |
| `1dm` | `lagp-1.6.cif` | 0.6 | 0.480 | −0.120 |

Both are **file-level crystal identity candidates** with exact first-party publisher CIF SHA and previously verified geometry fit. The original experimental material might contain secondary phases, a processing-dependent phase distribution, and separate bulk/grain-boundary/total conductivity measurements: nominal filename x and Rietveld refined x are **not interchangeable**, and no per-specimen measured values have been attributed. Actual accepted author full manuscript **26 pages** and original publisher Rietveld SI **15 pages** were parsed, but numeric token page co-occurrence is **not** physical sample identity. No original public TEST data was consulted; scientifically qualified experimental independent samples remain **0**.

The public paper [publisher abstract](https://pubs.acs.org/doi/10.1021/acsami.8b00842) states that a solubility limit was observed at higher aluminum substitution. This paper-level observation is consistent with a possible nominal/refined composition difference, but does not by itself prove the causal mechanism for the two specific CIFs; that needs direct diffraction refinement and synthesis/measurement table adjudication.

**Milestone B status:** source crystal to original nominal CIF label linkage improves, but independent specimen↔phase↔temperature↔bulk/total conductivity is not closed, and P0 science remains NO-GO.
