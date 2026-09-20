# ClaimAssessment evidence archives

Implemented slice: an existing scientific record → verified, append-only archive
→ Git ingestion receipt. No scientific calculation, follow-up, scheduling or
backend execution is added. Existing contracts and historical evidence are unchanged.

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
