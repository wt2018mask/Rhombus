"""Execution contract for the three authorized B5 DEV P1 relaxations.

This adapter consumes previously materialized B5 pending batches and delegates
actual relaxation to the existing stateless run_batches path. Scientific
thresholds and P1 verdict semantics remain owned by rudeus.mlip.relax.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Sequence

from rudeus.mlip.sharding import run_batches
from rudeus.science.known_material_b5_p1_batch_materialization import (
    B5P1PendingBatch,
)


B5_P1_REAL_RUNNER_VERSION = "known-material-b5-p1-real-runner-v1"


def validate_uniform_p1_protocol(batches: Sequence[B5P1PendingBatch]) -> dict:
    items = tuple(batches)
    if not items:
        raise ValueError("real P1 runner requires pending batches")
    if len({item.batch_id for item in items}) != len(items):
        raise ValueError("real P1 runner requires unique batch IDs")
    protocols = [dict(item.mlip_protocol) for item in items]
    if any(protocol != protocols[0] for protocol in protocols[1:]):
        raise ValueError("B5 P1 runner requires one uniform MLIP protocol")
    if any(item.split != "DEV" or item.p0_state != "PLAUSIBLE" for item in items):
        raise ValueError("real B5 P1 runner accepts only authorized DEV PLAUSIBLE batches")
    return protocols[0]


def execute_b5_p1_batches(
    batches: Sequence[B5P1PendingBatch],
    *,
    relax_fn: Callable,
    work_root: Path,
    worker_info: dict,
) -> dict:
    """Execute all authorized DEV batches through the existing stateless runner."""
    items = tuple(sorted(batches, key=lambda item: item.batch_id))
    protocol = validate_uniform_p1_protocol(items)
    pending = work_root / "pending"
    done = work_root / "done"
    pending.mkdir(parents=True, exist_ok=True)
    done.mkdir(parents=True, exist_ok=True)

    for item in items:
        (pending / f"{item.batch_id}.json").write_text(
            json.dumps(item.to_dict(), sort_keys=True),
            encoding="utf-8",
        )

    counts = run_batches(
        pending,
        done,
        shard_index=0,
        n_shards=1,
        relax_fn=relax_fn,
        worker_info=worker_info,
        batch_order=[item.batch_id for item in items],
    )
    return {
        "runner_version": B5_P1_REAL_RUNNER_VERSION,
        "batch_count": len(items),
        "protocol": protocol,
        "counts": counts,
        "done_dir": str(done),
        "scientific_results_generated": True,
        "qualification_evidence_authorized": False,
        "held_out_execution_authorized": False,
        "production_search_authorized": False,
    }
