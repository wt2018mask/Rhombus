# Red-team remediation Batch B — engineering review

Base: canonical main `d217c458bfec2d0be095e9f63d7c238fc7af0299`, checkpoint 0119.
Branch: `worker/redteam-remediation-batch-b`. [PR #284](https://github.com/wt2018mask/Rhombus/pull/284) adds only checkpoint 0120.
No historical event, baseline, scientific result, sealed cohort or original
source dataset is changed. No model binary/corpus download, sAlex processing,
model training or Kaggle execution is performed. All original release gates
remain false; no finding is RESOLVED.

## Acceptance states

| Finding | Engineering | Independent acceptance |
| --- | --- | --- |
| RT-P0-01 | IMPLEMENTED: versioned sealed protocol, authenticated ordering and nonce-bound commitment | BLOCKED: no real independent steward, access audit or sealed evaluation |
| RT-P0-02 | IMPLEMENTED: exact-checkpoint, full-source, selected-frame, preprocessing and energy-label manifest verifier | BLOCKED: real independent checkpoint/full-source observations and selected-frame evidence absent |
| RT-P0-03 | IMPLEMENTED: material denominator, conservative outcomes, preregistered precision and conditional Wilson intervals | BLOCKED: independently sampled adequate material cohort and statistical review absent |
| RT-P1-02 | IMPLEMENTED: bounded authenticated shard identity, SQLite/coverage validation and deterministic resume/merge | PARTIAL: synthetic transport only; real Kaggle crash/recovery evidence absent |
| RT-P1-05 | PARTIAL: honest all-outcome accounting, abstention and conditional uncertainty | BLOCKED: independent-model lineage, physical validity, trajectory adequacy and temperature transfer unproved |

Engineering implementation, provider execution, scientific evidence acceptance
and independent qualification are separate states. Every new scientific or
execution authorization output remains false, even with structurally complete
and authentically signed assertions.

## Trust and cryptographic boundary

`rhombus.evidence.receipts.verify_evidence_receipt` verifies canonical JSON
Ed25519 signatures with `cryptography==50.0.2`, an optional `phase3-evidence`
extra and a pinned Fast CI dependency. No signing API, private key, service or
network is part of the implementation. Deterministic signing seeds exist only
in explicitly artificial TEST_ONLY fixtures.

A trusted host supplies `TrustedIssuer` public keys, permitted roles, independent
groups, SYNTHETIC/EXTERNAL scope and accepted log identity outside the artifact.
An artifact cannot provision its own key or elevate a synthetic key to EXTERNAL.
Receipts bind schema, issuer, role, event, subject SHA256, context SHA256, scope,
log, sequence and preceding receipt SHA256. Unknown fields, malformed hashes,
wrong roles/scopes and altered signatures fail closed. JSON is bounded to 8 MiB,
rejects duplicate keys and nonfinite constants, and uses canonical SHA256.

Signatures authenticate an assertion; they do not prove factual honesty,
independence, absence of earlier leaks, complete source coverage, or trusted-log
append-only behavior. Key enrollment, revocation, access controls and external
log verification require independently governed host integration. No production
trust anchors are provisioned by this PR. EXTERNAL-scope unit cases still use
TEST_ONLY synthetic identifiers/keys to exercise policy branches, and are not
external observations or independent scientific evidence.

## B1 — sealed material evaluation

`rhombus.qualification.sealed_evaluation.evaluate_sealed_materials` binds the
model SHA256, evaluation version, protocol, secret steward-generated cohort
nonce and opaque material-token commitment. Protocol/selection rules must be
preregistered. The independent steward signs preregistration and truth release;
a separate independent witness signs prediction commitment. The authenticated
common-log sequence and receipt hash chain require preregistration before
prediction commitment before truth release. The steward/witness must be outside
the development group and independent of each other. Truth must match the
nonce-bound original cohort. Altered prediction/configuration/truth bytes,
duplicate materials, missing rows or optimistic relabeling are rejected.

Only a real external steward may choose real materials, mint high-entropy opaque
tokens/nonce or hold truth. Real identities, nonce and answers stay outside the
public repository and development-agent context. This code selects no cohort
and contains only artificial test identifiers. Public B3/B4 fixtures stay
contaminated diagnostic evidence; their existing blinding checks are untouched.

Material outcome aggregation is preregistered conservative unanimity. FAILED,
INDETERMINATE or UNKNOWN trajectories cannot be relabeled into success. Mixed
conclusive trajectories become INDETERMINATE. Empty trajectories explicitly
represent UNKNOWN abstention. POSITIVE, NEGATIVE, BORDERLINE, UNKNOWN, FAILED,
INDETERMINATE and NONDIFFUSIVE are separately retained, including all materials
in the denominator. Repeated trajectories never increase material sample size.
The diagnostic metric counts correct POSITIVE/NEGATIVE/BORDERLINE material
predictions across all preregistered materials; other outcomes are not silently
excluded or converted to negatives. Truth-class counts are also reported.

The precision rule specifies minimum independent materials, confidence level,
maximum half width and a rationale. It rejects a minimum smaller than the
worst-case Wilson precision bound. Wilson is an approximate binomial interval,
conditional on a preregistered IID-material sampling model; it is not an exact
coverage guarantee or a power study. For dependent/unverified material sampling,
no interval is emitted and precision remains unsatisfied. Merely reaching a
synthetic precision target never authorizes performance/generalization claims.
Correlations within a material are handled by conservative aggregation, not
pseudo-replication. Real sample acquisition, population validity, stratification
and power review remain independent external requirements.

Optional training-overlap evidence must use the exact protocol/model and
steward-canonical token scheme, with a trusted independent lineage-auditor
signature. Observed overlap is rejected; absent evidence stays explicitly
UNATTESTED. Model bias, exposure, defect/rare-event adequacy and transfer from
550 K to room temperature cannot be cleared by these summaries.

## B2 — checkpoint-bound training lineage

`rhombus.domain.training_manifest.verify_training_lineage_manifest` is additive;
the old metadata checklist stays a checklist, never evidence authentication.
The strict v1 package fixes the official medium asset/release and publisher
revision, and retains reported checkpoint SHA256
`75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`.
A separate checkpoint-observer receipt authenticates a declared full-file
independent rehash, distinct from publisher-reported metadata. Both MPTrj and
sAlex need full original-source observations; a 1 MiB prefix is rejected as
complete source identity.

Actual bounded JSON artifact bytes must match their SHA256 and exact checkpoint,
source and dataset bindings. The complete selected-frame list has unique frame
and source-record identities and an exact count. Preprocessing and energy-label
artifacts are separately bound; labels must cover exactly the selected frames
with explicit fields/units. Publisher, independent source observer and separate
lineage auditor must authenticate the source-selection package. Host-approved
preprocessing/label digests must match the package; without them audit readiness
remains blocked, and unsupported rule bindings fail closed. Material identifiers
must use a steward-reviewed canonical identity scheme before overlap analysis.

`audit_verified_training_overlap` reruns the full verifier and requires external
policy plus approved rules; loose booleans cannot authorize it. Its outputs are
an overlap diagnostic and provenance, not a scientific exposure/generalization
verdict. Exact training-frame scientific attestation stays false pending the
separate independent membership audit.

Two bounded upstream text references were reread at pinned revision
`0f5de4b15d9c7f86d4e50996533ecf6c0f48a51b`: the golden foundation artifact source
(14,942 bytes) and golden reference JSON (14,080 bytes), both containing the
reported digest. Their byte hashes/URLs are recorded in the new engineering
evidence. No 79,462,305-byte model asset or complete corpus was fetched. A
future binary acquisition requires explicit resource/provenance preflight;
selected-frame lists and preprocessing/label provenance require the publisher
and independent reviewers. MPTrj prefix and historical sAlex receipts are not
promoted to complete checkpoint-selected training membership.

## B3 — persisted shard recovery

`rhombus.domain.durable_shards.plan_durable_shard_resume` reuses the existing
canonical ordinal partition plan and checks a strict immutable shard identity:
source/plan/protocol hashes, ordinal/count, exact range, row count, artifact
length/SHA256, record commitment, storage epoch/namespace and completion/
persistence states. Independently provisioned source-observer and storage-
receiver receipts authenticate the identity, with persistence after source audit.
A stale epoch, wrong receiver, duplicated/conflicting shard or replayed receipt
fails. Merely finalized LOCAL_ONLY shards remain pending; unfinalized shards
cannot count as completed.

Retrieved artifacts are selected by a trusted host digest-to-Path map within
an existing trusted root. No path from a remote manifest is executed. SQLite
bytes are rehashed, length checked and queried from an in-memory snapshot of
those exact bytes, preventing row/hash mismatches during file mutation. Checks
include SQLite integrity, exact tables/metadata, source/protocol consistency,
contiguous expected ordinals, unique record IDs across all shards and matching
source-record commitments. WAL/SHM, symlinks, missing/corrupt files and traversal
are rejected. Current verification budgets: 16 MiB/file, 64 MiB total retrieved
bytes, 100,000 total rows. Larger use needs a reviewed resource-bound integration.

Resume returns only missing ranges in original deterministic order. Reordered
input or concurrent read-only verification produces identical results, with no
double counting. It grants no execution. `verify_completed_shard_merge` requires
all authenticated completed shards and a byte-verified SQLite merge matching
all retained rows; complete coverage alone never implies merged output validity.
Existing no-overwrite staging and multipart byte verification are reused and
fault-tested. The old membership verifier now correctly accepts pathlib
subclasses and rejects duplicate dataset/record IDs; both gaps were reproduced.

The existing two-job GitHub synthetic workflow is retained, with immutable
Actions SHAs and seven-day GitHub artifact retention. Before upload it invokes
Batch A's unchanged scanner with an exact one-file allowlist. The public artifact
is readable JSON containing exactly eight literal artificial rows and a local
SQLite digest. SQLite/parts remain local, without encoded opaque bytes or secret
payloads. The separate receiver job validates exact fixed JSON, reconstructs
SQLite locally and tests its parts/rows. This proves synthetic JSON transport,
not remote SQLite byte durability, real source lineage or Kaggle crash recovery.
The prior opaque synthetic upload is removed rather than bypassing the scanner.

Authorized future Kaggle integration needs a stable finalized producer,
independent original-source record evidence, independently governed receiver
keys/logs, immutable persistence receipts, read-after-write retrieval, epoch
control and two small real-source crash/restart demonstrations. Production
submissions remain disabled; this PR provides no tokens or authorization.

## Lossless continuity and self-review

The checkpoint 0118 snapshot/descriptor remain unchanged. CURRENT retains every
0119 reference, historical code and blocker through the existing resolver.
`prior_checkpoint119_state` points to a byte-for-byte archive of main's compact
0119 CURRENT, retaining its complete integration/frontier metadata without
replaying history. Checkpoint 0120 is the only new event; the handoff is generated
from the complete effective state. CI count assertions now derive the exact
baseline+delta union so valid additive future checkpoints are supported, while
all 214 baseline reference values and 150 codes are still explicitly tested.

Adversarial self-review retained these limitations: trusted signatures cannot
prove a dishonest assertion true; external enrollment/revocation/access/log
audits are not supplied; Wilson assumptions and conservative aggregation are
preregistered diagnostic contracts, not empirical calibration; source-selected
frames and real provider persistence remain unverified. No synthetic pass is
promoted into scientific, operational production, or generalization authority.
All original red-team register release gates, Batch A scanner/submission guards
and numerical protections are preserved. Relevant regressions and exact-HEAD
GitHub results are recorded in the PR and new engineering evidence.

## Observed local verification

- Batch B + affected SQLite and synthetic transport: **102 passed**.
- Affected Batch A, legacy lineage/recovery/blinding and continuity regression selection: **184 passed**.
- Final continuity/adversarial selection: **31 passed**.
- Full R2 Fast CI command after all implementation changes: **889 passed**, eight existing warnings.
- Compile, fixed synthetic JSON scanner/receiver CLI, and nine protected guard/register/baseline byte comparisons passed.

Effective continuity retains all 221 prior references and 158 prior codes, and
adds seven references and three codes: **228 references / 161 codes**. CURRENT
is 3,349 bytes; checkpoint 0120 is 565 bytes. The historical-state archive is
bound to exact base CURRENT bytes by PR checks and protected against changes.
