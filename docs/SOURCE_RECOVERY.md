# Original-source recovery for checkpoint 0194

The institutional publisher Version of Record for Campanella et al.,
*ChemSusChem* 2023, 16, e202300399, DOI **10.1002/cssc.202300399**, passed
[actual GitHub Actions verification 39357927381](https://github.com/wt2018mask/Rhombus/actions/runs/39357927381/job/118416972769)
on code commit `1fd36ff2b7594fdc0e186fdd693941ede0cba417`.
The complete machine-readable [source receipt](../data/development/0194-unimore-vor-authenticated-source-v1.json)
retains execution provenance, raw-file identity, rights evidence, extracted
cell mappings and Unicode-decoding evidence. This authenticates an existing
published source; no new model comparison or material experiment was performed.

- Institution: Universita degli Studi di Modena e Reggio Emilia,
  [record 11380/1328508](https://iris.unimore.it/handle/11380/1328508).
- Original PDF size: **3,845,459 bytes**.
- Original PDF SHA-256:
  `871e6ff252cce27799e8e2bf5455667bdaf6dc639dde2875ad57a4ecce5fc58b`.
- Source qualification: publisher VOR obtained over HTTPS from the fixed
  institutional record/file handle. Wiley HTML authentication is separate.

## Rights evidence

The selected file's table row declares `VOR - Versione pubblicata dall'editore`
and `[IR] creative-commons`. Its AJAX `licenseUri` is
`http://creativecommons.org/licenses/by/4.0/`, bound to the same file UUID's
`license_<UUID>` element. The verifier reads this literal metadata without
executing JavaScript; HTTPS canonicalization identifies the same license.

The PDF itself states the Creative Commons Attribution License and permits use,
distribution and reproduction with proper citation. It does **not** explicitly
state a license version in that notice. Version 4.0 comes from the institution's
file-specific metadata; that distinction remains in the receipt. Repository-wide
CC0 metadata rights and the site's default file policy are not used as
this document's license evidence. Raw PDF bytes are not redistributed.

## Scientific mapping and decoding

Table 2 binds six named series to 600/650/700 C hot pressing, with
conductivity reported at 25 C in S/cm. All **18 keyed cells** are verified as
`(nominal series, hot-press temperature) -> total ionic conductivity`.
The adjacent Figure 4 text identifies the total-conductivity observable.
Value swaps between series or temperatures, changed series, temperature, units,
DOI or numerical cells fail verification. Expected constants are used only
for comparison after the source cells have been independently associated.

The PDF's embedded TeX math font has no Unicode mapping for code 0. Ordinary
extraction consequently drops the minus signs. The verifier pins the original
PDF, embedded font and original CMap; decodes the Type1 program; and checks
code 0's actual rounded horizontal-minus contour. Only that audited code point
is mapped to U+2212 in a temporary extraction copy. The raw source bytes remain
unchanged. The receipt records the contour, font/CMap hashes, extraction-copy
hash, extractor versions and resulting table mapping. Native Poppler layout
preserves columns; pypdf reading order preserves the two-column license notice.
No OCR, missing-cell filling or expected-value-based sign inference is used.

The 18 conditions are **one paper and six nominal series**, not 18 independent
materials or specimens. Author-reported 25 C values do not attest that each
was directly sampled by EIS at exactly 25 C. The 0191 conventional-sintering
model remains outside this 56 MPa hot-press domain. Production stays OFF,
scientific GO is false, and P0-01/02/03 remain BLOCKED. Official OBELiX TEST 121
labels remain unread.

## CI and integration

The original-source qualification job requires authenticated institutional VOR
identity, rights and every keyed cell. The separate Wiley availability job
records `UNAVAILABLE`, `publisher_live_source_verified=false` and a null HTML
hash when both endpoints return 403. It does not qualify the source; received
invalid HTML and TLS failures still fail. The default strict Wiley CLI remains
fail-closed. A frozen numerical diagnostic is never source authentication.

PR 363's HEAD is `3c2f42f6f5c3c88acfb55fcd6cdf7acab8b76802`; its base is
main at `1aaaa555a9a1ce2c9123845402fec4e664626708`.
Its six historical SI ZIP failures all succeeded on selective failed-job reruns
without scientific-code changes: **56/56 latest checks passed**. PR 364 remains
stacked on 363. Existing 0193/0194 checkpoint events and baseline snapshots are
unchanged; checkpoint 0195 is not consumed by this repair.

The branch API reports main protected, with no required status contexts in its
visible summary; no rulesets were returned. Detailed protection access returned
403, so additional review/admin conditions are unverified. Repository contracts
still require Fast CI, canonical Wave 2, continuity and the task's scientific
workflow on the final commit. No merge is authorized by this source recovery.
