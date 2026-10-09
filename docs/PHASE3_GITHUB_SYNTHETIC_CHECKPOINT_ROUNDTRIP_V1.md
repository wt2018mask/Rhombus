# Phase 3 — GitHub synthetic checkpoint transfer experiment (0117)

**Purpose:** Validate actual upload to the GitHub Actions artifact service,
then independent download and re-verification by a second runner, before
attempting expensive real Kaggle work.

The workflow `.github/workflows/phase3-github-synthetic-checkpoint-roundtrip.yml`
runs on narrowly scoped pull requests and offers a separate manual
`run_synthetic_roundtrip=true` opt-in (default false).
The producer creates only **eight artificial SQLite records**, invokes
the SHA256 checkpoint part bundler, and uploads a small no-overwrite
parts+manifest set using `actions/upload-artifact@v4` with
**seven-day retention**.

A second runner's `actions/download-artifact@v4` downloads the bundle,
checks every part's SHA256, reassembles the SQLite bytes and independently
verifies source SHA256, SQLite `PRAGMA quick_check`, and the eight
exact test rows. The workflow prints
`GH_SYNTHETIC_CROSS_JOB_ARTIFACT_ROUNDTRIP_PASS_NO_KAGGLE_RESUME`
only on successful completion.

An initial PR-head real two-job transfer succeeded in
[GitHub Actions run #37945062113](https://github.com/wt2018mask/Rhombus/actions/runs/37945062113).
Check the **final PR-head** run before merge. Offline tests:
`python -m pytest -q tests/test_phase3_github_synthetic_checkpoint.py`.

**Limitations:** Source-free synthetic data only. An uploader inside
Kaggle, exact member/shard-bound resume, externally retrieved authentic
source receipts and post-worker-crash persistence are NOT implemented.
A local verifier cannot assert an upload by itself; the independent
GitHub workflow provides the experiment's provider transport evidence.
Artifacts expire after seven days and do not establish long-term GitHub
Release durability. Existing MACE-MPA-0 training selection remains
unattested; no original MPTrj or sAlex recomputation starts here.
