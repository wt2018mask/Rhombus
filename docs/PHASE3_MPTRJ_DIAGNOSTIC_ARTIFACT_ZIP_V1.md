# Phase 3 — bounded MPTrj diagnostic ZIP-to-receipt byte binding (v1)

Checkpoint 0075 adds a **local byte-equality** check for the diagnostic report that the manual GitHub Actions workflow *may* upload. It is offline-only, optional, and does not dispatch any action or download Figshare, MPTrj or the model.

## Use after a separately authorized manual run

1. Independently inspect the official GitHub Actions run and its GitHub API data, including run ID, source SHA, workflow path and status.
2. Download the named `mptrj-first-frame-observation` artifact ZIP from that exact run via GitHub's interface/API, preserving the ZIP without extracting it.
3. Supply the ZIP and the separately saved local JSON receipt to the extended reviewer:

```powershell
python -m scripts.development.review_mptrj_manual_run --run-json .\run.json --artifacts-json .\artifacts.json --receipt .\mptrj-first-frame-observation.json --artifact-zip .\mptrj-first-frame-observation.zip --expected-head-sha <reviewed-main-40hex-sha>
```

The checker requires a regular non-symlink ZIP at most 64KiB, exactly one member named `mptrj-first-frame-observation.json`, no directories/traversal/symlink/encrypted members, and at most 16KiB of declared and actually read member data. It hashes and compares the exact uncompressed ZIP member and separately supplied receipt bytes, and applies the strict existing receipt schema (including duplicate JSON field rejection and no scientific claim promotions). No extraction and no file writes.

The `--artifact-zip` option is optional for backwards compatibility, but omitting it explicitly prints `RECEIPT_NOT_BOUND_TO_ARTIFACT`. A successful ZIP check prints `LOCAL_ARTIFACT_ZIP_RECEIPT_BYTES_MATCH_SHA256`.

**What is NOT proven:** A ZIP copy and local JSON copy can both be forged. Matching bytes do not authenticate the GitHub API snapshots, live Actions execution, canonical Figshare source, or MACE-MPA-0 training frame manifest. Operator must separately verify real GitHub provenance. The 12.2GB source has **not** been read; sAlex/Kaggle are untouched, and WBM exposure, calibration and unseen-generalization authorization remain denied.

This work is fixture tested only; it does not launch the manual observation.


## Checkpoint 0076 — GitHub REST whole-ZIP digest claim

When `--artifact-zip` is supplied, the named artifact's REST `digest` field must contain a canonical `sha256:<64 lowercase hex>` value. The checker now hashes the same bounded ZIP bytes it parses, checks the whole-ZIP digest against the supplied REST metadata, then compares the single uncompressed JSON member to the local receipt. An absent, invalid, or mismatched archive digest fails closed; metadata-only review without ZIP stays backward compatible.

A successful result prints `CALLER_SUPPLIED_GITHUB_ARTIFACT_DIGEST_MATCH_SHA256`. This is still a comparison to **caller-supplied** API JSON. It does not authenticate that JSON, the ZIP origin, the upstream Figshare bytes, or MACE-MPA-0 training frames. Operators must independently inspect the official live GitHub API and action run; no scientific gate opens.
