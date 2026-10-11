# Phase 3 checkpoint 0136 — source-eligibility funnel for a public benchmark

## Baseline and documentation repair completed before development

Canonical `main` at start: `b38870f9f007d62a67fc250d3199145d655f13bc`;
[PR #299](https://github.com/wt2018mask/Rhombus/pull/299) merged after
Development Continuity, Fast CI, Wave 2, and actual OBELiX + Caltech source
workflow **all passed**.

Before adding code, this PR updated:

- The **top of README.md** with the actual latest canonical 0135 status,
  public dataset denominators, source licensing and all scientific P0 blocks.
- `data/development/CURRENT.json` to checkpoint **0136** with compact
  versioned append-only continuity, explicit next action 0137.
- Generated `docs/DEVELOPMENT_HANDOFF.md` from the *effective inherited*
  baseline plus 0136 compact state; the prior 0135 handoff was byte-verified
  before regeneration.
- Append-only event `data/development/checkpoints/0136-science-public-benchmark-quality-funnel.json`.

Historical README sections remain historical; earlier evidence artifacts
and canonical 0135 benchmark bytes are left untouched.

## Why a source eligibility funnel, not a premature 571-record leaderboard

The actual original CaltechDATA CSV was previously downloaded and checked
against the primary published MD5 and fixed SHA256; its 571 source
literature rows have the following exact field names:

`compound`, `icsd_collectioncode`, `conductivity_doi`,
`conductivity_siemens_per_cm`,
`lowest_extrapolation_temperature_K`.

Original Caltech source SHA256:
`868c4bd793d7c31b929787dc69478691b27ced0440d19269075143c98ecd1545`.
Original 0135 public OBELiX TRAIN 478 JSONL source SHA256:
`c166ca57817bc962f9f664d8b0a3359274cd27d601ef4eef4e11c7209a123067`.

Actual source overlap in 0135: 225 Caltech records with an exact DOI
signal against public OBELiX TRAIN; 346 without; 113 shared distinct DOI
tokens. **No claim of 346 novel materials is supported.** The Caltech
temperature column refers to the *lowest extrapolation temperature*, not
necessarily the actual measurement temperature. An ICSD collection code
is neither independently verified exact atomic coordinates nor permission
to redistribute the ICSD structure.

## 0136 implementation

`scripts/science/public_transport_quality_funnel.py` reads only the
original file and the verified 0135 public TRAIN candidate artifact.

**All checks are source-only, deterministic and aggregate-only:**

- Re-verify official Caltech source original MD5, SHA256, row budget, and
  five exact field names; reject other snapshots and malformed rows.
- Re-verify exact OBELiX 0135 public TRAIN JSONL hash/partition/science
  no-GO before any cross-source candidate comparison.
- Count reported source fields with DOI, ICSD structure code, original
  composition string, positive finite conductivity metadata and positive
  finite *lowest extrapolation temperature*. Missing/nonfinite/negative
  values are explicit review flags, never silently replaced.
- Calculate **DOI candidate overlap against original OBELiX TRAIN only**;
  reserve original public TEST identities/labels, including the 121
  original source test records.
- Count distinct exact **formula/ICSD/DOI string proxy** keys and repeated
  rows. These are duplicate-*candidate* signals, **not** physically
  identical samples, phases or mutually independent experimental units.
- Separate field-complete **manual-review candidates** from properly
  verified measured experimental conductivity/temperature/structure
  and source-independent materials. The latter remain **unknown**;
  new science-qualified material count is **zero**.

The original source CSV stays inside the temporary runner environment.
`caltech_source_quality_aggregate.json` outputs **only integers,
source hashes, field names, scope flags, and conservative limitations**.
It emits no original third-party row values, formula strings, DOI tokens,
ICSD codes or licensed structure coordinates. Publication and commercial
rights remain unresolved, regardless of source availability.

The actual-source workflow
`.github/workflows/phase3-obelix-real-source.yml` executes this
diagnostic immediately after the 0135 real Caltech/OBELiX source
acquisition. The uploaded artifact
`public-transport-0136-caltech-eligibility-aggregate` contains
only aggregate evidence.

Local replay (requires the exact checked Caltech original, not user
invented data):

```powershell
py -3.11 scripts/science/public_transport_quality_funnel.py `
  --caltech-csv "C:\\data\\original-caltech-571.csv" `
  --obelix-benchmark-dir "C:\\data\\public-transport-0135" `
  --output-dir "C:\\data\\public-transport-0136-quality"
```

Adversarial Fast CI:
`tests/test_phase3_public_transport_quality_funnel.py`.

## Verified actual 0136 original-source result

[GitHub Actions run #38108708936](https://github.com/wt2018mask/Rhombus/actions/runs/38108708936)
**PASSed** after making the scientific parser distinguish **all original DOI
strings** from the smaller set of DOI tokens beginning with valid `10.`.
The first real-source run failed because the two denominators were
incorrectly equated. We corrected the distinction and now fail closed
with per-field aggregate drift counts, without leaking original
third-party source rows. Both original source hashes remain immutable.

| Caltech original-source review funnel | Real observed count |
| --- | ---: |
| Original source rows | **571** |
| Positive finite reported source conductivity | 571 |
| Source entries carrying an ICSD identifier | 571 |
| Source entries carrying usable `10.` DOI token | 569 |
| Positive finite lowest **extrapolation** temperature | 135 |
| All five source metadata fields present/parseable | **134** |
| All-five-metadata records without exact OBELiX TRAIN DOI signal | **56** |
| Source formula + ICSD + DOI string proxy keys | 569 |
| Formula + ICSD string proxy keys | 571 |
| Repeated exact formula/ICSD/DOI proxy rows | 0 |
| Caltech source rows with OBELiX TRAIN DOI signal | 225 |
| Source paper / phase / actual experimental temperature authenticated | **0** |
| Newly science-qualified independent materials | **0** |

**These are not 134 benchmark-ready samples, 56 genuinely new
materials or 569 independently measured conductors.** Caltech's
`lowest_extrapolation_temperature_K` does not identify exact
experimental measurement temperature; original paper, structure and
sample adjudication remain unperformed. Formula/ICSD/DOI string keys
are *deduplication review signals*, not certified physical objects.

Artifact `public-transport-0136-caltech-eligibility-aggregate`,
ID `11690726618`, was downloaded and independently rehashed:

- Original task-specific runner SHA:
  `e8cdddb6cc074d068d4f4d15f145ec08988be5df`
- Original aggregate JSON SHA256:
  `95779db2eb7bdba527b919ec9c98ee0a61588b0e20cca79fd95951f70ec28678`
- Downloaded archive ZIP SHA256:
  `17f255e9dc79e8741b090f39c137bf8c5c1ac91cfb6e041d7c1a6a2222317677`

This verifies source parsing and correct scientific conservatism,
**not** independent experimental or external blind qualification.
The final PR head must pass the four required CI jobs again.

## Next evidence expansion and scientific gate

0137 should acquire/review other **primary source downloads and their reuse
licences**, beginning with Liverpool / Laskowski and DDSE, then Shon–Min and
SPSE. Only data whose original source byte identity, rights and actual
experiment conditions can be verified should be added to future public
downloadable rows. Do not silently add the whole Caltech original 571
records to the existing 478-row OBELiX public TRAIN set.

The conversion funnel must continue to report distinctly:

`original acquired → exact source hash verified → reuse rights cleared →
original DOI/sample/phase/quantity/temperature checked → structure bound
to measured sample → repeated measurements and duplicate materials
adjudicated → exact model training exposure audited → externally sealed
blind cohort evaluated`.

Passing GitHub Actions demonstrates **engineering and source parsing
integrity**, not source-independent scientific truth or external
blinding. No new MLIP/Kaggle compute, scientific scoring or release
authorization is granted by 0136. **Science NO-GO.**
