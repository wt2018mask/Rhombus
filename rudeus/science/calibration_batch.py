"""Batch orchestration over a frozen calibration dataset's replicate inventory.

Orchestration only: resolves the dataset lineage once, then materializes
each declared replicate through the existing single-replicate machinery.
No estimator logic, no aggregation science, no verdicts, no qualification.
Per-replicate persisted records remain authoritative; the returned mapping
is an operational summary, never a scientific result.
"""

from __future__ import annotations

from rudeus.execution.contracts import ExecutionError, classify_failure
from rudeus.science.calibration import CalibrationDatasetManifest, CalibrationPlan
from rudeus.science.calibration_execution import (
    build_calibration_task,
    materialize_replicate,
    validate_materialization_lineage,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import VALID, validate_dataset


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _resolve_dataset(store, dataset_manifest_hash):
    try:
        return store.retrieve(CalibrationDatasetManifest, dataset_manifest_hash)
    except ExecutionError:
        _fail("calibration dataset lineage is not valid")


def materialize_calibration_dataset(
    *,
    calibration_store: CalibrationStore,
    dataset_manifest_hash: str,
    artifact_root,
    seeds,
    cells=None,
    code_revision,
) -> dict:
    """Materialize every replicate declared by a frozen dataset manifest.

    Args:
        calibration_store: source of all frozen G.1 records.
        dataset_manifest_hash: content hash of the dataset to execute.
        artifact_root: root for trajectory/manifest/attempt artifacts.
        seeds: explicit mapping of replicate ID to integer seed. Must cover
            exactly the declared inventory; seeds are never invented.
        cells: optional mapping of replicate ID to parameter cell ID. When
            omitted, the dataset must declare exactly one parameter cell.
        code_revision: code revision stamped on every constructed task.

    Returns a deterministic operational summary; per-replicate persisted
    records remain authoritative. Structural lineage problems fail fast
    before any materialization; per-replicate failures are isolated.
    """
    from rudeus.science.calibration import CalibrationDatasetManifest

    if not isinstance(calibration_store, CalibrationStore):
        _fail("calibration batch requires a CalibrationStore")
    if not isinstance(seeds, dict):
        _fail("calibration batch seeds must be an explicit mapping")
    dataset = _resolve_dataset(calibration_store, dataset_manifest_hash)
    if not isinstance(dataset, CalibrationDatasetManifest):
        _fail("calibration dataset lineage is not valid")
    if validate_dataset(calibration_store, dataset_manifest_hash).status != VALID:
        _fail("calibration dataset lineage is not valid")
    declared = list(dataset.attempted_replicate_ids)
    if len(set(declared)) != len(declared):
        _fail("calibration dataset inventory contains duplicates")
    if set(seeds) != set(declared):
        _fail("calibration batch seeds must cover exactly the declared inventory")
    for replicate_id in declared:
        seed = seeds[replicate_id]
        if isinstance(seed, bool) or not isinstance(seed, int):
            _fail("calibration batch seeds must be integers")
    if cells is None:
        if len(dataset.parameter_cell_ids) != 1:
            _fail("calibration batch cells must be explicit for multi-cell datasets")
        cells = {replicate_id: dataset.parameter_cell_ids[0] for replicate_id in declared}
    if not isinstance(cells, dict) or set(cells) != set(declared):
        _fail("calibration batch cells must cover exactly the declared inventory")
    if len(dataset.generator_spec_hashes) != 1:
        _fail("calibration batch requires exactly one declared generator")
    if len(dataset.truth_record_hashes) != 1:
        _fail("calibration batch requires exactly one declared truth record")
    generator_spec_hash = dataset.generator_spec_hashes[0]
    truth_record_hash = dataset.truth_record_hashes[0]

    try:
        plan = calibration_store.retrieve(CalibrationPlan, dataset.plan_hash)
    except ExecutionError:
        _fail("calibration dataset lineage is not valid")

    order = sorted(declared)
    results, succeeded, failed = {}, [], []
    for replicate_id in order:
        task = build_calibration_task(
            plan_hash=plan.content_hash,
            scope_hash=dataset.scope_hash,
            dataset_manifest_hash=dataset.content_hash,
            generator_spec_hash=generator_spec_hash,
            truth_record_hash=truth_record_hash,
            replicate_id=replicate_id,
            parameter_cell_id=cells[replicate_id],
            split_assignment=dataset.split_assignment.value,
            seed=seeds[replicate_id],
            code_revision=code_revision)
        try:
            validate_materialization_lineage(calibration_store, task)
            outcome = materialize_replicate(
                task=task, calibration_store=calibration_store,
                artifact_root=artifact_root)
        except Exception as exc:
            failure = classify_failure(exc)
            outcome = {"artifact_status": "FAILED",
                       "failure_class": failure.value, "reason": str(exc)}
        results[replicate_id] = outcome
        (succeeded if outcome.get("artifact_status") == "STORED" else failed
         ).append(replicate_id)
    return {"dataset_manifest_hash": dataset.content_hash,
            "declared_replicates": order,
            "attempted": len(order),
            "succeeded": sorted(succeeded),
            "failed": sorted(failed),
            "results": results}


__all__ = ["materialize_calibration_dataset"]
