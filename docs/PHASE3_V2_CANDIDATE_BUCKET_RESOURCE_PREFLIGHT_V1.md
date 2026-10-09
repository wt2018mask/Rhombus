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
