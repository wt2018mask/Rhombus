# Phase 3 — source-only WBM index fingerprint/prototype provenance (checkpoint 0091)

The one-pass original MPTrj-to-WBM source-only comparator must not silently consume a
WBM target SQLite built by a different fingerprint-bucketing or prototype-label
executor. A wrong bucket can produce false source-level non-matches even if the WBM
initial-structure file SHA256 and row count appear correct.

## Index creation and validation

`rhombus.domain.overlap.build_wbm_target_index` writes two additional index
metadata keys:

- `candidate_fingerprint_protocol_id` — the frozen
  `rhombus-composition-site-count-candidate-fingerprint-v1` ID **only** when the
  bundled `structure_candidate_fingerprint_sha256` callback is selected.
- `prototype_group_protocol_id` — the frozen
  `matbench-protostructure-label-v1` ID **only** when the bundled
  `matbench_prototype_group` callback is selected.

If either callback is replaced, that field is instead marked
`CUSTOM_UNATTESTED`. No callback is certified solely because it outputs the
expected-looking value.

The original MPTrj source/WBM overlap observer requires both metadata IDs
to agree with the executors selected for comparison, plus the expected
original WBM SHA256 and exact target row count. Its **production defaults**
reject custom callbacks entirely. Test fixtures with alternate callbacks
must opt in using `allow_custom_protocols_for_fixture=True`; the
production command-line runner does not expose that flag.

A missing metadata field in an older WBM target index is **not
silently accepted**. The index must be rebuilt from the frozen verified
source and pinned executors before expensive original MPTrj streaming.

## Scientific boundary

These stored IDs are consistency and preflight evidence: they are
**not independently authenticated hashes of the SQLite index contents**
and do not replace verifying the original WBM data bytes, code/runtime
versions, or full MPTrj source. Original-source structural matches still
do not establish which frames were selected to train MACE-MPA-0.

Only small, offline synthetic SQLite and structure fixtures are exercised
by checkpoint 0091. No new MPTrj 1MiB or 12.2GB data request or Kaggle run
occurs.
