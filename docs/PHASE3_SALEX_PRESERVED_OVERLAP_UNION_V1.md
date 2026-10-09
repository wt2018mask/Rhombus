# Phase 3: reuse preserved sAlex–WBM overlap without a new Kaggle run

## Goal

The 2026-10-08 sAlex Kaggle run has completed and produced
a six-piece byte-verified output archive preserved in a private GitHub
draft Release (ID 406879217). One small **369,521-byte** asset contains the
zstd-compressed WBM→sAlex source-overlap result: 256,963 per-material rows.
The companion 1,185-byte summary was also archived. We can independently
recompute *de-duplicated source-overlap statistics* from those existing
artifacts without repeating the 10,447,765-frame sAlex computation.

This is **source-only evidence**; sAlex source overlap does not attest the
selected frames actually used for MACE-MPA-0 training. Nothing here grants
unseen-generalization eligibility.

## Run offline against existing downloaded artifacts

Use the original draft GitHub Release by **release ID**, not its ambiguous
tag; verify assets and authorization separately before downloading.
Do not publish the draft release or modify/delete its duplicate.

    python -m pip install zstandard
    python -m scripts.development.analyze_preserved_salex_wbm_overlap \
      --compressed-overlap rhombus_phase3_wbm_salex_overlap.jsonl.zst.part0000 \
      --preserved-summary rhombus_phase3_salex_summary.json \
      --report new-salex-source-only-overlap-triage.json

The script makes **no network calls**. Before emitting a new report, it
checks the exact known SHA256 and byte size of the compressed asset, the
SHA256 of the original summary, the complete decompressed SHA256 of the
original overlap JSONL, 256,963 strictly sorted unique WBM material IDs,
typed Boolean matching columns, empty unresolved `audit_basis_ids`,
frozen sAlex and WBM source identities, expected 10,447,765 sAlex rows,
and the original summary's per-class source-overlap totals.

The report contains counts, not material IDs or raw source structures.
It computes exact/near/prototype matching intersections and the distinct
positive-match union, as well as the WBM remainder with **no detected sAlex
source overlap**. The remainder is explicitly **UNRESOLVED**, *not* unseen
by the model or eligible for empirical calibration.

## Real preserved-data offline verification — 2026-10-09

A pre-existing user-preserved copy of the 369,521-byte compressed overlap
asset and the 1,185-byte summary was read **in this development turn**.
Exact archive SHA256, original summary SHA256, streamed decompressed JSONL
SHA256, all 256,963 strictly ordered unique WBM IDs, boolean match flags,
empty audit basis IDs and source marginal totals were independently checked.
This independent actual-data verification used system `zstd -dc` plus a
read-only Python JSONL stream, not the newly added cross-platform CLI;
therefore CI integration coverage of that CLI remains distinct.

The new [frozen source-only observation](../data/development/phase3_salex_preserved_source_overlap_union_observation_v1.json)
records: **near-only 1,879, prototype-only 53, both near+prototype 14,
exact 0, distinct positive SOURCE overlap 1,946**, and 255,017 WBM
structures without detected sAlex *source* overlap that remain
**unresolved for MACE-MPA-0 model training exposure**.

## Known source-only counts (preserved summary)

- exact: 0
- near duplicate: 1,893
- prototype overlap: 67

The verified union is **1,946** (1,893 + 67 − 14), calculated from all
256,963 actual preserved rows and bound to frozen compressed/decompressed
SHA256 identities. The 255,017 unmatched-by-sAlex-source rows are **NOT**
MACE-MPA-0 model-unseen. The exact training frame lineage remains unknown.
No new MPTrj 1MiB/12.2GB source request or Kaggle job occurred.
