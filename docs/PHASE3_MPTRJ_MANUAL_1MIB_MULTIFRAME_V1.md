# Phase 3 — 1MiB manually dispatched MPTrj multi-frame observation

Checkpoint 0083 introduces a separate **manual-only** GitHub Actions workflow, distinct from the existing frozen 256KiB diagnostic. To run it, an operator must explicitly select the workflow **Phase 3 MPTrj 1MiB Multi-Frame Manual** and click **Run workflow** on a trusted main commit. **This development PR does not dispatch the workflow.**

The job first validates the Git-retained ZIP/receipt from the real MPTrj 256KiB observation (run 37852263493). It uses a strict HTTPS Range request for at most 1MiB of original Figshare source (file ID 41619375), requires HTTP 206 and exact declared source size, and keeps the response in memory. A redirect can involve additional HTTP requests. The first 256KiB SHA256 must equal the frozen real source digest, or the job fails without uploading anything.

At most 16 complete frames are parsed using pymatgen. The report includes material/frame IDs, atom count, formula, energy field presence, first 256KiB SHA256, 1MiB sample SHA256, declared source size, and a warning that the remaining stream is unverified. It uploads *only* a JSON metadata receipt no larger than 16KiB with 7-day retention. It never uploads raw source bytes, triggers Kaggle, or downloads the whole MPTrj source.

The workflow independently validates the JSON metadata before uploading it, requires read-only GitHub permissions, and has no schedule/push/pull request trigger.

A successful observation does **not** verify all 12,188,168,685 bytes, prove the exact MACE-MPA-0 training frame selection, authorize a WBM exposure audit, support empirical calibration, or establish generalization to unseen structures. Those gates remain closed.


## Checkpoint 0085 — timed pilot metadata

The manual-only observation report has been versioned to **v2**, adding two non-authoritative timed diagnostics: logical 1MiB Range operation duration and bounded frame inspection duration. Neither is a validated extrapolation to the full 12.2GB dataset. See [timed pilot and resource preflight guide](PHASE3_MPTRJ_TIMED_PILOT_RESOURCE_GATE_V1.md). This code change itself does not run the source request.

## Checkpoint 0111 — fail before remote access on broken runtime or frozen evidence

This 1MiB source probe remains a **separately approved diagnostic**, not
a source-wide or MACE-MPA-0 training audit. To avoid repeating the real WBM
profiling runtime failure, the manual GitHub Actions workflow now requires
an explicit boolean `run_1mib_probe=true` (default: **false**) in
addition to `workflow_dispatch`. The job condition rejects default/false
input before starting the runner's source-observation steps.

After installing the pinned parser dependencies, a **no-network preflight**
imports `ijson` and the exact production observer/parser modules, verifies
the original source's Git-preserved **256KiB first-frame ZIP and JSON
receipt**, checks the recorded complete first frame and original
12,188,168,685-byte registry size, and proves that the source range
cap is still 1,048,576 bytes. Only after this succeeds can the
`--observe` command request a bounded HTTP-206 Range. The preflight
does not infer successful HTTPS connectivity or parse any new original
MPTrj bytes.

After CI and merge, the operator may use GitHub Actions /
**Phase 3 MPTrj 1MiB Multi-Frame Manual** on `main`, set
`run_1mib_probe=true`, and click Run workflow. This is **optional**;
do not run the 12.2GB source or Kaggle task as a substitute. A successful
1MiB pilot can measure prefix parsing behavior only on that runner;
its timing cannot be safely extrapolated to full MPTrj, infer
MACE-MPA-0 selected training frames, or establish unseen-generalization.

## Checkpoint 0113 — verify actual 1MiB run and small metadata ZIP

After the source-reviewer PR merges into `main`, the operator may explicitly
dispatch exactly one bounded diagnostic on GitHub Actions /
**Phase 3 MPTrj 1MiB Multi-Frame Manual**, select branch `main`, check
`run_1mib_probe=true` and click **Run workflow**. The default false
intentionally refuses an accidental source request. This code change does
**not** authorize or perform a background dispatch.

For a successful real run, download the exact named
`mptrj-multiframe-1mib-observation` artifact ZIP within its seven-day
retention period. Preserve it without modification, record its run ID and
exact `main` SHA from the GitHub Actions page, then perform this
source-read-only public REST + local ZIP review:

```powershell
python -m scripts.development.review_mptrj_1mib_github_run `
  --live-review `
  --run-id YOUR_SUCCESSFUL_RUN_ID `
  --expected-head-sha EXACT_40_HEX_MAIN_SHA `
  --artifact-zip .\mptrj-multiframe-1mib-observation.zip
```

This reviewer performs **two bounded read-only GETs** for the exact Actions
run and named artifact metadata, then validates GitHub's ZIP SHA256 and
one approved JSON member against the original frozen first-256KiB
structure evidence. The report must show exactly **1,048,576** observed
prefix bytes, **1–16** complete structures, and honest two-phase runner
timings. It outputs a source-only JSON receipt containing the run identity,
archive/report digests and observed 1MiB count/timings; store this receipt
and original ZIP separately before the artifact expires.

The tool never initiates a Figshare download, Kaggle computation,
model-training proof or scientific performance claim. Even a successful
1MiB pilot does NOT establish full original MPTrj SHA256, exact
MACE-MPA-0 training selection, real full-source comparison cost or
unseen-generalization. Do not extrapolate pilot timings to 12.2GB.

If this manual job is not successfully completed, no actual 1MiB result
exists and there is nothing to archive or interpret.
