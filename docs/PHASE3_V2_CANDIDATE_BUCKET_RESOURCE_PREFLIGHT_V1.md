# Phase 3: v2 candidate-bucket resource preflight (0096)

The composition-only v2 candidate index introduced in 0095 prevents near-duplicate false negatives from different original site counts. Such buckets can be larger than historical v1 composition+site-count buckets. This preflight is a local **workload proxy**, not a benchmark or a full-source runtime prediction.

## No-network inspection

    python -m scripts.development.run_mptrj_wbm_source_overlap --preflight --wbm-target-db /path/to/verified-v2-wbm-targets.sqlite

The trusted original WBM SHA256, 256963 material rows, frozen v2 fingerprint/prototype identities and every persisted v2 fingerprint must match before reporting. The metadata-only result contains number of v2 composition buckets, largest bucket (candidate targets per source frame upper bound), mixed-sitecount group count, and separate v1/v2 sum-of-squares pair-comparison proxies. They assume one synthetic source frame per WBM indexed target and must NEVER be extrapolated as actual MPTrj cost, time, source distribution or model-training coverage.

## Separate opt-in bulk-run resource cap

Full original MPTrj source streaming now requires the operator to supply --max-targets-per-composition-bucket followed by a positive integer approved after pilot/resource review. Without it or if the verified largest v2 bucket exceeds the cap, execution fails closed before any original source network transfer. It does not silently drop material candidates. No default numerical limit is asserted as safe.

    python -m scripts.development.run_mptrj_wbm_source_overlap --execute-full-download --wbm-target-db /path/to/verified-v2-wbm-targets.sqlite --max-targets-per-composition-bucket YOUR_REVIEWED_POSITIVE_INTEGER --report /path/to/new-source-only-summary.json

The original source remains unverified in full; real 1MiB pilot is not yet run. The model training selection and eligibility for unseen generalization remain unknown. The historical sAlex v1 positive union 1946 remains only the detected v1 count, not exhaustive v2 near coverage.

## Checkpoint 0097: profile verified original WBM gzip directly

An offline, read-only profiler accepts the canonical original WBM initial-structure JSONL.gz. It SHA256-checks every compressed byte before reading any structure, then validates all 256963 unique original initial structures and computes composition-only v2 and historical v1 site-count bucket statistics.

    python -m scripts.development.profile_wbm_v2_original_source --wbm-gzip /path/to/original-wbm.jsonl.gz --report /path/to/new-v2-profile.json

No network calls, Kaggle, prototype-label computation, training membership declaration, WBM index or MPTrj downloads. Production SHA256 and row count are frozen and cannot be overridden by the CLI. Fixture-only identity overrides can be used by tests. The output is a target-index-only complexity proxy, NOT an execution-time forecast or authorization to run whole-source comparisons.

The real original WBM gzip is currently not available in the user's Library, so the actual 256963-material v2 cost figures remain unmeasured.

## Checkpoint 0098 — manual verified original WBM transfer to a metadata-only v2 profile

After this checkpoint is merged into main, open GitHub Actions / Phase 3 WBM v2 Original Source Profile (Manual) and choose Run workflow on the main branch. Set run_verified_profile=true explicitly; the default false blocks the original download. This opt-in action does not run for PRs, pushes or schedules.

The job downloads only frozen https://figshare.com/ndownloader/files/53161835 (2 GiB and 20 minute transfer bounds), verifies registry MD5 b809f101dd42a745ec2baabe7eb16f11 and source SHA256 98d545172c1ea9060f03f40cace6f8173a4ac06f1ee875ccd963765211519b58 BEFORE parsing, then runs the standalone profile which separately checks full source bytes and 256963 unique WBM structures. It verifies aggregate scientific scope, deletes the downloaded original source even after failure, and uploads ONLY wbm-v2-original-source-profile.json metadata with 7 day retention.

Exact artifact name: phase3-wbm-v2-original-source-profile. Do not copy any WBM original raw gzip into repository commits or GitHub Actions artifacts. A failed job does not establish v2 bucket statistics. Before a real receipt is inspected, the numeric v2 source-level cost remains UNKNOWN.

Even a successful real profile is a WBM bucket workload proxy, not an MPTrj frame frequency, wall-clock estimate, MACE-MPA-0 training membership attestation, authorization for a full sAlex rerun, or certification of unseen generalization.

## Checkpoint 0099: verify a completed manual WBM profile against GitHub's run record

After deliberately dispatching and completing the 0098 manual WBM original-source workflow, download only the small named ZIP artifact. Run the following read-only check with the exact recorded main SHA and workflow run ID:

    python -m scripts.development.review_wbm_v2_github_profile --live-review --run-id YOUR_WORKFLOW_RUN_ID --expected-head-sha EXACT_40_HEX_MAIN_SHA --artifact-zip ./phase3-wbm-v2-original-source-profile.zip

The verifier performs exactly two bounded public REST GETs for that run's metadata and its named artifact list. It never triggers GitHub Actions, downloads the ZIP, requests WBM source bytes or writes output to disk; it prints a compact verified JSON receipt on successful consistency checks.

It demands the expected exact workflow_dispatch job, successful run from main at the requested SHA, a single nonexpired artifact, a matching artifact ZIP SHA256, exactly the original approved JSON metadata member, frozen original WBM SHA256, all 256963 observed rows and plausible v2/v1 arithmetic. It rejects forged training/generalization claims, duplicates and changed ZIPs.

Note: public GitHub API metadata matching an artifact is **not signed provenance** and does not independently recompute the 256963 WBM structures or establish MACE-MPA-0 selected training frames. If the manual job is not yet dispatched, there is no real report to review.
