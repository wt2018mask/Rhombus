# Phase 3 — opt-in live GitHub REST diagnostic review v1

Checkpoint 0077 supplies an operator-initiated, read-only verification path for the existing **manually dispatched** 256KiB MPTrj probe. This reviewer does **not** dispatch the workflow, download the Figshare source, use Kaggle, fetch a GitHub archive, or read model checkpoints.

After a separate, explicitly chosen workflow dispatch, inspect the official Actions run ID and exact main SHA. Independently download the small diagnostic ZIP and its JSON receipt from GitHub. Run:

```powershell
python -m scripts.development.review_mptrj_live_github_run --live-review --run-id <run-id> --expected-head-sha <40-character-main-sha> --artifact-zip .\artifact.zip --receipt .\mptrj-first-frame-observation.json
```

Only two pinned HTTPS GET endpoints are allowed under `api.github.com`: `/repos/wt2018mask/Rhombus/actions/runs/{run_id}` and `/repos/wt2018mask/Rhombus/actions/runs/{run_id}/artifacts?name=mptrj-first-frame-observation&per_page=100`. They require HTTP 200, no redirects, JSON, no compression, no duplicate JSON keys and a strict 128KiB maximum each. Authentication tokens are not used or saved. Review requires an explicitly identified successful `workflow_dispatch` on `main` at the expected SHA, exactly one artifact and a matching REST SHA256 for the locally supplied, 64KiB-bounded ZIP. The ZIP must contain one safe JSON member byte-identical to the 16KiB-bounded local receipt, which must pass all previous fail-closed checks.

Live HTTPS GitHub metadata is less susceptible to local snapshot editing than caller-supplied saved JSON, but **it is not a signed GitHub provenance attestation**, nor proof of original MPTrj bytes or MACE-MPA-0 training frame selection. No exposure audit, empirical calibration, generalization or scientific production claim is authorized.

If public API access is rate-limited or returns no matching artifact, fail closed. Never silently replace live verification with user-edited snapshots. Tests mock the two HTTP calls; this checkpoint did not contact GitHub via this new code or run the MPTrj workflow.
