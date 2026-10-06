"""Synthetic compatibility checks for B5 P1 pending batches and stateless runner.

No MLIP is loaded and no scientific P1 verdict is authorized. The purpose is
to prove execution plumbing before spending GPU compute.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence

from rudeus.mlip.sharding import run_batches, structure_dict_sha256
from rudeus.science.known_material_b5_p1_batch_materialization import (
    B5P1PendingBatch,
)


B5_P1_WORKER_CONTRACT_VERSION = "known-material-b5-p1-worker-contract-v1"


def _write_pending(root: Path, batches: Sequence[B5P1PendingBatch]) -> Path:
    pending = root / "pending"
    pending.mkdir(parents=True, exist_ok=True)
    for batch in batches:
        path = pending / f"{batch.batch_id}.json"
        path.write_text(
            json.dumps(batch.to_dict(), sort_keys=True),
            encoding="utf-8",
        )
    return pending


def validate_synthetic_worker_handoff(
    batches: Sequence[B5P1PendingBatch],
) -> dict:
    """Exercise normal completion, resume, and one isolated execution error."""
    items = tuple(batches)
    if not items:
        raise ValueError("worker contract requires pending batches")
    if len({item.batch_id for item in items}) != len(items):
        raise ValueError("worker contract requires unique batch identities")

    with TemporaryDirectory() as directory:
        root = Path(directory)
        pending = _write_pending(root, items)
        done = root / "done"

        def successful_relax(structure_dict):
            return {
                "p1_verdict": "KEEP_FOR_P2",
                "converged": True,
                "synthetic_only": True,
            }

        first = run_batches(
            pending,
            done,
            shard_index=0,
            n_shards=1,
            relax_fn=successful_relax,
            worker_info={"mode": "synthetic-contract"},
            batch_order=[item.batch_id for item in items],
        )
        if first["processed"] != len(items) or first["errored"] != 0:
            raise AssertionError("normal synthetic P1 handoff did not complete all batches")

        for item in items:
            payload = json.loads((done / f"{item.batch_id}.json").read_text(encoding="utf-8"))
            if payload["structure_sha256"] != item.structure_sha256:
                raise AssertionError("worker changed pending structure identity")
            if payload["source_execution_plan_hash"] != item.source_execution_plan_hash:
                raise AssertionError("worker lost B5 P1 plan provenance")
            if payload["result"]["input_structure_sha256"] != item.structure_sha256:
                raise AssertionError("P1 result is not bound to pending structure SHA")
            if payload["result"]["p1_verdict"] != "KEEP_FOR_P2":
                raise AssertionError("synthetic success verdict was not retained")

        resumed = run_batches(
            pending,
            done,
            shard_index=0,
            n_shards=1,
            relax_fn=lambda _: (_ for _ in ()).throw(AssertionError("resume recomputed")),
            worker_info={"mode": "synthetic-contract-resume"},
            batch_order=[item.batch_id for item in items],
        )
        if resumed["skipped_done"] != len(items) or resumed["processed"] != 0:
            raise AssertionError("P1 resume is not idempotent")

    with TemporaryDirectory() as directory:
        root = Path(directory)
        pending = _write_pending(root, items)
        done = root / "done"
        target_sha = items[0].structure_sha256

        def one_failure(structure_dict):
            if structure_dict_sha256(structure_dict) == target_sha:
                raise RuntimeError("synthetic isolated worker failure")
            return {
                "p1_verdict": "KEEP_FOR_P2",
                "converged": True,
                "synthetic_only": True,
            }

        isolated = run_batches(
            pending,
            done,
            shard_index=0,
            n_shards=1,
            relax_fn=one_failure,
            worker_info={"mode": "synthetic-contract-error-isolation"},
            batch_order=[item.batch_id for item in items],
        )
        if isolated["errored"] != 1 or isolated["processed"] != len(items) - 1:
            raise AssertionError("one worker failure was not isolated to one batch")
        failed = json.loads((done / f"{items[0].batch_id}.json").read_text(encoding="utf-8"))
        if failed["result"]["p1_verdict"] != "ERROR":
            raise AssertionError("operational exception did not remain ERROR")
        if failed["result"].get("error_type") != "RuntimeError":
            raise AssertionError("operational error type was not retained")

    return {
        "contract_version": B5_P1_WORKER_CONTRACT_VERSION,
        "batch_count": len(items),
        "normal_processed": first["processed"],
        "resume_skipped_done": resumed["skipped_done"],
        "isolated_error_count": isolated["errored"],
        "isolated_success_count": isolated["processed"],
        "synthetic_only": True,
        "scientific_verdict_authorized": False,
        "p1_execution_started": False,
        "qualification_evidence_authorized": False,
        "production_search_authorized": False,
    }
