"""Stateless P1 batch sharding and resume logic (CPU-tested, MLIP-agnostic).

Protocol (see rudeus/mlip/DESIGN.md section 2):
  - Batch files are committed BEFORE any GPU session starts; each carries
    everything the worker needs (no coordination at runtime).
  - batch_id (v2) = sha256(parent_id | child_index | seed |
    generation_config_hash | checkpoint_id | structure_sha256)[:16], where
    structure_sha256 is the canonical-JSON sha of the input structure_dict.
    The v1 scheme (no seed, no structure) is LEGACY: it allowed two different
    structures to share one ID (observed overwrite, Stage 1 report).
  - Shard assignment is int(batch_id,16) % n_shards (unchanged across schemes).
  - A batch is finished iff its result file exists in done_dir AND (when the
    record carries one) its input_structure_sha256 matches the pending input.
    Missing or stale = unfinished = re-runnable.
  - No locks, no queue, no daemon, no database. Two workers on one shard
    converge (same inputs, idempotent files, last-writer-wins in git).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

#: Current batch-ID scheme marker. Files without this marker are legacy v1.
BATCH_ID_SCHEME_V2 = "v2-structure-sha256"

#: Result verdicts meaning "attempted and failed" (retryable via retry_errors).
ERROR_VERDICTS = frozenset({"ERROR"})
#: Result verdicts meaning "deliberately not attempted" (retryable via
#: retry_skipped). Includes the legacy string so previously written skipped
#: records keep their meaning without migration.
SKIPPED_VERDICTS = frozenset({"DISORDERED_UNSUPPORTED_FOR_MLIP",
                              "SKIPPED_DISORDERED"})


def structure_dict_sha256(structure_dict: Dict[str, Any]) -> str:
    """Canonical-JSON sha256 of a serialized structure dict.

    Same canonicalization as generation.structure_sha256 (sort_keys,
    default=str): deterministic, dict-order-independent, reproducible.
    Pure-dict operation — no pymatgen needed, so sharding stays MLIP-agnostic.
    """
    payload = json.dumps(structure_dict, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_batch_id_v1(
    parent_id: str,
    child_index: int,
    generation_config_hash: str,
    checkpoint_id: str,
) -> str:
    """LEGACY v1 derivation (no seed, no structure). For migration audit only.

    Do NOT use for new batches: it cannot distinguish two different
    structures sharing parent/index/config/checkpoint.
    """
    payload = "|".join([parent_id, str(child_index),
                        generation_config_hash, checkpoint_id])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def make_batch_id(
    parent_id: str,
    child_index: int,
    seed: int,
    generation_config_hash: str,
    checkpoint_id: str,
    structure_dict: Dict[str, Any],
) -> str:
    """Deterministic v2 batch ID: pure function of the full computational input.

    Binds parent/index/seed/config/checkpoint AND the input structure hash,
    so one input structure has exactly one identity and one identity can
    never silently refer to a different structure.
    """
    struct_sha = structure_dict_sha256(structure_dict)
    payload = "|".join([parent_id, str(child_index), str(seed),
                        generation_config_hash, checkpoint_id, struct_sha])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def assign_shard(batch_id: str, shard_index: int, n_shards: int) -> bool:
    """Pure-function shard assignment. Raises on out-of-range shard_index."""
    if not 0 <= shard_index < n_shards:
        raise ValueError(f"shard_index {shard_index} out of range for {n_shards} shards")
    return int(batch_id, 16) % n_shards == shard_index


def shard_batches(
    batch_ids: List[str],
    shard_index: int,
    n_shards: int,
) -> List[str]:
    """Deterministic subset for one worker (sorted for stable order)."""
    return sorted(b for b in batch_ids if assign_shard(b, shard_index, n_shards))


def write_json_atomic(path: Union[str, Path], payload: Dict[str, Any]) -> Path:
    """Atomic JSON write (temp file + os.replace) — never a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)
    return path


