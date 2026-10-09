# Phase 3 sAlex Kaggle — post-commit partial chunks (checkpoint 0112)

## Why this exists

The earlier multi-hour sAlex Kaggle full-source processing had little useful
progress visibility and its complete SQLite and compressed outputs were only
exported after all 10,447,765 source records finished. A timeout could leave
provisional data under `/kaggle/temp` inaccessible. A partial artifact is
not evidence that a whole-source scientific audit succeeded.

## New behavior for **future, separately authorized** executions

The production sAlex driver passes `--partial-output-dir
/kaggle/working/rhombus_salex_partial_chunks` to the existing
`run_salex_wbm_overlap.py full` process. It does **not** submit a kernel
or change previously pinned executions.

After each SQLite batch of 5,000 membership records is **committed**,
the optional callback writes those same stable `MembershipIndexRecord`
metadata rows into a pending gzip JSONL stream. At exactly **50,000**
committed records it closes and flushes a gzip file, computes SHA256,
writes a separate final append-only JSON receipt, and prints a
`SALEX_COMMITTED_DIAGNOSTIC_CHUNK` event immediately (`flush=True`).

A complete `.jsonl.gz` plus adjacent `.json` is an independently
checkable *partial diagnostic*; a lone `.inflight` file is NOT. Each
receipt records the committed row interval, piece hash, prior piece hash
and explicit false claims for whole-source verification and model training.
No raw source LMDB, tokens or Kaggle credentials are placed in this format.

### Local verification

```python
from pathlib import Path
from scripts.development.salex_committed_chunks import verify_committed_chunk

folder = Path("/kaggle/working/rhombus_salex_partial_chunks")
piece = folder / "salex-committed-0000.jsonl.gz"
manifest = folder / "salex-committed-0000.json"
print(verify_committed_chunk(piece, manifest))
```

The offline regression in `tests/test_phase3_salex_committed_chunks.py`
simulates a source crash after a previously sealed piece. It verifies that
full pieces remain distinct from uncommitted `.inflight` data and that
hash tampering and scientific claim promotion fail closed.

## Important recovery limitation

**This is not yet a durable cross-session Kaggle checkpoint system.**
Kaggle `/working` files are local to the notebook runtime. The Kaggle
platform may expose the files only when it publishes a completed saved
Notebook version; on sudden termination, an in-memory or disk file need
not become a downloadable output. Nor are the pieces sufficient to
resume exact streaming on their own: only complete original source hash,
shard coverage and checkpoint identity checks could authorize that.

Before saying 'sleep through a 10+ hour job and still get intermediate
results guaranteed', further work must create **independently completed,
bounded shard runs** (or a separately approved external authenticated
upload destination), upload each successful shard plus manifest/digest,
verify retrieval outside Kaggle, then implement explicit deterministic
resume/reassembly with no gaps or duplicates and complete-source SHA256
verification. External write credentials must never leak into Kaggle
notebooks or public artifacts.

The historical 2026-10-08 sAlex run and its missing run receipt cannot
be repaired retroactively by a new source commit. This implementation
does not execute a Kaggle job, authorize unseen generalization or
prove MACE-MPA-0 exact training membership.
