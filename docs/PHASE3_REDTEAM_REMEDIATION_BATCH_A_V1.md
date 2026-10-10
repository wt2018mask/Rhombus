# Red-team remediation Batch A — engineering review

Baseline: canonical main `e565e827119be40b23c21060bd59c873b895abaf`, checkpoint
0118. Branch: `worker/redteam-remediation-batch-a`. Checkpoint 0119 is the only
new event. [PR #283](https://github.com/wt2018mask/Rhombus/pull/283) targets
main. Its actual number is bound in CURRENT and the new event; the generated
handoff and exact PR continuity check must match. No merge is authorized
by this report. Prior CURRENT remains recoverable from the exact baseline Git
blob recorded in [engineering evidence](../data/development/phase3_redteam_batch_a_evidence_v1.json).

All scientific NO-GO gates in the original remediation register remain false.
No original scientific results, historical checkpoint events, held-out truth
or source datasets were changed. No Kaggle workload or full-source download
was performed. No finding is marked RESOLVED; independent acceptance remains
pending for every engineering change below.

| Finding | Engineering status | Behavior and outstanding evidence |
| --- | --- | --- |
| RT-P1-03 | IMPLEMENTED | Recursive bounded ZIP/gzip text scan; fail closed on zstd/SQLite, malformed/encrypted/unknown/oversized artifacts. Existing science archive upload is intentionally blocked until a separate safe export contract exists. |
| RT-P1-04 | PARTIAL | Automatic push launcher disarmed and removed. Controller admits only exact historical resume/retrieve; new submit and dataset creation code removed. No trusted atomic cross-run consumption ledger exists, so new execution remains disabled. |
| RT-P2-01 | IMPLEMENTED | Reject duplicate/near-identical T, rank-deficient or ill-conditioned dimensionless inverse-T design, invalid input and nonfinite/zero prefactor. Established valid fits retained. |
| RT-P2-02 | IMPLEMENTED | Require signed nonzero Integral charge; reject bool, fractional/integral float and strings. Preserve z-squared conductivity and estimate label. |
| RT-P2-03 | PARTIAL | Immutable Actions in five affected workflows; SHA256-locked controller dependencies; source/constraint/package/runtime/seed/explicit artifact provenance. Full scientific and hardware reproducibility remains unverified. |

## Confidentiality boundary

The export scanner permits UTF-8 text formats and recursively inspects ZIP/gzip
with limits: 16 MiB per read/file, 32 MiB aggregate input and expanded bytes,
128 tree/archive entries, nesting depth 3, compression ratio 100. It scans
file paths, ZIP metadata bytes and expanded text for credential patterns and
known injected credential values. It rejects unknown formats, binary text,
symlinks, encrypted/nonregular ZIP entries, duplicate members, unsafe member
paths and malformed archives. `--allow` provides an optional complete set of
expected relative file paths; unexpected or missing files fail.

There is no hash-based bypass. A valid science digest never clears opaque
content. Multipart zstd and SQLite exports are denied entirely, including
SQLite TEXT/BLOB fixtures and split archive parts. The scanner does not
promise detection of arbitrary encoding or steganography. Its supported
patterns and stable private input directory are explicit prerequisites; it
is not an independent security audit. Concurrent mutation between scanning
and a separate uploader remains outside the current workflow guarantee.

## Compute boundary

The launch request is disarmed while its historical dispatch facts and
scientific contracts are retained. Merely setting KAGGLE_PRODUCTION_ENABLED,
replaying a push, retrying the workflow or running concurrent controllers
cannot enable a new submission in the modified workflows. An explicit first
controller guard also denies submit before any credentials are loaded.

The only accepted recovery identity is full commit
`643b8a260b6fcff78bb02f3a63f348c29fd91317`; retrieved evidence must match that
full commit and its source/summary/archive hashes. The historical short slug
only locates the provider job and is not accepted as provenance on its own.
Concurrency serialization and artifact receipts are not atomic consumption
proof. Re-enabling new execution requires a new independently reviewed,
durable atomic consumption mechanism, explicit fresh authorization and the
existing scientific/resource/recovery gates. No such authorization is implied
by these unit tests. Old workflow versions in GitHub history cannot be revoked
by a code PR; administrators must keep production credentials/environment
approval protected and prevent historical submit reruns.

## Numerical boundary

Temperature distinction uses relative tolerance 1e-6 and absolute tolerance
1e-6 K. The dimensionless design `[inverse_T/max(inverse_T), 1]` must have rank
2 and condition number at most 1e6. These documented numerical thresholds are
not measurement precision or scientific calibration. Invalid designs raise
ValueError before availability or SUPPORTED_BY_DATA is returned. Two-point
valid fits remain supported numerically, without inventing uncertainty.

Valid positive and negative integer charges, including NumPy integers, retain
the Nernst–Einstein formula. Bool, float, string, zero and nonfinite types are
rejected before coercion. Overflow/nonfinite conductivity is rejected.

## Reproducibility boundary

The five scoped workflows are Fast CI, Security Contract, Development
Continuity, sAlex Launch and sAlex Full Run. Official HTTPS Git tag reads
established checkout v4.3.1 SHA `34e114876b0b11c390a56381ad16ebd13914f8d5`,
setup-python v5 SHA `a26af69be951a213d495a4c3e4e4022e16d87065`, and
upload-artifact v4 SHA `ea165f8d65b6e75b540449e92b4886f43607fa02`.
The controller installs 34 exact dependencies with `--require-hashes` from
trusted dispatch code, separately from the historical science checkout.
Kaggle 2.2.4 and zstandard 0.25.0 were installed and their CLI/import surface
checked locally without a remote workload. Refresh the lock deliberately
using its `.in` file and the recorded generation command.

The additive runtime collector records actual source commit, dirty-source
flag, package versions, constraint-file hash, observed CPU/platform and
Python precision, supplied seed and supplied local artifact-byte hashes. It
never reads credential files, dumps environment variables or exports package
URLs. No seed is fabricated. The deterministic sAlex streaming receipt gains
the environment inventory; original receipts are not retroactively modified.

Other workflows, runner/container images, the complete scientific transitive
dependency graph, GPU/BLAS/model precision and independent numerical
replication remain unverified. Existing scientific paths already record seeds
and input/trajectory hashes; model/data family declarations remain distinct
from independently verified exact training membership. No exact original
model/source data or Kaggle hardware was available for this task. Both
bitwise and independent reproduction flags remain false.

## Verification and review

- Before fixes: transport regressions 12 failed/21 passed; artifact regressions
  13 failed/4 passed; new Kaggle policy contracts 11 failed; new provenance/pin
  contracts 7 failed. The additional filename regression also failed before
  its follow-up correction.
- Final local R2 Fast CI: **761 passed**, zero failures/skips, 8 existing
  ASE/fixture warnings. This executes the current workflow's exact pytest
  command, including all **73 new** Batch A cases.
- Focused transport/security/recovery/provenance contracts: 147 passed before
  three additional artifact cases. Final scanner subset: 29 passed. All
  additions also passed in the final Fast CI.
- Controller hash-locked install: 34 packages in a separate Python 3.11
  environment; CLI help passed. Compile checks passed.
- Development Continuity validation follows the one-event, compact CURRENT
  update, including actual PR #283 binding.
- GitHub PR #283 was created successfully after initial proxy CONNECT denial.
  Initial-head Development Continuity failed because PR was null; actual #283
  binding is corrected in the next commit. Final-head CI must pass before merge.
  Wave 2 was not run or dispatched locally; normal PR CI remains required.

The api.github.com domain addition was saved in the cloud environment draft;
saving does not apply runtime networking or publish the environment. Review
and save the environment settings and publish as required by the platform.
Repository administrators still need to attest effective branch protection,
required CI/reviews and production environment approval. Independent steward,
model lineage and real source-shard recovery work remain prerequisites for
any scientific qualification or new long computation.
