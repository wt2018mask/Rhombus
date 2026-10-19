# 0194 — Actual new original 2023 Te-garnet source: 25 C TOTAL and nonmonotonic hot pressing

2023 first-party primary publisher source: D. Campanella et al., ChemSusChem 16 e202300399, DOI [10.1002/cssc.202300399](https://doi.org/10.1002/cssc.202300399); [original published HTML](https://chemistry-europe.onlinelibrary.wiley.com/doi/10.1002/cssc.202300399). The original Table 2 reports 25 C total ionic conductivity in S/cm of six series at 600/650/700 C, hot pressed at 56 MPa: four Te-substituted nominal LLZO series (Te0.1, 0.25, 0.375, 0.5), Al-LLZO and Ta-LLZO commercial references.

| Author hot press C | Te0.1 | Te0.25 | Te0.375 | Te0.5 | Al-LLZO | Ta-LLZO |
|---|---:|---:|---:|---:|---:|---:|
| 600 | 1.21e-5 | 2.95e-5 | 1.61e-5 | 2.33e-5 | 3.88e-8 | 2.64e-7 |
| 650 | 1.76e-5 | 4.64e-5 | 3.27e-5 | 4.24e-5 | 1.04e-7 | 2.29e-6 |
| 700 | 1.45e-5 | 5.15e-5 | 4.66e-5 | 4.83e-5 | 3.05e-7 | 6.70e-6 |

All values are total S/cm at **author-reported 25 C**, not bulk-only or mS/cm. EIS testing was from 20 to 80 C; this paper's specific 25 C tabulated target is not proof each number was separately directly sampled at exactly 25 C (rather than derived via fitting). The 18 values are **18 measured/reference conditions but ONE independent paper**; source labels already visible in original, not a fresh prospective blind test.

**Concrete nonmonotonic target:** Te0.1 at 650 C is 1.76e-5, above 700 C at 1.45e-5. Always pick hottest 700 C succeeds for 5 of 6 series; loses Te0.1. Without replicated measurements and measurement uncertainty, the ~21 percent gain of the intermediate temperature is not statistically certified.

**Physically meaningful OOD:** The prior 0191 numeric sintering-time/temperature residual model trains on 1100–1220 C and conventional manufacture. This is pressure-assisted HOT_PRESS at 56 MPa and 600–700 C; 0191's process predictor is explicitly **NOT ROUTABLE**, all six series ABSTAIN. This is not an out-of-paper learner gain; there is no candidate-ranking superiority claim for this new DOI, even though it adds a scientifically useful counterexample.

The implementation requires live first-party publisher HTML, exact DOI and author binding, unscaled 25 C target, full original Table 2, frozen all-18 numeric match and SHA256 of original HTML. If original Wiley retrieval is blocked or returns a page with no author measurements, the source workflow **fails closed**; tests passing on fixtures never substitute for retrieval of the actual source.

See [source executable](../scripts/science/obelix_solo_oxide_author_te_hotpress_0194.py), [mutant/source regression tests](../tests/test_phase3_obelix_solo_oxide_author_te_hotpress_0194.py), [first-party source workflow](../.github/workflows/phase3-solo-oxide-te-hotpress-original-0194.yml).

Solo objective remains original independent material/process candidate choice under equal free compute; not merely descriptive conductivity regressions or additional CI paperwork. Future 0195 must identify a **compatible hot-pressing train DOI** (or new exact-25 C comparable thermal-process source) before fitting/evaluating a route-specific predictor on this already-exposed paper. Science verdict INCONCLUSIVE, original official OBELiX TEST 121 unread, physical P0-01/02/03 BLOCKED, production OFF.
