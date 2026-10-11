# 0153-B — Real original open accepted-manuscript verification (LAGP)

Goal: replace abstract-only review with **actual first-party text source bytes**, without inventing experimental sample qualification. One of the eight 0152 primary publisher DOI abstracts is Weiss et al. LAGP `10.1021/acsami.8b00842`, linked in 0152 to **two separate original OBELiX TRAIN exact-CIF records**. The US DOE OSTI indexed URL [publicly hosts an author-accepted manuscript](https://www.osti.gov/servlets/purl/1434719). Publisher page [ACS](https://pubs.acs.org/doi/10.1021/acsami.8b00842) lists supplementary X-ray/neutron Rietveld PDF and an author-provided CIF ZIP; these files are **not yet byte-verified or inspected by this checkpoint**. The accepted version differs from the formal final version of record and must not automatically be treated as publisher final layout or tabular calibration.

## Reproducible original source attempt

The [0153 GitHub Actions original-source workflow](../.github/workflows/phase3-original-public-manuscript-0153.yml) (1) installs pinned bounded PDF parser `pypdf==5.9.0` and runs adversarial local fixtures, (2) makes only an explicit host-restricted HTTPS request to OSTI, subject to 12MiB/60-page/text limits, (3) computes SHA256, extracts full-document text *ephemerally*, and requires exact original DOI and topical markers in the bytes, (4) publishes only hashes, page/length counts and boolean text-context features. Original publisher PDF bytes, extracted prose, tables, CIFs, TEST rows or experimental numbers are **never** uploaded. Host redirects or unavailable/garbled PDF **fail closed**, not a silently successful paper read. Access and source identity are distinct from human scientific review.

## Actual state and scope

- 0152: original 10 source-CIF queue rows / eight reviewed **publisher abstracts**; two source rows share this DOI.
- 0153 pending GitHub real-source experiment: OSTI accepted manuscript bytes *may* be verified; a successful workflow demonstrates accessible full-document PDF text with matching DOI, not that supplementary figures/tables were adjudicated.
- Numeric source-paper conductivity and temperatures remain **unmatched to any specific original CIF row**. Original P0-01 blind, P0-02 exact MACE training frames, P0-03 independent-material precision remain **BLOCKED**. A publication-level text hit is not independent physical sample/phase identification or actual transport comparison.
- Follow-on 0154-B needs real supplementary PDFs/CIF ZIP, original sample composition x and phase/occupancy, measured temperature, bulk/total conductivity and experimental sample matching before any physical structure ordering or finite-temperature MACE.