def make_batch_file(
    pending_dir: Union[str, Path],
    parent_id: str,
    child_index: int,
    seed: int,
    generation_config_hash: str,
    checkpoint_id: str,
    structure_dict: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Create one committed v2 batch file. Returns its path."""
    batch_id = make_batch_id(parent_id, child_index, seed,
                             generation_config_hash, checkpoint_id,
                             structure_dict)
    payload: Dict[str, Any] = {
        "batch_id_scheme": BATCH_ID_SCHEME_V2,
        "batch_id": batch_id,
        "child_index": child_index,
        "seed": seed,
        "parent_id": parent_id,
        "generation_config_hash": generation_config_hash,
        "checkpoint_id": checkpoint_id,
        "structure_sha256": structure_dict_sha256(structure_dict),
        "structure_dict": structure_dict,
    }
    if extra:
        payload.update(extra)
    return write_json_atomic(Path(pending_dir) / f"{batch_id}.json", payload)


def run_batches(
    pending_dir: Union[str, Path],
    done_dir: Union[str, Path],
    shard_index: int,
    n_shards: int,
    relax_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    worker_info: Optional[Dict[str, Any]] = None,
    retry_errors: bool = False,
    retry_skipped: bool = False,
) -> Dict[str, int]:
    """Run this worker's shard. Resume-safe: done files are never recomputed.

    Outcome classes (conservative defaults; explicit flags to retry):
      DONE (KEEP_FOR_P2 / FAIL_CONVERGENCE / FAIL_UNPHYSICAL): skipped on
        rerun when the input structure hash matches; recomputed as stale when
        it disagrees. A valid completed result stays idempotent.
      ERROR (raised exception -> ERROR record, or returned ERROR verdict):
        skipped by default; recomputed ONLY with retry_errors=True.
      SKIPPED (DISORDERED_UNSUPPORTED_FOR_MLIP and legacy SKIPPED_DISORDERED):
        skipped by default; recomputed ONLY with retry_skipped=True.
      Retry never loops: each invocation recomputes at most once per batch
      (a deterministic unsupported input yields the same SKIPPED record again,
      which is then skipped on the next default run).

    Crash-resistant per candidate: ANY exception from relax_fn is caught and
    written as a structured ERROR record for that batch (verdict, exception
    class, message, input-structure hash, worker) — the shard NEVER aborts
    mid-loop. Deliberate process death (SIGKILL, session kill) still leaves
    no file, so the batch stays unfinished and is recomputed on resume.
    BaseException (KeyboardInterrupt etc.) is NOT caught.

    Identity hardening: legacy (non-v2) pending files are NEVER processed —
    they are counted as skipped_legacy so old and new identity schemes can
    never be treated as equivalent. Resume is verified by structure hash: a
    done record whose input_structure_sha256 disagrees with the pending input
    is stale (e.g. written for overwritten content) and is recomputed, never
    trusted. Records without a hash (legacy ERROR records) are trusted as-is.
    Returns counts {processed, errored, skipped, skipped_done, skipped_shard,
    skipped_legacy, stale_recomputed, retried_errors, retried_skipped}.
    """
    pending_dir, done_dir = Path(pending_dir), Path(done_dir)
    counts = {"processed": 0, "errored": 0, "skipped": 0, "skipped_done": 0,
              "skipped_shard": 0, "skipped_legacy": 0, "stale_recomputed": 0,
              "retried_errors": 0, "retried_skipped": 0}
    for batch_file in sorted(pending_dir.glob("*.json")):
        batch_id = batch_file.stem
        if not assign_shard(batch_id, shard_index, n_shards):
            counts["skipped_shard"] += 1
            continue
        try:
            with open(batch_file, encoding="utf-8") as f:
                batch = json.load(f)
            if not isinstance(batch, dict) or "structure_dict" not in batch:
                raise ValueError("pending file is not a valid batch record")
        except Exception as e:  # malformed pending: ERROR record, never abort
            done_payload = {"batch_id": batch_id,
                            "malformed_pending_file": batch_file.name,
                            "result": {"p1_verdict": "ERROR",
                                       "error_type": "MalformedPending",
                                       "error_message": str(e)[:500],
                                       "converged": False,
                                       "input_structure_sha256": None},
                            "worker": worker_info or {}}
            write_json_atomic(done_dir / f"{batch_id}.json", done_payload)
            counts["errored"] += 1
            continue
        if batch.get("batch_id_scheme") != BATCH_ID_SCHEME_V2:
            counts["skipped_legacy"] += 1
            continue
        done_file = done_dir / f"{batch_id}.json"
        if done_file.exists():
            try:
                with open(done_file, encoding="utf-8") as f:
                    prior = json.load(f)
                prior_result = prior.get("result")
                prior_sha = (prior_result.get("input_structure_sha256")
                             if isinstance(prior_result, dict) else None)
                prior_verdict = (prior_result.get("p1_verdict")
                                 if isinstance(prior_result, dict) else None)
            except Exception:
                prior_sha, prior_verdict, prior_result = None, None, None
            if not isinstance(prior_result, dict):
                counts["stale_recomputed"] += 1  # malformed: never trusted
            elif (prior_sha is not None
                    and prior_sha != structure_dict_sha256(batch["structure_dict"])):
                counts["stale_recomputed"] += 1  # wrong structure: recompute
            elif prior_verdict in ERROR_VERDICTS and not retry_errors:
                counts["skipped_done"] += 1
                continue
            elif prior_verdict in SKIPPED_VERDICTS and not retry_skipped:
                counts["skipped_done"] += 1
                continue
            elif prior_verdict in ERROR_VERDICTS and retry_errors:
                counts["retried_errors"] += 1  # fall through: recompute
            elif prior_verdict in SKIPPED_VERDICTS and retry_skipped:
                counts["retried_skipped"] += 1  # fall through: recompute
            else:
                counts["skipped_done"] += 1
                continue
        try:
            result = relax_fn(batch["structure_dict"])
        except Exception as e:  # per-candidate backstop: record, never abort
            result = {
                "p1_verdict": "ERROR",
                "error_type": type(e).__name__,
                "error_message": str(e)[:500],
                "converged": False,
                "input_structure_sha256": structure_dict_sha256(
                    batch["structure_dict"]),
            }
            counts["errored"] += 1
        else:
            verdict = result.get("p1_verdict") if isinstance(result, dict) else None
            if verdict in ERROR_VERDICTS:
                counts["errored"] += 1
            elif verdict in SKIPPED_VERDICTS:
                counts["skipped"] += 1
            else:
                counts["processed"] += 1
        done_payload = dict(batch)
        done_payload["result"] = result
        done_payload["worker"] = worker_info or {}
        write_json_atomic(done_file, done_payload)
    return counts
