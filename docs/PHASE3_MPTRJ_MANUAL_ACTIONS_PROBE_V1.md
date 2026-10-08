# Phase 3 — manual-only MPTrj source first-frame diagnostic workflow

This is an optional GitHub Actions **manual** workflow, not a scheduled background data job. It exists to move from synthetic fixtures toward a real limited source observation without running a full 12.2 GB MPTrj data task.

**Workflow:** `.github/workflows/phase3-mptrj-first-frame-manual.yml`, named **Phase 3 MPTrj Capped Source Prefix**. It has `workflow_dispatch` as its only event. It never runs automatically on PR, push or a schedule.

## Execution and evidence boundaries

A manual **Run workflow** launches:

1. Read-only checkout of the exact workflow commit with persisted Git credentials disabled.
2. Minimal Python 3.11 parsing dependencies.
3. `scripts.development.probe_mptrj_source_prefix` with `--probe --require-complete-frame --prefix-bytes 262144` and a new diagnostic report path.
4. **Only after success**, upload that JSON as `mptrj-first-frame-observation`, with 7-day artifact retention. No original source data are included.

The existing inspector requires a canonical Figshare source URL, **exact HTTP 206 Content-Range**, HTTPS redirect, identity-encoded response and bounded reads. A server that responds with HTTP 200 or ignores Range causes a safe failure before body reads. **There is no fallback to a whole-file GET.** Job timeout is 10 minutes, the GitHub token is read-only, and the workflow requires no secrets or Kaggle tokens.

On failed negotiation or insufficient prefix to complete the first JSON frame, this run fails and **does not produce a success artifact**; it does not mean the source dataset is invalid.

## Operator steps (no run has been launched by this change)

After this PR has passed CI and been merged into `main`, choose **Actions → Phase 3 MPTrj Capped Source Prefix → Run workflow** and select `main`. A run initiates one limited network request, so only dispatch it intentionally.

If it succeeds, inspect its `mptrj-first-frame-observation` artifact for the `first_frame_structure` observation and the explicit `complete_original_source_hashed: false` and `unseen_generalization_claim: false` flags.

**This report is not a source-level verified MD5/SHA256 or full MPTrj representation.** It does not prove membership in the MACE-MPA-0 checkpoint training set, which still requires a checkpoint-bound selected frame, preprocessing and energy-label manifest for each training dataset. Do not promote a C0–C4 generalization or calibration claim from this diagnostic.

Neither sAlex results nor any Kaggle run or sealed cohort are modified by the workflow or this PR.
