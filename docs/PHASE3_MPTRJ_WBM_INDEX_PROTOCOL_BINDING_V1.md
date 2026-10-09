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


## Checkpoint 0092 — frozen candidate bucket row consistency

Before issuing a costly full original MPTrj download, the reader scans all WBM target rows read-only and recomputes the candidate fingerprint digest from stored reduced composition + site count using the frozen protocol ID and canonical JSON serialization. Any mismatch fails closed before the remote request. This closes the false negative risk from silently stale or corrupted candidate buckets that merely carry the expected protocol metadata. The check does **not** reverify WBM source bytes or independently validate prototype labels or model training selection. Fixture-only custom fingerprint callbacks remain explicitly non-authoritative.


## Checkpoint 0095 — critical v1 prefilter unsound for near duplicates

**Erratum:** The historical `rhombus-composition-site-count-candidate-fingerprint-v1` bucket contains original site count. The exact matcher explicitly requires the same count, but the near matcher may accept distinct original unit/supercell site counts after primitive-cell normalization. Thus the v1 prefilter could **skip** genuine near duplicates. In checkpoint 0095 the active protocol changes to `rhombus-reduced-composition-candidate-fingerprint-v2`: its canonical SHA256 JSON payload contains only `protocol_id` and `composition_key`. Original `site_count` remains a separately checked SQLite field but no longer partitions the candidates. Both original MPTrj and sAlex target index readers reject stale v1 metadata. Previous v1 SHA256/indices are **not silently migrated**. New v2 indices require fresh authorized construction from frozen sources; this development change does not run sAlex or MPTrj full streams. See [v2 protocol](../data/development/phase3_candidate_fingerprint_prefilter_soundness_v2.json).

## Checkpoint 0106 — stored WBM structure must agree with v2 index fields

In addition to the 0092/0095 fingerprint and protocol checks, the original MPTrj one-pass source-only reader now scans each existing SQLite target row **before making a costly MPTrj source network request**. It bounds each persisted JSON to 4 MiB, parses the actual stored pymatgen structure, and independently checks its **reduced elemental composition** and **original site count** against the separate indexed `composition_key` and `site_count`. The existing canonical v2 digest check still binds the `composition_key` to its protocol ID. Hence even a self-consistently forged `composition_key` / `candidate_fingerprint_sha256` pair cannot authenticate a different WBM stored structure.

Malformed, empty, oversized or mismatched target JSON fails closed. A structure's legitimate supercell site count is allowed as long as it agrees with the indexed original count: the v2 **candidate bucket remains composition-only** and does **not** reintroduce the unsafe v1 site-count prefilter. All checks are local and one row at a time, and fixture-only custom callbacks remain non-authoritative. In particular the preflight does **not** rerun costly frozen Matbench prototype-group labels, independently hash original WBM file bytes, or establish model training frame lineage; separate source and protocol provenance are still required. No actual original WBM or full MPTrj data transfer occurs in this patch.

## Checkpoint 0107 — preserve the verified SQLite target snapshot during MPTrj comparison

The 0106 target-structure validation is now held together with all subsequent
MPTrj source-only comparisons in one explicit SQLite **read transaction**,
started before querying index metadata. A second process can commit a WAL-mode
SQLite target update, but it cannot substitute changed `structure_json`,
composition/site-count metadata or candidate hashes inside the already-validated
observer's consistent snapshot. All read-only profile, match, witness and
source-target export queries use the same connection until the observer exits.
A separate, newly opened observer sees the modification and must reject
inconsistent data before a full MPTrj GET. Fixture tests cover concurrent
writer commits and exceptional observer closure without any live source access.

This protects **one local database snapshot** from a post-preflight mutation.
It does not independently bind that snapshot to a freshly verified original WBM
gzip or prove model training membership. The snapshot is deliberately held
throughout a potentially lengthy original MPTrj source observation. Although
WAL writers can continue to commit, the pinned read transaction can prevent
old WAL pages from being checkpointed/reclaimed until the observer closes.
Operators should avoid concurrent target-index mutation during any separately
approved original MPTrj source run. No source transfer is started by this change.
