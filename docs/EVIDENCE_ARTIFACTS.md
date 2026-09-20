# ClaimAssessment evidence archives

The archive layer converts an existing scientific record into a verified,
append-only archive and supports Git ingestion receipts. Explicit follow-up
generation and the narrow local execution path are described below. Existing
scientific contracts and historical evidence are unchanged.

## Executable workflow

```powershell
.venv/Scripts/python.exe -B -m rudeus.science.evidence publish request.json --source-root . --store-root data/batches/evidence
.venv/Scripts/python.exe -B -m rudeus.science.evidence verify EVIDENCE_SHA256 --store-root data/batches/evidence
# Commit the archive through the normal explicit Git batch workflow first.
.venv/Scripts/python.exe -B -m rudeus.science.evidence acknowledge-git EVIDENCE_SHA256 --store-root data/batches/evidence --git-root . --revision HEAD
```

`EVIDENCE_SHA256` is the `evidence_hash` returned by publication. The Python API is
`EvidenceStore.publish(request, source_root=...)`, `verify(hash)` and
`acknowledge_git(hash, git_root=..., revision=...)`.

The request is JSON containing:

- `task`: the existing serialized TaskSpec for the scientific computation.
- `attempts`: serialized ExecutionAttempts for every source-producing execution.
  The scientific producer must match `task.task_id`. Each attempt's
  `output_manifest` maps output names to **ArtifactManifest content hashes**.
  The producing attempt must also carry `task_content_hash = TaskSpec.content_hash`,
  the existing canonical SHA256 of the entire TaskSpec, including provenance and
  operational fields. `task_id` retains its existing scientific identity meaning.
  Missing or mismatched full-content bindings fail with INTEGRITY; they are never
  inferred from `task_id`. Legacy upstream attempts without their TaskSpecs remain
  readable, but cannot serve as the producer of the submitted TaskSpec. Existing
  unbound archives are not rewritten or grandfathered into verified publication.
- `manifests`: serialized ArtifactManifests for the record and its complete
  ancestry. Locators are relative to `source-root`; escaping that root is rejected.
- `record_manifest`: the ArtifactManifest content hash for the scientific record.
- `checks`: optional original claim-engine evaluation context; defaults to empty.

The record is either the four-field `p3_scientific_record` object or its complete
P3 result wrapper. It contains ClaimSpec, Observation (possibly null), Uncertainty
and ClaimAssessment. The record manifest's parents must equal the task's input
artifact hashes. Sources must include the protocol and ClaimSpec provenance
identity, all observation/supporting/conflicting artifacts, and their ancestors.
For the existing P3 wrapper, provenance includes the canonical JSON object
`{"p2": p2_payload, "p25": p25_payload}`; its hash is the default ClaimSpec
provenance identity. P3's protocol, input-result and scientific-record bindings
are checked. No missing attempt, manifest or scientific input is fabricated.

Only completed successful producers and fully available outputs are supported in
this slice. Legacy data without execution provenance cannot be silently adopted.
Upstream TaskSpecs are not inferred: their recorded task IDs remain in the archived
attempts. Existing execution metadata is retained verbatim, not authenticated as
a new scientific qualification or an independent attestation of physical validity.

## Verification and preservation

Every source is checked against its raw SHA256, size and logical hash. Supported
canonicalizations are existing `canonical-json-v1` and `p2-traj-v1`. Trajectory
verification uses the existing loader and canonical trajectory hash on a snapshot
of the exact source bytes. NPZ container hashes never replace logical identities.
Caller-supplied verification labels are not trusted.

The existing claim engine replays the assessment; all assessment fields must
match. Observation/uncertainty bindings and provenance closure are required.
The archive preserves the original record, unresolved requirements, uncertainty,
checks, manifests and execution metadata. UNKNOWN and INDETERMINATE are retained.
The publisher neither recalculates observables nor upgrades any verdict.

Optional qualified records require a separately trusted `qualification_registry`
supplied to the Python API on publication and verification, plus the corresponding
certificate/evidence artifacts. Registry entries cannot be supplied by the request
JSON. No production qualification registry or new scientific criterion is provided.

## Storage and durability

Sources and the canonical archive JSON are copied into `blobs/<raw-sha256>`.
The archive's deterministic ArtifactManifest is published last at
`evidence/<logical-sha256>.json`. Metadata ordering is canonicalized; repeated
identical publication is idempotent. Different records or execution provenance
produce separately addressable archives. There is no mutable latest-result index,
conflict winner or automatic scientific conflict resolution.

Files are flushed and published with exclusive atomic hard links. Existing files
are never replaced, including corrupted ones. Interrupted publication can leave
unreferenced blobs; it cannot confer a completed archive or Git receipt. Unsupported
filesystems fail explicitly. Every verification rereads all retained source bytes.

Publication means `VERIFIED_LOCAL`, not `DURABLY_INGESTED`. Git acknowledgement
checks every manifest, archive and source blob against one existing commit before
appending a content-addressed receipt under `receipts/`. A fresh checkout containing
that commit can verify the archive without the original source directory.
The receipt itself belongs in the next Git batch commit. No commit or push is
performed automatically, and remote replication remains `NOT_ATTESTED`.

Artifact success remains separate from scientific qualification, which for the
current P3 workflow is **UNKNOWN / NEEDS EVIDENCE**.

## Explicit follow-up requests

The optional evidence-publication request field `followups` is a list of
serialized `rudeus.science.followups.FollowupRequest` records. Each contains
`scientific_record_hash`, `assessment_hash`, a nonempty `reason`, and `task`
(a complete existing TaskSpec, or null when instructions remain unresolved).
The scientific owner must explicitly supply this annotation; verdicts alone
never authorize follow-ups. Publication verifies the assessment/record bindings
and archives the requests without changing any scientific assessment. Existing
archives have no follow-up permission and remain unchanged. Adding an annotation
requires a new append-only archive, not editing the original archive.

