# Phase 3 MACE-MPA-0 full model binary observation — checkpoint 0140

**P0-02 remains OPEN / independent training lineage NO-GO.** The objective is to eliminate a *small but real* provenance gap: actual full-file observation of one publisher-supplied **79,462,305-byte** MACE-MPA-0 medium binary, rather than solely trusting a digest copied from a source file.

## Source and reproducible scope

- Model: MACE-MPA-0 medium; exact filename `mace-mpa-0-medium.model`.
- Official publisher release tag: [ACEsuit/mace-foundations `mace_mpa_0`](https://github.com/ACEsuit/mace-foundations/releases/tag/mace_mpa_0).
- Official release asset GitHub API ID **213937064**, original publication **2024-12-17**. Reported size **79,462,305 bytes**. This GitHub metadata does not provide an independent SHA-256 digest.
- Existing Rhombus publisher-reported SHA256: `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`, pinned in `rhombus/domain/mpa0_publisher_digest.py`.

Run one bounded GitHub Actions CPU job on the exact PR commit. Use HTTPS with finite time, redirect and file-size limits to download **only that binary**, hash the **entire** temporary file in streamed chunks, fail closed if length or digest differs, then erase no content from the publisher. Upload **only an aggregate source-bound JSON receipt**, not the model weights. This is not heavy scientific simulation, data republishing or a Kaggle workload.

## Claims and nonclaims

A successful real download/re-hash means the **public release asset's full bytes** match the already recorded publisher-reported digest *when observed by this GitHub Actions job*. This is a reproducible computational check, not a separately appointed external scientific auditor or independently signed attestations. It does not establish actual checkpoint-selected MPTrj/sAlex frame membership, complete original source files, preprocessing rules, DFT energy/force label selection, leak-free test materials, empirical calibration, generalization, or independent blind evaluation.

**P0-02 remains BLOCKED** until authenticated selected-frame manifests, full original source SHA256, rules and independent role-bound receipts (see `rhombus/domain/training_manifest.py`). **P0-01 and P0-03 remain BLOCKED**. Never rewrite legacy science results. Do not interpret GitHub Actions CI PASS as scientific GO.

## Acceptance

- Exact asset API/release tag/name and size bound verified.
- Negative tests for truncated, altered, oversized, wrong source metadata, wrong digest and argument spoofing.
- No model weights or source training frame identifiers in uploaded artifact.
- Retain full downloaded byte count and SHA256 in receipt, together with exact repository source and source asset ID.
- Final exact-head Development Continuity, R2 Fast CI, Wave 2 and new independent CPU artifact-hash workflow PASS, with P0 status all NO-GO.
