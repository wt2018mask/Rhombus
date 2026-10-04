# Remote compute contract and capability gate

`rudeus.execution.backend.ComputeBackend` defines `capabilities()`,
`submit(task_bundle, resource_requirements)`, `status(attempt)`, and `retrieve(attempt)`.
This slice includes one provider adapter, `KaggleBackend`. Its only supported
provider operation is a read-only local prerequisite probe. Remote submission,
status and downloads are explicitly **UNSUPPORTED** in this implementation.
There is no demonstrated remote execution or unattended free-capacity claim.

## Evidence and stop condition

On 2026-09-21 the current project environment had no Kaggle CLI, project-venv CLI,
SDK, credential file, access-token file, token environment variable or legacy
username/key environment pair. No authentication, account eligibility, quota,
dependency installation, upload, run or retrieval was verified. CPU/GPU, memory,
time limits, network, persistent storage, artifact transfer and free execution
remain **UNKNOWN**, including when local credentials/tooling are later detected.
The adapter does not install tools, read secret values, submit provider jobs or
fall back to paid infrastructure.

Run the separate probe with:

```powershell
.venv/Scripts/python.exe -B -m rudeus.execution.kaggle_backend
```

It emits JSON and exits 2 to indicate that execution capability was not verified.
Only local prerequisite presence is observed. It never treats credentials as
successful authentication. The
[official Kaggle CLI documentation](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md)
describes notebook push/status/output operations; those descriptions do not prove
this account can run the required mode. A future adapter extension requires an
explicit account-specific free execution probe, immutable provider-run binding,
dependency/bootstrap validation and verifiable downloads. Installing the CLI or
setting credentials alone does not enable submission. No scheduler is introduced.
The existing controlled launcher generates its own attempt ID and records backend
`local` with no provider session. It is not silently relabeled as a remote run:
binding a real provider submission to a producing attempt remains unimplemented.

## Task and attempt records

`build_task_bundle` verifies the existing follow-up TaskSpec and independently
reconstructs its CodeBundle. It inventories the originating evidence closure and
available controlled-execution records with canonical relative paths, exact raw
SHA256 values and sizes. `verify_task_bundle` rebuilds that inventory from verified
evidence and Git objects, rejecting missing, extra or changed entries. The bundle
is a deterministic manifest: archive payloads remain in the evidence store and
code bytes in Git. Remote transfer packaging is not yet implemented.

`BackendAttempt` is an immutable operational record alongside the existing terminal
`ExecutionAttempt`. Each retry uses `new_attempt` for a new nonce-derived ID, without
altering the scientific task ID or full TaskSpec hash. Status snapshots reference
the preceding snapshot hash; `retain_attempt` appends them by content hash using
the existing exclusive append primitive. A provider must acknowledge submission
and supply a run ID before reporting SUBMITTED. The gated Kaggle adapter creates
no accepted attempts or fabricated run IDs.

The operational lifecycle distinguishes CREATED, SUBMITTED, RUNNING, COMPLETED,
PREEMPTED, INTERRUPTED, FAILED, RETRIEVED and DURABLY_INGESTED. Preemption/interruption
are terminal for that attempt; retrying creates another attempt. Infrastructure,
resource, numerical, software, integrity and unsupported-input failures remain
operational classifications. Timeout/network/unknown operational errors map to
INFRASTRUCTURE here without changing existing failure enums or scientific verdicts.

## Verification boundary

`verify_retrieved` consumes an already downloaded archive, checks bytes through
`EvidenceStore.verify`, binds the exact TaskSpec and producing attempt/backend/run,
and verifies the retained CodeBundle/ExecutionManifest/RuntimeRecord. It advances
to RETRIEVED only after verification, and does not mark Git ingestion complete.
`verify_ingested` requires the existing independently checked v2 Git receipt before
advancing to DURABLY_INGESTED. These helpers provide verification, not transport;
they do not trust a remote success flag or implement new scientific calculations.

Provider status and operational snapshots are observations, not attestation.
Actual execution identity remains **NOT_ATTESTED**. Existing H-1/H-2, local runner,
scientific, archive and receipt contracts are unchanged. Tests use a real local
controlled execution wrapped in a clearly synthetic transport envelope to test
the verification boundary; they do not constitute a Kaggle end-to-end test.
