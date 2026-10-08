# Phase 3 — MPTrj manual run metadata consistency review (v1)

This optional **offline** operator tool reviews saved GitHub Actions REST run and artifact-list metadata alongside the strict 256KiB diagnostic receipt introduced in checkpoint 0073. It does not dispatch a workflow, make network requests, fetch original MPTrj bytes, or change Kaggle/sAlex.

## Operator review after an explicitly authorized manual execution

Only after the separate 256KiB `workflow_dispatch` run has completed, use GitHub's official Actions run page to determine the actual run ID and head commit SHA. Save independently fetched REST JSON from:

- `GET /repos/wt2018mask/Rhombus/actions/runs/{run_id}`
- `GET /repos/wt2018mask/Rhombus/actions/runs/{run_id}/artifacts`

Obtain the **actual diagnostic JSON** from the named `mptrj-first-frame-observation` artifact, after independently checking the GitHub Actions run and artifact provenance. Example:

```powershell
python -m scripts.development.review_mptrj_manual_run --run-json .\run.json --artifacts-json .\artifacts.json --receipt .\mptrj-first-frame-observation.json --expected-head-sha <reviewed-40-character-main-commit>
```

The checker enforces a successful `workflow_dispatch` from `main`, the exact repository/workflow path, a caller-reviewed commit SHA, a single named non-expired small artifact linked to that same run and SHA, and the earlier strict receipt schema. Files are bounded, symlinks and duplicate JSON keys are rejected, and the tool is read-only.

**Important trust boundary:** saved JSON files are caller-controlled. Consistency of JSON values is **not** authenticated GitHub execution origin. Even a successful result does not prove that the downloaded receipt was actually contained in the referenced artifact; independently compare the live GitHub API and artifact archive. Neither the prefix SHA256 nor the run metadata attests the full 12.2GB source, the MACE-MPA-0 training selection, exposure audit eligibility, empirical calibration, or unseen generalization. No scientific gate opens.

If GitHub supplies a different metadata shape or a failed/incomplete run, fail closed and inspect the actual live API rather than weakening these checks.


## Optional stronger local ZIP-to-receipt check (checkpoint 0075)

Pass `--artifact-zip <downloaded-artifact.zip>` when running the reviewer to require safe single-member ZIP inspection, exact local receipt byte equality and strict receipt schema checks. This is *local copy equivalence*, **not** authenticated GitHub run/artifact origin. See [diagnostic ZIP guide](PHASE3_MPTRJ_DIAGNOSTIC_ARTIFACT_ZIP_V1.md).
