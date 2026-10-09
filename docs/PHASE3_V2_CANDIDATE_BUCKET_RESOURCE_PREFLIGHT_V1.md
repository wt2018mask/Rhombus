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

## Checkpoint 0100: offline replay after GitHub artifact expiry

**Only after** a real, operator-dispatched 0098 WBM profiling run has succeeded, save the exact small `phase3-wbm-v2-original-source-profile.zip` locally. Run the 0099 live reviewer with the explicit successful run ID and exact `main` commit SHA; preserve its JSON stdout as `wbm-v2-github-review-receipt.json` without modification (for example redirect stdout to a new file). Never save the large raw source gzip as an evidence archive.

Once the two small files are safely preserved, the following offline command has **zero network traffic**, does not require a live GitHub artifact and does not write or modify either input:

    python -m scripts.development.replay_wbm_v2_archived_profile --review-receipt ./wbm-v2-github-review-receipt.json --artifact-zip ./phase3-wbm-v2-original-source-profile.zip --run-id YOUR_WORKFLOW_RUN_ID --expected-head-sha EXACT_40_HEX_MAIN_SHA

The replay refuses altered archives, swapped run/commit IDs, changed bucket metrics, noncanonical source identity, unsafe ZIP entries or extra claimed scientific authority. It outputs a machine-readable JSON record binding the exact archived receipt bytes, full ZIP hash and original report hash. Save these three small evidence files with their SHA256 and immutable run details if preservation is authorized. GitHub Action artifacts expire after seven days; this replay only rechecks **the two user-supplied local artifacts** and cannot independently verify whether the archived receipt truly came from GitHub, certify original WBM measurement, or authorize whole-MPTrj source requests.

## Checkpoint 0101: same-open-file source hashing and structural profiling

Earlier the 0097 standalone profiler hashed a gzip file by pathname, then reopened that name for 256963 structure parses. In a mutable directory, this left a hash-to-parse path replacement window. The profiler now opens the source once, retains the file descriptor throughout **initial complete gzip SHA256 → bounded JSONL parsing → second complete gzip SHA256**, and checks that the final source path still denotes the opened regular file. Source replacement, symlink substitution, changed file size, or persistent in-place byte modification fails closed before any output report is written.

This is a provenance-consistency guard, **not an immutable filesystem guarantee against an adversary who can overwrite and restore bytes while reading**, and not independent authorization for MACE-MPA-0 training-frame claims. Existing original WBM SHA256/MD5 identities and v2 composition-only candidate semantics remain unchanged. No new source network transfer, Kaggle computation or full MPTrj download is performed by this development PR.

## Checkpoint 0102: enforce the 20-minute original transfer budget across retries

The manual profile workflow used to pass `curl --max-time 1200 --retry 2` directly. Since `--max-time` bounds an individual curl attempt rather than an entire series of attempts, repeated attempts could exceed the intended 20-minute download budget. The manual-only workflow now invokes `timeout --signal=KILL 1200s curl ...`; GNU `timeout` bounds the entire curl process including retries, retry delays and redirects.

If the outer timer expires, the download command fails. Normal `set -euo pipefail` behavior prevents hashing/parsing/upload steps, and the existing `if: always()` cleanup deletes any partially downloaded gzip. The existing absolute 2 GiB download cap, pinned source MD5/SHA256, workflow 40-minute total timeout and default-deny operator input are unchanged. The original WBM download is **not** activated by this code change, pull-request CI or any scheduler.

## Checkpoint 0103: reconstruct bucket-cost proxies from small metadata distributions

The verified original WBM direct profiler now emits **report schema v2** (`rhombus-phase3-original-wbm-v2-direct-candidate-profile-v2`). Two compact maps named `v2_composition_bucket_size_histogram` and `v1_composition_sitecount_subbucket_size_histogram` contain only integer bucket **sizes** as decimal-string keys and counts of buckets with each size; neither material IDs, actual composition formulas nor raw structures are included. Histograms are aggregated from the existing 256963-row pass and do not create an SQLite index or initiate a transfer.

For each histogram, the manual job's preupload verifier and opt-in GitHub run/ZIP review now independently reconstruct: bucket count = sum of histogram frequencies; target count = sum of size × frequency; largest bucket = maximum size; and candidate-comparison proxy = sum of size² × frequency. The v2 and v1 results must exactly match the stated source-verified report metrics and both histograms must individually account for **256963** initial WBM structures. No histogram entry may have an invalid or noncanonical integer, and all calculations are bounded by the frozen row count. The archived ZIP replay uses the same validator. This makes the saved source-only workload aggregates falsifiable without retaining sensitive/bulky original structure records.

The source-profile metadata schema advanced from v1 to v2 **before any genuine manual WBM source profile was observed**. Existing 0099 GitHub review receipt and 0100 offline replay schema versions are unchanged, while the reviewer now requires the stricter v2 report embedded in the saved ZIP. The result remains an original-WBM **index-only resource proxy**, not a real MPTrj frame distribution, full source runtime benchmark, training-selection attestation or model-unseen classification. Original source download still requires the operator's explicit default-deny workflow input.

## Checkpoint 0104: artifact ZIP hash and report JSON must use identical bytes

The 0099 live manual-run ZIP reviewer and the 0100 offline replay now use a single immutable **in-memory snapshot** of the caller-supplied bounded metadata-only ZIP. The verifier checks the ZIP's expected SHA256 and then parses precisely these same bytes by opening `ZipFile(io.BytesIO(zip_bytes))`. It no longer reads an archive pathname for its hash and reopens that pathname to parse a different possible ZIP.

A local pathname swap to different but plausible metadata or to corrupt archive bytes after the single input read cannot change the JSON attributed to the verified ZIP digest. Two no-network regression fixtures exercise both cases. Existing restrictions remain in force: one approved JSON member, 512 KiB maximum ZIP, 64 KiB maximum metadata report, frozen WBM source SHA256, 256963 target rows, current report schema v2 histograms, and fail-closed science claims. This is a **supplied-artifact consistency check**, not an authenticated GitHub signature, independent recomputation of WBM structures, or permission to infer MACE-MPA-0 training membership or MPTrj runtime.

## Checkpoint 0108 — bound the *actual* original-profile artifact ZIP read

The original-WBM-v2 GitHub evidence reviewer formerly checked a local ZIP
size of at most 512 KiB using `stat()`, then unconditionally allocated the
entire path with `Path.read_bytes()`. A concurrent swap/growth after the
size preflight could exceed this memory budget before a SHA256 mismatch was
raised. The verifier now reads at most `MAX_ZIP_BYTES + 1` from the actual
opened ZIP and refuses all snapshots outside the positive 512 KiB bound.
Afterward both digest verification and ZIP member/JSON parsing consume that
**same bounded byte snapshot**. Existing archive-path-swap identity regressions
remain enforced, along with new stat/open growth and unbounded-read regression
tests. The protection is against resource-bound bypass; it does not provide
authenticated GitHub signing or independent source recomputation, and does
not run the original WBM profile by itself.
