"""Stateless P1 batch sharding and resume logic (CPU-tested, MLIP-agnostic).

Protocol (see rudeus/mlip/DESIGN.md section 2):
  - Batch files are committed BEFORE any GPU session starts; each carries
    everything the worker needs (no coordination at runtime).
  - batch_id = sha256(parent_id | child_index | generation_config_hash |
    checkpoint_id)[:16]; shard assignment is int(batch_id,16) % n_shards.
  - A batch is finished iff its result file exists in done_dir (atomic
    temp-file + os.replace writes). Missing = unfinished = re-runnable.
  - No locks, no queue, no daemon, no database. Two workers on one shard
    converge (same inputs, idempotent files, last-writer-wins in git).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


def make_batch_id(
    parent_id: str,
    child_index: int,
    generation_config_hash: str,
    checkpoint_id: str,
) -> str:
    """Deterministic batch ID (pure function of committed inputs)."""
    payload = "|".join([parent_id, str(child_index),
                        generation_config_hash, checkpoint_id])
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
    generation_config_hash: str,
    checkpoint_id: str,
    structure_dict: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Create one committed batch file. Returns its path."""
    batch_id = make_batch_id(parent_id, child_index,
                             generation_config_hash, checkpoint_id)
    payload: Dict[str, Any] = {
        "batch_id": batch_id,
        "child_index": child_index,
        "parent_id": parent_id,
        "generation_config_hash": generation_config_hash,
        "checkpoint_id": checkpoint_id,
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
) -> Dict[str, int]:
    """Run this worker's shard. Resume-safe: done files are never recomputed.

    relax_fn maps structure_dict -> result dict. Any exception from relax_fn
    propagates (the batch simply stays unfinished — no poison records).
    Returns counts {processed, skipped_done, skipped_shard}.
    """
    pending_dir, done_dir = Path(pending_dir), Path(done_dir)
    counts = {"processed": 0, "skipped_done": 0, "skipped_shard": 0}
    for batch_file in sorted(pending_dir.glob("*.json")):
        batch_id = batch_file.stem
        if not assign_shard(batch_id, shard_index, n_shards):
            counts["skipped_shard"] += 1
            continue
        done_file = done_dir / f"{batch_id}.json"
        if done_file.exists():
            counts["skipped_done"] += 1
            continue
        with open(batch_file, encoding="utf-8") as f:
            batch = json.load(f)
        result = relax_fn(batch["structure_dict"])
        done_payload = dict(batch)
        done_payload["result"] = result
        done_payload["worker"] = worker_info or {}
        write_json_atomic(done_file, done_payload)
        counts["processed"] += 1
    return counts
