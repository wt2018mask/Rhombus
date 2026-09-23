"""Frozen S2 DEV coverage evidence run (orchestration only, no qualification).

Executes the committed S2 DEV inventory (64 replicates, seeds 201..264)
through the existing calibration pipeline and persists one descriptive
coverage summary. Importing this module executes nothing; use
``main()`` or the ``__main__`` guard.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import (
    CalibrationClass,
    CalibrationDatasetManifest,
    SplitAssignment,
)
from rudeus.science.calibration_batch import materialize_calibration_dataset
from rudeus.science.calibration_estimator import (
    ESTIMATOR_MODULE,
    ESTIMATOR_NAME,
    estimate_calibration_replicate,
    estimate_interval_for_replicate,
    persist_coverage_summary,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import VALID, validate_dataset
from rudeus.science.contracts import digest
from rudeus.science.statistics import (
    MATCHED_ORIGIN_BLOCKS_V2,
    ResamplingSpec,
    coverage_experiment,
)
from rudeus.science.calibration_s1 import (
    S1_CODE_REVISION,
    S1_ESTIMATOR_CONFIG,
    S1_TRUTH_D_M2_PER_S,
    build_s1_plan_family,
)
from rudeus.science.calibration_s2 import (
    S1_DEV_SEEDS_RESERVED,
    S1_HELDOUT_SEEDS_RESERVED,
    S2_DEV_REPLICATES,
    S2_DEV_SEEDS,
    S2_MONTE_CARLO_CONFIDENCE,
    S2_NOMINAL_COVERAGE,
    S2_PILOT_SEEDS_RESERVED,
    S2_PROCEDURE,
    S2_PROCEDURE_HASH,
    S2_RESAMPLING_SEED,
)


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def assert_frozen_preconditions():
    """Verify the frozen S2 DEV inventory before any execution call."""
    if set(S2_DEV_SEEDS.values()).isdisjoint(S1_HELDOUT_SEEDS_RESERVED) is False:
        _fail("S2 DEV seeds overlap HELD_OUT")
    if set(S2_DEV_SEEDS.values()).isdisjoint(
            S1_DEV_SEEDS_RESERVED | S1_HELDOUT_SEEDS_RESERVED | S2_PILOT_SEEDS_RESERVED) is False:
        _fail("S2 DEV seeds overlap reserved seeds")
    if len(S2_DEV_SEEDS) != 64 or len(set(S2_DEV_SEEDS.values())) != 64:
        _fail("S2 DEV inventory must hold exactly 64 unique seeds")
    if tuple(S2_DEV_SEEDS) != S2_DEV_REPLICATES:
        _fail("S2 DEV replicate IDs must match the frozen inventory")
    if digest(S2_PROCEDURE) != S2_PROCEDURE_HASH:
        _fail("S2 procedure hash mismatch")
    if S2_PROCEDURE["nominal_coverage"] != 0.68:
        _fail("S2 nominal coverage is not the frozen value")
    if S2_PROCEDURE["block_origins"] != 2:
        _fail("S2 block length is not the frozen value")
    if S2_PROCEDURE["resampling_spec"]["n_resamples"] != 16:
        _fail("S2 resample count is not the frozen value")


def _read_json(path):
    return json.loads(Path(path).read_bytes())


def _find_replicate_manifest_hash(store, replicate_id):
    found = [p for p in (store.root / "calibration_replicates").glob("*.json")
             if json.loads(p.read_bytes())["replicate_id"] == replicate_id]
    if len(found) != 1:
        _fail(f"replicate manifest for {replicate_id} is ambiguous or missing")
    return found[0].stem


def _find_estimator_result(root, replicate_manifest_hash):
    found = [p for p in (root / "estimator_results").glob("*.json")
             if json.loads(p.read_bytes())["replicate_manifest_hash"]
             == replicate_manifest_hash]
    if len(found) != 1:
        _fail("estimator result for replicate is ambiguous or missing")
    return json.loads(found[0].read_bytes())


def _find_interval_record(root, estimator_result_hash):
    found = [p for p in (root / "calibration_intervals").glob("*.json")
             if json.loads(p.read_bytes())["estimator_result_hash"]
             == estimator_result_hash]
    if len(found) != 1:
        _fail("interval record for estimator result is ambiguous or missing")
    return json.loads(found[0].read_bytes())


def build_s1_family_for_run(store):
    """Author the frozen S1 plan family (ids must match S1 content hashes)."""
    return build_s1_plan_family(store)


def build_s2_dev_dataset(store, family):
    """Author, store, and validate the frozen ds-s2-dev-64 dataset manifest."""
    dataset = CalibrationDatasetManifest(
        dataset_id="ds-s2-dev-64",
        plan_hash=family["plan"],
        scope_hash=family["scope"],
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",),
        trajectory_ids=tuple(f"traj-{rep}" for rep in S2_DEV_REPLICATES),
        truth_record_hashes=(family["truth"],),
        split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(family["generator"],),
        artifact_manifest_hashes=(),
        attempted_replicate_ids=S2_DEV_REPLICATES,
    )
    dataset_hash = store.store(dataset)
    if validate_dataset(store, dataset_hash).status != VALID:
        _fail("S2 DEV dataset lineage is not valid")
    return dataset_hash


def _frozen_resampling_spec():
    return ResamplingSpec(
        block_origins=2,
        min_blocks_provisional=1,
        n_resamples=16,
        nominal_coverage_provisional=0.68,
        seed=S2_RESAMPLING_SEED,
        replica_scheme="single_trajectory_no_replica_resampling",
        joint_quantities=("D:Li",),
        method=MATCHED_ORIGIN_BLOCKS_V2,
    )


def run_s2_dev_coverage(*, store_root, artifact_root, code_revision):
    """Execute the frozen 64-replicate S2 DEV evidence run. Returns a summary."""
    assert_frozen_preconditions()
    if not isinstance(code_revision, str) or not code_revision:
        _fail("code revision must be explicit")
    store = CalibrationStore(store_root)
    root = Path(artifact_root).resolve()
    family = build_s1_family_for_run(store)
    dataset_hash = build_s2_dev_dataset(store, family)

    batch = materialize_calibration_dataset(
        calibration_store=store,
        dataset_manifest_hash=dataset_hash,
        artifact_root=root,
        seeds=dict(S2_DEV_SEEDS),
        code_revision=code_revision,
    )
    if batch["failed"]:
        _fail(f"S2 DEV materialization failures: {sorted(batch['failed'])}")

    seed_to_rep = {seed: rep for rep, seed in S2_DEV_SEEDS.items()}
    estimator_hashes, interval_hashes = {}, {}

    def generator(seed):
        rep = seed_to_rep[seed]
        manifest_hash = _find_replicate_manifest_hash(store, rep)
        manifest = json.loads(
            (store.root / "calibration_replicates" / f"{manifest_hash}.json").read_bytes())
        traj_hash = manifest["trajectory_artifact_hash"]
        payload = _read_json(root / "blobs" / traj_hash)
        return np.asarray(payload["positions"], dtype=np.float64)

    def make_estimator(rep):
        def estimator(positions):
            est = _find_estimator_result(root, rep)
            interval = _find_interval_record(root, est["estimator_result_hash"])
            estimate = est["result"]["self_diffusion_by_species"]["Li"]["D_m2_per_s"]
            return {"estimate": estimate,
                    "interval": interval["intervals"]["D:Li"]}
        return estimator

    manifest_hashes = {}
    for rep in S2_DEV_REPLICATES:
        manifest_hashes[rep] = _find_replicate_manifest_hash(store, rep)
        estimated = estimate_calibration_replicate(
            calibration_store=store, artifact_root=root,
            replicate_manifest_hash=manifest_hashes[rep],
            estimator_config=dict(S1_ESTIMATOR_CONFIG),
            code_revision=code_revision)
        interval = estimate_interval_for_replicate(
            calibration_store=store, artifact_root=root,
            estimator_result_hash=estimated["estimator_result_hash"],
            resampling_spec=_frozen_resampling_spec(),
            code_revision=code_revision)
        estimator_hashes[rep] = estimated["estimator_result_hash"]
        interval_hashes[rep] = interval["interval_hash"]

    _active = {}

    def generator_for_coverage(seed):
        _active["rep"] = seed_to_rep[seed]
        return generator(seed)

    def estimator_for_coverage(positions):
        return make_estimator(_active["rep"])(positions)

    seeds = sorted(S2_DEV_SEEDS.values())

    coverage = coverage_experiment(
        generator_for_coverage,
        estimator_for_coverage,
        seeds=seeds,
        truth=S1_TRUTH_D_M2_PER_S,
        nominal_coverage=S2_NOMINAL_COVERAGE,
        monte_carlo_confidence=S2_MONTE_CARLO_CONFIDENCE,
        generating_protocol={
            "scope": "S1 isotropic-Brownian scope verbatim",
            "procedure_hash": S2_PROCEDURE_HASH,
            "dataset_manifest_hash": dataset_hash,
        },
    )
    persisted = persist_coverage_summary(
        artifact_root=root,
        coverage=coverage,
        s2_procedure_hash=S2_PROCEDURE_HASH,
        s2_procedure=dict(S2_PROCEDURE),
        dataset_manifest_hash=dataset_hash,
        replicate_ids=list(S2_DEV_REPLICATES),
        seeds=dict(S2_DEV_SEEDS),
        estimator_identity={"name": ESTIMATOR_NAME, "module": ESTIMATOR_MODULE,
                            "config_hash": digest(S1_ESTIMATOR_CONFIG)},
        resampling_identity={"method": MATCHED_ORIGIN_BLOCKS_V2,
                             "spec_hash": _frozen_resampling_spec().content_hash},
        truth={"record_hash": family["truth"],
               "value": {"D_m2_per_s": S1_TRUTH_D_M2_PER_S}, "units": "m2/s"},
    )
    summary = {
        "dataset_hash": dataset_hash,
        "requested": len(S2_DEV_REPLICATES),
        "materialized": len(batch["succeeded"]),
        "estimator_results": len(estimator_hashes),
        "interval_results": len(interval_hashes),
        "coverage_hash": persisted["coverage_hash"],
        "failures": [],
    }
    print(f"dataset={summary['dataset_hash'][:12]} "
          f"requested={summary['requested']} "
          f"materialized={summary['materialized']} "
          f"estimates={summary['estimator_results']} "
          f"intervals={summary['interval_results']} "
          f"coverage={summary['coverage_hash'][:12]} failures=none")
    return summary


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--code-revision", required=True)
    args = parser.parse_args(argv)
    run_s2_dev_coverage(store_root=args.store_root, artifact_root=args.artifact_root,
                        code_revision=args.code_revision)


if __name__ == "__main__":
    main()
