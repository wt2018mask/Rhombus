# Phase 3 Kaggle sAlex/WBM — terminal-state and recovery playbook (v1)

**Status:** design and operations only; NOT an authorized production change.
**Frozen in-flight Kaggle commit:** `643b8a260b6fcff78bb02f3a63f348c29fd91317`.
**Kernel identity:** `wt2018mask/rhombus-salexcpu-643b8a260b6f`.
**Workflow:** `.github/workflows/r2-phase3-salex-kaggle-full-run.yml`.

## Noninterference contract

- Never push a new kernel, rerun an old submit job, cancel the Kaggle job, or mutate the frozen inputs merely to improve observability.
- This document does not change the in-flight kernel. A new GitHub commit cannot patch its executed Python source.
- Do not change the frozen WBM/sAlex SHA256, protocol identifiers, expected counts, or scientific claim authorization.
- Distinguish provider process state, controller state, retrieved output state, and scientific qualification.
- Keep user-facing status `UNKNOWN` when all that is known is that the provider status command ran.
- Controller `KAGGLE_STATUS_CHECK_PERFORMED` is a heartbeat for the status *query*, not a provider `RUNNING` attestation. Every 300 iterations (~5 hours plus overhead), the controller attempts to dispatch a fresh `resume` workflow.
- The current controller is scoped to GitHub environment `kaggle-production`. A new resume/retrieve may require an environment reviewer; check pending approval before assuming automatic continuation.
- There is a narrow exception in the workflow allowing only `resume`/`retrieve` at exact commit `643b8a260b6fcff78bb02f3a63f348c29fd91317` when new production submission is disabled. Preserve this exception until retrieval is complete.

## State machine (evaluate after terminal provider evidence)

### A — COMPLETE

1. Confirm the exact kernel ref and the provider's terminal `COMPLETE`, and identify the controller that detected it.
2. Let `operation=retrieve` dispatch (or assess the dispatch/approval failure without submitting a kernel). Inspect GitHub's independent verification outcome.
3. Require `rhombus_phase3_salex_run_receipt.json` with `status=PRODUCTION_COMPLETE_SOURCE_STREAM_FINISHED` and the exact original source commit.
4. Require the summary and **10,447,765** sAlex rows, **256,963** WBM targets, and both frozen source digests.
5. Verify each compressed part's byte length and SHA256, concatenated compressed digest, stream-decompressed SQLite/JSONL digest, and the summary digest. The existing workflow's `Independently verify retrieved hashes and row counts` implements these checks.
6. Only after `SALEX_KAGGLE_RETRIEVAL_VERIFIED` and successful upload should the sAlex/WBM component be marked independently verified. MPTrj lineage remains unverified; do NOT authorize unseen-generalization, held-out qualification, or model validity.

### B — ERROR

1. Capture the sanitized `kaggle-error.log` and controller-state artifact. Do not upload raw provider responses or credentials.
2. Inspect the earliest causal error in the Kaggle notebook: WBM download/identity, sAlex network/extraction/LMDB, scientific structure conversion, SQLite/disk/memory, compression/output, or result verification.
3. Inspect any available Kaggle output. An incomplete DB is **diagnostic only**, not an authorized production membership index.
4. Reproduce failure with the smallest bounded nonproduction fixture, fix on a new versioned commit, and run focused CI plus full required merge gates.
5. Only after confirming original run termination and explicit production authorization consider a *new* submit; never reuse the same immutable source/receipt identity for changed code.

### C — TIMEOUT / provider cancelled or incomplete execution

1. Capture the terminal provider status, wall-clock, last notebook log line, and any accessible output listings. Some providers may expose an incomplete output version; do not assume it exists.
2. Distinguish actual provider timeout from continued `RUNNING` with no progress. A 300-check controller loop ending is **not** Kaggle timeout.
3. Evaluate every recoverable output for valid schema, SQLite `integrity_check`, consistent row counts and WAL state, frozen source binding and hash/manifest. In-progress bytes cannot be counted as qualified science.
4. The current driver writes provisional SQLite under `/kaggle/temp/rhombus-phase3-salex` and only exports compressed production outputs after the full stream. Therefore there is **no guaranteed durable partial checkpoint** for this run.
5. Before re-executing, implement and test immutable source-shard manifests and independent checkpoint upload, safe resume, deterministic merge and complete-source end-to-end attestation.