```powershell
.venv/Scripts/python.exe -B -m rudeus.science.followups EVIDENCE_SHA256 --store-root data/batches/evidence --output followups.json
```

The CLI and `generate_followups(store, evidence_hash)` reverify the entire archive
before generating anything. This slice supports explicit P3 analysis tasks only.
The supplied P3Protocol config must match its protocol hash and explicitly state
lags, fit window and the supported reference frame. Inputs must already be
verified artifacts in the archive, and code_revision must be a full Git commit
hash. Missing instructions or unsupported definitions return an unresolved result
with no task; corrupt evidence raises an execution integrity error.

Generation preserves supplied scientific parameters and adds the source task as
a dependency. The existing immutable TaskSpec gains an optional `provenance`
mapping containing evidence, request, scientific-record and assessment hashes,
plus the original claim scope. Missing structure/phase identifiers remain absent;
they are not inferred. Provenance is excluded from the existing scientific task
ID, just as operational resource/retry metadata already is. Equivalent requested
computations can therefore share a task ID across separately addressable evidence
archives or attempts. Config, protocol, inputs, dependencies, code and requested
seed/replica/temperature retain their existing identity semantics. Absent
provenance is omitted during serialization, preserving old TaskSpec bytes/hashes.

The output keeps source verdict and qualification unchanged and separates
`GENERATED` bookkeeping status from scientific outcomes. Output publication is
append-only and idempotent. This command does not execute, schedule, retry, commit
or push any generated task.

## One local execution and verified ingestion

Save one `tasks[i].task` object from the follow-up output as `task.json`:

```powershell
.venv/Scripts/python.exe -B -m rudeus.execution.local task.json --store-root data/batches/evidence
```

The API is `execute_local(task: TaskSpec, store: EvidenceStore)`. It reverifies the
originating archive and requires an exact match to an explicitly generated task.
The task's full `code_revision` must be the checked-out HEAD, with unchanged
tracked computation sources. The runner's own source hash is recorded separately
to support testing before committing it. No code checkout or task rewriting occurs.

This operation supports one P3 self-diffusion scientific-record output using the
originating ClaimSpec and identical protocol. Inputs must contain its protocol,
P2/P2.5 provenance and verified trajectory, with complete producer-output ancestry.
The sole dependency must be the originating task. The trajectory binding must be
a safe relative path; archived bytes are restored in a temporary directory without
changing historical payloads. New protocols, additional assessment checks/conflicts,
collective analysis, replica execution, mismatched temperature or an unbound seed
are rejected. Resampling uses only the existing explicit protocol seed.

The existing P3 calculation runs on these verified snapshots. Only its canonical
four-field scientific record becomes the output artifact; wall-clock timestamps
remain in the real ExecutionAttempt. Python/package versions, platform, CPU
information, thread settings, code identity and measured runtime are recorded.
Repeated computations retain the same logical/raw scientific output hashes while
individual attempts and their evidence archives remain separately addressable.

Output raw/logical hashes and size are verified, then EvidenceStore verifies the
complete provenance and replays the assessment before publication. The returned
artifact manifest points to its producing attempt; the archived immutable TaskSpec
retains originating evidence, assessment and request references. `tasks/` and
`attempts/` contain append-only copies of the existing contracts. Failed execution
or verification records a classified FAILED attempt, exposes no scientific verdict,
and never reports verified ingestion. Storage errors that prevent persisting an
attempt are propagated explicitly.

Success returns `VERIFIED_LOCAL` and the scientific verdict separately. It does
not qualify science, update candidate states, schedule, retry, commit or push.
Git durability still requires the separate archive commit/receipt workflow above.

## Local evidence to a Git durability receipt

Execution `COMPLETED`, artifact `VERIFIED_LOCAL`, and Git `DURABLY_INGESTED` are
separate results. After explicitly committing the local output's archive and its
originating evidence archives, use the execution result's `evidence_hash`:

```powershell
.venv/Scripts/python.exe -B -m rudeus.science.evidence acknowledge-git EVIDENCE_SHA256 --store-root data/batches/evidence --git-root . --revision HEAD
.venv/Scripts/python.exe -B -m rudeus.science.evidence verify-git-receipt RECEIPT_SHA256 --store-root data/batches/evidence --git-root .
```

`RECEIPT_SHA256` is the canonical content hash used in `receipts/<hash>.json`.
The existing acknowledgement now records the commit and tree, repository-relative
store path, output logical/manifest identities, producing attempt, TaskSpec ID,
input parents and originating task provenance. The archived task and attempt are
already embedded in the evidence; standalone `tasks/` and `attempts/` copies are
not required for recovery. Originating evidence is also verified and required in
the same commit, including its source blobs and explicit follow-up binding.

`verify_git_receipt(hash, git_root=...)` reads a newly generated receipt, checks
its content identity, independently rebuilds its proof and compares every required
file against the recorded commit. Missing commits, staged-only evidence, changed
required files, forged references and incomplete originating evidence fail with
INTEGRITY. Unrelated working edits are allowed. Verification works after HEAD moves
and in a fresh clone; it does not depend on a mutable branch name or remote URL.

Regeneration for the same verified state is deterministic and append-only. Existing
older receipts remain untouched; regenerate an acknowledgement to obtain the
expanded verifiable receipt. The receipt itself needs a subsequent commit for
checkout recovery and is not included in its own proof. Local Git durability does
not attest a push, replication, or scientific qualification; UNKNOWN/INDETERMINATE
remain unchanged. Neither receipt command commits or pushes.
