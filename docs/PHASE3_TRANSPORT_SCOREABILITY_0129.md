# Phase 3 science 0129 — transport reference scoreability preflight

This checkpoint develops the **science bottleneck** between large experimental
data acquisition and legitimate benchmark scoring: a measured conductivity
source row is not automatically independent material-level ground truth.

## Execute after checkpoints 0127 and 0128

Use the files produced by the two previous offline CLIs. With Python 3.11
and Rhombus importable, from the repository root:

```powershell
py -3.11 -m rhombus.qualification.transport_scoreability `
  --obelix-records-jsonl "C:\\path\\to\\0127\\records.jsonl" `
  --obelix-summary-json "C:\\path\\to\\0127\\summary.json" `
  --review-pairs-jsonl "C:\\path\\to\\0128\\review_pairs.jsonl" `
  --identity-summary-json "C:\\path\\to\\0128\\summary.json" `
  --output-dir "C:\\path\\to\\0129-scoreability"
```

The CLI does not download sources, train MACE, call an LLM, launch Kaggle,
run MD, or modify the public official OBELiX TRAIN/TEST split.

It recomputes the **entire 0128 duplicate-review pair output and summary**
from the hash-bound 0127 records and rejects any mismatch. This prevents
overlap evidence (including a possible train/test leakage pair) from being
removed merely by editing a JSON summary. Outputs
`scoreability_records.jsonl` and `summary.json` are deterministic and
include an output SHA256 tied to the original input snapshot and overlap report.

## Scientific categories and sample counts

Every source record is retained, never automatically clustered or dropped.

- `SOURCE_CIF_AVAILABLE_PHASE_UNVERIFIED`: a source "Match" or "Close Match"
  has a linked CIF, **not** a verified match to the experimentally measured
  phase, disorder or sample
- `SOURCE_CIF_ABSENT`: no source-linked CIF, not structurally scoreable
  through this intake
- `EVIDENCE_GAPS`: missing original experiment review, exactly measured
  temperature, phase and structure identity, material independence, and
  exposure to MACE training records
- `POTENTIAL_IDENTITY_CONFLICT_REQUIRES_REVIEW`: 0128 identified a candidate
  with common composition string, DOI or CIF hash; never silently merge
- `DECLARATION_COMPLETE_INDEPENDENT_AUTHENTICATION_REQUIRED`: a reviewer
  *claims* that evidence exists for this record; this is **not** authentication
  of experimental truth or proof of unseen generalization

The report counts total source records, official TRAIN/TEST, exact-match,
close-match and missing CIF, numerically processed point values, affected
records from identity signals and reviewer-declared completeness.

**No valid path in this checkpoint sets a new source record's
`independent_transport_truth_qualified=true`.** The independent-material
count and independently qualified benchmark count remain `null`, not
fabricated as 599, 518 or the number of available CIFs. No new independent
blinded test is created. The science verdict remains `INDETERMINATE`.

A source's reported "room temperature" cannot be silently treated as a
verified exact 298.15 K value. Experimental ionic conductivity and MD
self-diffusion are **different quantities**; transport scoreability must
compare the same quantity, temperature and phase, or explicitly justify a
separate physical mapping.

## Optional untrusted curation declarations

`--curation-declarations-json FILE` may contain a bounded JSON **array** of
`rhombus-transport-reference-review-declaration-v1` objects. Each object
is keyed by the original source ID and the exact 0127 source-record SHA256,
plus a declared source evidence-artifact SHA256, conductivity measurement
quantity, precise temperature in Kelvin, phase assessment, experimental
value assessment, independent material assessment, and MACE training
exposure assessment.

This is deliberately **not an Ed25519-verified independent receipt**. A hash
written by the same reviewer is a declaration, not external attestation.
Even a fully completed declaration leaves scientific approval blocked.
Censored upper-bound records cannot be turned into point measurements, and
a missing/close-match CIF cannot be declared an exact experimental phase.
A single-source assertion of "not in training" is not an independent
original-frame lineage audit.

For actual independent scientific acceptance, separately acquire original
measurement records, authenticated independent reviewer/steward receipts,
source-specific temperature/quantity/structure/phase linkage, verified
material grouping, and MACE-MPA-0 selected training-frame evidence. A
separate B1 sealed trial and statistical precision design remain mandatory.

## Scope / evidence

Code: `rhombus/qualification/transport_scoreability.py`.
Regressions: `tests/test_phase3_transport_scoreability.py`.
Checkpoint evidence:
`data/development/phase3_transport_scoreability_0129_evidence_v1.json`.

The next practical bottleneck is source-to-evidence adjudication and a
**small independent real-source pipeline execution** before any new GPU
submission, not more synthetic benchmark sample-size claims.