## Findings and proposed future engineering contracts (not yet implemented)

1. **Progress visibility:** emit bounded, non-sensitive structured progress events: stage name; monotonic elapsed seconds; consumed records/shards; committed SQLite rows; upload/checkpoint state; timestamp; explicit `diagnostic_only`. Do not report percentage without a validated denominator.
2. **Honest polling:** stop swallowing all provider CLI/API errors as apparent `RUNNING`. Separate `STATUS_QUERY_ERROR`, `QUEUED`, `RUNNING`, `COMPLETE`, `ERROR`, `CANCELLED`, and `UNKNOWN`. Retry transient status query failures with a bounded budget; preserve redaction.
3. **Durable checkpoints:** compute stable source-member/shard boundaries, normalized record IDs, row counts, frozen protocol IDs and digest; finalize SQLite safely (including WAL), compress and validate it, and export after each independently bounded unit.
4. **Resume semantics:** accept *only* trusted-configuration checkpoints whose source identity, protocol version, ordered shard IDs and digest all agree. Recompute missing/corrupt shards; never accept a user/model-provided arbitrary checkpoint URL or path.
5. **Merge semantics:** verify disjoint and complete shard coverage; reject duplicate record IDs and missing ranges; rebuild deterministic indices; recompute overlap without double-counting; independently validate expected final counts and whole-source SHA256.
6. **Budget protection:** reserve walltime for checkpoint/upload/receipt and avoid starting units that cannot finish safely. Validate storage and artifact quotas before relying on them.
7. **Tests:** synthetic interruption after a committed shard, after local DB write before upload, during multipart upload, at resume, with duplicate or poisoned manifests, with incorrect source SHA, and with transient provider status failures. Assert fail-closed scientific authorization.
8. **Operational security:** no Kaggle token in outputs; limited telemetry; respect `kaggle-production` reviewers and existing default-deny behavior.
9. **No state inflation:** update `CURRENT.json` with proposal/evidence pointers only; implementation and successful empirical qualification require separate subsequent checkpoints.

## Current observed status vs proof

The user observed a Kaggle notebook past 28,000 seconds, no new informative notebook log after prior warnings, and GitHub `Poll Kaggle terminal state` with >200 query iterations. This does not establish processed rows, completed index, provider timeout, or final receipt. The source throughput pilot processed 10,000 rows in 16.87 s; its ~4.90 h straight-line estimate explicitly excludes WBM target indexing, production SQLite work and structure matching, so it is not an upper bound.

**Exit criterion:** no scientific or operational success claim without a real terminal observation plus a verified receipt. This playbook does not launch, stop, or poll Kaggle.

## Checkpoint 0112 — post-COMMIT diagnostic chunks are locally recoverable only

Future Kaggle sAlex runs now stage hash-bound, independent 50,000-record
partial `MembershipIndexRecord` JSONL.gz chunks and explicit
SOURCE_UNVERIFIED receipts under `/kaggle/working`, with flushed
progress events after each completed piece. The callback is called only
after a successful SQLite batch commit, never ahead of source work.
The current historical Kaggle execution remains pinned to its immutable
older commit and is unaffected.

This is **not** external mid-run durability: Kaggle may not publish output
files while a notebook is running, or after an abrupt worker kill.
Partial pieces alone cannot prove the complete source hash or authorize
resume/full scientific evidence. The next milestone is separately
completed shard versions, externally verified archive upload and
source-bound deterministic resume. Details:
[partial chunk recovery guide](PHASE3_SALEX_PARTIAL_CHUNK_RECOVERY_V1.md).
