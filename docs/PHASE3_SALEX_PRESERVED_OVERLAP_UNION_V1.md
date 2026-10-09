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

## Known source-only counts (preserved summary)

- exact: 0
- near duplicate: 1,893
- prototype overlap: 67

The union is **not yet known** from these marginal counts because the near
and prototype groups may intersect. No estimated union is stored here.
Run the offline tool on the preserved raw artifact to establish it.

No real archive reread, MPTrj 1MiB/12.2GB source request, or new Kaggle job
was performed in this development checkpoint.
