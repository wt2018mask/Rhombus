"""Gated S2 v2 HELDOUT execution through exact per-replicate evidence only.

Every mode starts with a fresh HELDOUT root and exact replay verification of
the persisted pre-HELDOUT no-change acknowledgment. This runner executes no
qualification statistics and emits no scientific verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from rudeus.execution.contracts import ArtifactManifest, ExecutionError
from rudeus.science.calibration import (
    CalibrationClass, CalibrationDatasetManifest, CalibrationPlan,
    CalibrationReplicateManifest, SplitAssignment,
)
from rudeus.science.calibration_batch import materialize_calibration_dataset
from rudeus.science.calibration_estimator import estimate_calibration_replicate
from rudeus.science.calibration_s1 import (
    build_s1_plan_family,
)
from rudeus.science.calibration_s2v2 import (
    S2V2_CRITERION_HASH, S2V2_METHOD, S2V2_METHOD_HASH,
    assert_frozen_v2_policy,
)
from rudeus.science.calibration_s2v2_populations import (
    S2V2_DEV_A_HASH, S2V2_DEV_B_HASH, S2V2_HELDOUT_HASH,
    S2V2_HELDOUT_RECORD, S2V2_HELDOUT_SEEDS, S2V2_POPULATIONS_HASH,
    assert_frozen_v2_populations,
)
from rudeus.science.calibration_s2v2_heldout import (
    build_s2v2_heldout_evaluation,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import VALID, validate_dataset, validate_plan
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside
from rudeus.science import pre_heldout_no_change as no_change
from rudeus.science import run_s2v2_dev_b as devb

S2V2_FROZEN_ACKNOWLEDGMENT_HASH = (
    "23fbcb20efa1d8d4f85eeca445f08a7f2fe46e235172733ce2778ef955cd221a")
S2V2_FROZEN_PACKAGE_HASH = devb.S2V2_FROZEN_PACKAGE_HASH
S2V2_FROZEN_IDENTITY_HASH = devb.S2V2_FROZEN_IDENTITY_HASH
S2V2_FROZEN_DEV_B_SUMMARY_HASH = no_change.S2V2_FROZEN_DEV_B_SUMMARY_HASH
S2V2_FROZEN_DEV_B_SUMMARY_REVISION = no_change.S2V2_FROZEN_DEV_B_CODE_REVISION
S2V2_FROZEN_Q_HAT = devb.S2V2_FROZEN_Q_HAT

DATASET_ID = "ds-s2v2-heldout-379"
PLAN_OBJECTIVE = "s2v2-heldout-isotropic-brownian-single-blind"
EVALUATION_DIR = "heldout_evaluations"
EXPECTED_ESTIMATOR_CONFIG = dict(devb.S2V2_EXPECTED_ESTIMATOR_CONFIG)


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _read_json(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        _fail(f"unreadable HELDOUT evidence file {Path(path).name}: {exc}")


def verify_pre_heldout_gate(*, dev_a_artifact_root,
                            pre_heldout_artifact_root):
    """Replay the exact acknowledgment before any HELDOUT-side write."""
    return _verified_pre_heldout_context(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)


def _verified_pre_heldout_context(*, dev_a_artifact_root,
                                  pre_heldout_artifact_root):
    assert_frozen_v2_policy()
    assert_frozen_v2_populations()
    verified = no_change.verify_pre_heldout_no_change_complete(
        dev_a_artifact_root=dev_a_artifact_root,
        artifact_root=pre_heldout_artifact_root,
        package_hash=S2V2_FROZEN_PACKAGE_HASH,
        identity_hash=S2V2_FROZEN_IDENTITY_HASH,
        dev_b_summary_hash=S2V2_FROZEN_DEV_B_SUMMARY_HASH)
    if verified.get("acknowledgment_hash") != S2V2_FROZEN_ACKNOWLEDGMENT_HASH:
        _fail("persisted pre-HELDOUT acknowledgment hash is not the frozen record")
    acknowledgment = _read_verified_pre_heldout_acknowledgment(
        pre_heldout_artifact_root=pre_heldout_artifact_root,
        acknowledgment_hash=verified["acknowledgment_hash"])
    # The verifier replays all acknowledgment fields, including decision,
    # unopened state, tuning ban, roles, populations, q_hat, and DEV-B binding.
    return {
        "acknowledgment_hash": verified["acknowledgment_hash"],
        "decision": acknowledgment["decision"],
        "heldout_status": acknowledgment["heldout_status"],
        "post_dev_b_tuning": acknowledgment["post_dev_b_tuning"],
        "dev_b_role": acknowledgment["dev_b_role"],
        "method_hash": acknowledgment["method_hash"],
        "criterion_hash": acknowledgment["criterion_hash"],
        "dev_a_population_hash": acknowledgment["dev_a_population_hash"],
        "dev_b_population_hash": acknowledgment["dev_b_population_hash"],
        "heldout_population_hash": acknowledgment["heldout_population_hash"],
        "populations_hash": acknowledgment["populations_hash"],
        "calibration_package_hash": acknowledgment["calibration_package_hash"],
        "pre_heldout_identity_hash": acknowledgment["pre_heldout_identity_hash"],
        "q_hat": acknowledgment["q_hat"],
        "dev_b_summary_hash": acknowledgment["dev_b_summary_hash"],
        "dev_b_summary_code_revision": acknowledgment["dev_b_summary_code_revision"],
    }


def _read_verified_pre_heldout_acknowledgment(*, pre_heldout_artifact_root,
                                              acknowledgment_hash):
    """Read only the exact acknowledgment already accepted by the verifier."""
    try:
        require_hash(acknowledgment_hash)
    except (ValueError, TypeError) as exc:
        _fail(f"verified acknowledgment hash is malformed: {exc}")
    root = Path(pre_heldout_artifact_root).resolve()
    path = inside(root, f"{no_change.NO_CHANGE_DIR}/{acknowledgment_hash}.json")
    try:
        data = path.read_bytes()
        record = json.loads(data)
        record_hash = digest(record)
        canonical = canonical_bytes(record)
    except (OSError, ValueError, TypeError) as exc:
        _fail(f"verified acknowledgment could not be re-read canonically: {exc}")
    if not isinstance(record, dict) or data != canonical:
        _fail("verified acknowledgment is not a canonical record")
    if record_hash != acknowledgment_hash:
        _fail("verified acknowledgment bytes differ from the verified hash")
    if acknowledgment_hash != S2V2_FROZEN_ACKNOWLEDGMENT_HASH:
        _fail("verified acknowledgment is not the frozen record")
    return record


def check_fresh_heldout_root(*, store_root, artifact_root):
    """Refuse any prior artifact namespace or evidence; never resume."""
    store = Path(store_root)
    root = Path(artifact_root)
    namespaces = (
        (store, "calibration_replicates"),
        (store, "calibration_plans"),
        (store, "calibration_datasets"),
        (store, "calibration_scopes"), (store, "truth_records"),
        (store, "generator_specs"), (store, "heldout_evaluations"),
        (root, "trajectory_manifests"), (root, "blobs"),
        (root, "attempts"), (root, "estimator_results"),
        (root, EVALUATION_DIR),
    )
    for base, name in namespaces:
        path = base / name
        if path.exists() or path.is_symlink():
            _fail(f"HELDOUT target root is not fresh: {name}")


def preflight_s2v2_heldout(*, dev_a_artifact_root,
                           pre_heldout_artifact_root, store_root,
                           artifact_root, code_revision):
    """Verify gate and freshness, with no HELDOUT writes."""
    if not isinstance(code_revision, str) or not code_revision:
        _fail("HELDOUT execution code revision must be explicit")
    gate = verify_pre_heldout_gate(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)
    check_fresh_heldout_root(store_root=store_root, artifact_root=artifact_root)
    return {**gate, "requested": len(S2V2_HELDOUT_SEEDS),
            "population_hash": S2V2_HELDOUT_HASH,
            "code_revision": code_revision, "preflight": "VERIFIED"}


def build_s2v2_heldout_plan(store, family, code_revision, *,
                            dev_a_artifact_root,
                            pre_heldout_artifact_root):
    verify_pre_heldout_gate(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)
    plan = CalibrationPlan(
        objective=PLAN_OBJECTIVE, scope_hashes=(family["scope"],),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={}, split_rules={},
        seed_policy={"inventory_hash": S2V2_HELDOUT_HASH},
        dev_replicate_ids=(), heldout_replicate_ids=tuple(S2V2_HELDOUT_SEEDS),
        independence_rules={}, selection_stopping_policy={},
        frozen_analysis_fields=("estimator",), code_revision=code_revision)
    plan_hash = store.store(plan)
    if validate_plan(store, plan_hash).status != VALID:
        _fail("S2 v2 HELDOUT plan lineage is not valid")
    return plan_hash


def build_s2v2_heldout_dataset(store, family, code_revision, *,
                               dev_a_artifact_root,
                               pre_heldout_artifact_root):
    verify_pre_heldout_gate(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)
    plan_hash = build_s2v2_heldout_plan(
        store, family, code_revision,
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)
    dataset = CalibrationDatasetManifest(
        dataset_id=DATASET_ID, plan_hash=plan_hash,
        scope_hash=family["scope"],
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",),
        trajectory_ids=tuple(f"traj-{rep}" for rep in S2V2_HELDOUT_SEEDS),
        truth_record_hashes=(family["truth"],),
        split_assignment=SplitAssignment.HELD_OUT,
        generator_spec_hashes=(family["generator"],), artifact_manifest_hashes=(),
        attempted_replicate_ids=tuple(S2V2_HELDOUT_SEEDS))
    dataset_hash = store.store(dataset)
    if validate_dataset(store, dataset_hash).status != VALID:
        _fail("S2 v2 HELDOUT dataset lineage is not valid")
    return dataset_hash


def _find_manifest(store_root, replicate_id):
    if replicate_id not in S2V2_HELDOUT_SEEDS:
        _fail(f"replicate {replicate_id!r} is not frozen HELDOUT evidence")
    matches = []
    directory = Path(store_root) / "calibration_replicates"
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        manifest = _read_json(path)
        if not isinstance(manifest, dict) or digest(manifest) != path.stem:
            _fail(f"HELDOUT manifest filename/hash mismatch: {path.name}")
        if manifest.get("replicate_id") == replicate_id:
            matches.append((path.stem, manifest))
    if len(matches) != 1:
        _fail(f"HELDOUT manifest missing or ambiguous: {replicate_id}")
    return matches[0]


def _manifest_inventory(store_root):
    """Read and hash-check every HELDOUT manifest once; reject foreign/dupes."""
    store = CalibrationStore(store_root)
    inventory = {}
    directory = Path(store_root) / "calibration_replicates"
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        data = path.read_bytes()
        record = _read_json(path)
        if not isinstance(record, dict) or digest(record) != path.stem:
            _fail(f"HELDOUT manifest filename/hash mismatch: {path.name}")
        if canonical_bytes(record) != data:
            _fail(f"HELDOUT manifest is not canonical: {path.name}")
        replicate_id = record.get("replicate_id")
        if replicate_id not in S2V2_HELDOUT_SEEDS:
            _fail(f"foreign replicate evidence in HELDOUT store: {path.name}")
        if replicate_id in inventory:
            _fail(f"duplicate HELDOUT manifest for {replicate_id}")
        try:
            stored = store.retrieve(CalibrationReplicateManifest, path.stem)
        except ExecutionError as exc:
            _fail(f"HELDOUT manifest is not verifiable: {path.name}: {exc}")
        inventory[replicate_id] = (path.stem, record)
    return inventory


def _verify_manifest(manifest, *, replicate_id, truth_hash, code_revision):
    if manifest.get("replicate_id") != replicate_id:
        _fail("HELDOUT manifest replicate identity mismatch")
    if manifest.get("seed") != S2V2_HELDOUT_SEEDS[replicate_id]:
        _fail(f"HELDOUT manifest seed mismatch: {replicate_id}")
    if manifest.get("dataset_id") != DATASET_ID:
        _fail(f"HELDOUT manifest dataset mismatch: {replicate_id}")
    if manifest.get("split_assignment") != SplitAssignment.HELD_OUT.value:
        _fail(f"HELDOUT manifest split mismatch: {replicate_id}")
    if manifest.get("truth_record_hash") != truth_hash:
        _fail(f"HELDOUT manifest truth mismatch: {replicate_id}")
    conditions = manifest.get("conditions") or {}
    if conditions.get("seed") != S2V2_HELDOUT_SEEDS[replicate_id]:
        _fail(f"HELDOUT manifest condition seed mismatch: {replicate_id}")
    if conditions.get("code_revision") != code_revision:
        _fail(f"HELDOUT manifest revision mismatch: {replicate_id}")
    try:
        require_hash(conditions.get("scope_hash"))
    except (ValueError, TypeError) as exc:
        _fail(f"HELDOUT manifest scope binding is invalid: {replicate_id}: {exc}")


def verify_heldout_materialization_complete(*, store_root, artifact_root,
                                            truth_hash, code_revision):
    """Check exact IDs, seeds, execution attempts, and trajectory bytes."""
    store, root = Path(store_root), Path(artifact_root)
    manifests = _manifest_inventory(store_root)
    if len(manifests) != 379 or set(manifests) != set(S2V2_HELDOUT_SEEDS):
        _fail("HELDOUT materialization does not cover exactly the frozen 379 IDs")
    trajectories = {}
    trajectory_dir = root / "trajectory_manifests"
    trajectory_paths = sorted(trajectory_dir.glob("*.json")) if trajectory_dir.is_dir() else []
    if len(trajectory_paths) != 379:
        _fail("HELDOUT trajectory manifest inventory is not exactly 379")
    for path in trajectory_paths:
        raw = path.read_bytes()
        item = _read_json(path)
        if not isinstance(item, dict) or digest(item) != path.stem \
                or canonical_bytes(item) != raw:
            _fail(f"HELDOUT artifact manifest hash/canonicalization mismatch: {path.name}")
        try:
            artifact = ArtifactManifest.from_dict(item)
            artifact.validate()
        except (TypeError, ValueError) as exc:
            _fail(f"HELDOUT artifact manifest is invalid: {path.name}: {exc}")
        logical_hash = artifact.logical_hash
        if logical_hash in trajectories:
            trajectories[logical_hash].append((artifact.content_hash, artifact))
        else:
            trajectories[logical_hash] = [(artifact.content_hash, artifact)]
    if len(trajectories) != 379:
        _fail("HELDOUT trajectory logical inventory is not exactly 379")
    expected_attempts = {manifest.get("execution_attempt_hash")
                         for _, manifest in manifests.values()}
    attempt_dir = root / "attempts"
    attempt_paths = sorted(attempt_dir.glob("*.json")) if attempt_dir.is_dir() else []
    if len(attempt_paths) != 379 or {path.stem for path in attempt_paths} != expected_attempts:
        _fail("HELDOUT execution-attempt inventory is not exactly 379")
    blob_dir = root / "blobs"
    blob_paths = sorted(path for path in blob_dir.iterdir() if path.is_file()) \
        if blob_dir.is_dir() else []
    if len(blob_paths) != 379 or {path.name for path in blob_paths} != set(trajectories):
        _fail("HELDOUT trajectory blob inventory is not exactly 379")
    generator_hashes, scope_hashes = set(), set()
    for replicate_id in sorted(S2V2_HELDOUT_SEEDS):
        manifest_hash, manifest = manifests[replicate_id]
        _verify_manifest(manifest, replicate_id=replicate_id,
                         truth_hash=truth_hash, code_revision=code_revision)
        attempt_hash = manifest.get("execution_attempt_hash")
        try:
            require_hash(attempt_hash)
        except (ValueError, TypeError) as exc:
            _fail(f"HELDOUT attempt hash malformed: {replicate_id}: {exc}")
        attempt = _read_json(inside(root, f"attempts/{attempt_hash}.json"))
        if digest(attempt) != attempt_hash or attempt.get("status") != "COMPLETED" \
                or attempt.get("exit_status") != 0:
            _fail(f"HELDOUT attempt did not complete: {replicate_id}")
        if (attempt.get("environment") or {}).get("code_revision") != code_revision:
            _fail(f"HELDOUT attempt revision mismatch: {replicate_id}")
        if not isinstance(attempt.get("attempt_id"), str):
            _fail(f"HELDOUT attempt identity missing: {replicate_id}")
        trajectory_hash = manifest.get("trajectory_artifact_hash")
        matches = trajectories.get(trajectory_hash, [])
        if len(matches) != 1:
            _fail(f"HELDOUT trajectory manifest missing or ambiguous: {replicate_id}")
        artifact_hash, artifact = matches[0]
        if artifact.logical_hash != trajectory_hash \
                or artifact.producer_attempt != attempt.get("attempt_id") \
                or artifact.durable_locator != f"blobs/{trajectory_hash}" \
                or attempt.get("output_manifest", {}).get("trajectory") != artifact_hash:
            _fail(f"HELDOUT attempt/artifact binding mismatch: {replicate_id}")
        data = inside(root, artifact.durable_locator).read_bytes()
        if (len(data) != artifact.size_bytes
                or hashlib.sha256(data).hexdigest() != artifact.raw_hash
                or digest(json.loads(data)) != trajectory_hash):
            _fail(f"HELDOUT trajectory content mismatch: {replicate_id}")
        trajectory = json.loads(data)
        conditions = manifest.get("conditions") or {}
        if trajectory.get("replicate_id") != replicate_id \
                or trajectory.get("seed") != S2V2_HELDOUT_SEEDS[replicate_id] \
                or trajectory.get("scope_hash") != conditions.get("scope_hash"):
            _fail(f"HELDOUT trajectory lineage mismatch: {replicate_id}")
        generator_hash = trajectory.get("generator_spec_hash")
        try:
            require_hash(generator_hash)
        except (ValueError, TypeError) as exc:
            _fail(f"HELDOUT generator binding is invalid: {replicate_id}: {exc}")
        generator_hashes.add(generator_hash)
        scope_hashes.add(conditions["scope_hash"])
    if len(generator_hashes) != 1 or len(scope_hashes) != 1:
        _fail("HELDOUT trajectory generator/scope bindings are not uniform")
    return {"materialized": 379, "replicates": sorted(S2V2_HELDOUT_SEEDS)}


def run_s2v2_heldout_materialize(*, dev_a_artifact_root,
                                 pre_heldout_artifact_root, store_root,
                                 artifact_root, code_revision):
    preflight_s2v2_heldout(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root,
        store_root=store_root, artifact_root=artifact_root,
        code_revision=code_revision)
    store = CalibrationStore(store_root)
    family = build_s1_plan_family(store)
    dataset_hash = build_s2v2_heldout_dataset(
        store, family, code_revision,
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)
    result = materialize_calibration_dataset(
        calibration_store=store, dataset_manifest_hash=dataset_hash,
        artifact_root=Path(artifact_root).resolve(),
        seeds=dict(S2V2_HELDOUT_SEEDS), code_revision=code_revision)
    if result["failed"]:
        _fail(f"S2 v2 HELDOUT materialization failures: {sorted(result['failed'])}")
    verified = verify_heldout_materialization_complete(
        store_root=store_root, artifact_root=artifact_root,
        truth_hash=family["truth"], code_revision=code_revision)
    return {"dataset_hash": dataset_hash, "materialized": verified["materialized"]}


def resolve_heldout_estimator_result(artifact_root, result_hash):
    return devb.resolve_devb_estimator_result(artifact_root, result_hash)


def verify_heldout_estimator_result(record, *, replicate_id, manifest_hash,
                                    truth_hash, code_revision):
    return devb.verify_devb_estimator_result(
        record, replicate_id=replicate_id, manifest_hash=manifest_hash,
        truth_hash=truth_hash, expected_config=EXPECTED_ESTIMATOR_CONFIG,
        code_revision=code_revision)


def verify_heldout_estimator_complete(*, store_root, artifact_root,
                                      estimator_hashes, truth_hash,
                                      code_revision):
    if set(estimator_hashes) != set(S2V2_HELDOUT_SEEDS):
        _fail("estimator hash inventory does not equal frozen HELDOUT IDs")
    store, root = CalibrationStore(store_root), Path(artifact_root)
    manifest_hashes = {}
    manifests = _manifest_inventory(store_root)
    for replicate_id in sorted(S2V2_HELDOUT_SEEDS):
        manifest_hash, manifest = manifests[replicate_id]
        _verify_manifest(manifest, replicate_id=replicate_id,
                         truth_hash=truth_hash, code_revision=code_revision)
        estimator_hash = estimator_hashes[replicate_id]
        record = resolve_heldout_estimator_result(root, estimator_hash)
        verify_heldout_estimator_result(
            record, replicate_id=replicate_id, manifest_hash=manifest_hash,
            truth_hash=truth_hash, code_revision=code_revision)
        devb.verify_devb_truth_value(store, manifest.get("truth_record_hash"), truth_hash)
        manifest_hashes[replicate_id] = manifest_hash
    results = {}
    estimator_dir = root / "estimator_results"
    for path in sorted(estimator_dir.glob("*.json")) if estimator_dir.is_dir() else []:
        record = _read_json(path)
        replicate_id = record.get("replicate_id")
        if replicate_id not in S2V2_HELDOUT_SEEDS:
            _fail(f"foreign estimator evidence in HELDOUT root: {path.name}")
        if record.get("replicate_manifest_hash") != manifest_hashes.get(replicate_id):
            _fail(f"estimator manifest binding mismatch: {path.name}")
        results.setdefault(replicate_id, []).append(path.name)
    if any(len(names) != 1 for names in results.values()) \
            or set(results) != set(S2V2_HELDOUT_SEEDS):
        _fail("estimator evidence is missing or duplicated for HELDOUT")
    return {"estimated": 379, "replicates": sorted(S2V2_HELDOUT_SEEDS)}


def run_s2v2_heldout_estimate(*, dev_a_artifact_root,
                              pre_heldout_artifact_root, store_root,
                              artifact_root, code_revision):
    run_s2v2_heldout_materialize(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root,
        store_root=store_root, artifact_root=artifact_root,
        code_revision=code_revision)
    store, root = CalibrationStore(store_root), Path(artifact_root).resolve()
    family = build_s1_plan_family(store)
    estimator_hashes = {}
    for replicate_id in sorted(S2V2_HELDOUT_SEEDS):
        manifest_hash, manifest = _find_manifest(store_root, replicate_id)
        _verify_manifest(manifest, replicate_id=replicate_id,
                         truth_hash=family["truth"], code_revision=code_revision)
        result = estimate_calibration_replicate(
            calibration_store=store, artifact_root=root,
            replicate_manifest_hash=manifest_hash,
            estimator_config=dict(EXPECTED_ESTIMATOR_CONFIG),
            code_revision=code_revision)
        result_hash = result.get("estimator_result_hash")
        record = resolve_heldout_estimator_result(root, result_hash)
        verify_heldout_estimator_result(
            record, replicate_id=replicate_id, manifest_hash=manifest_hash,
            truth_hash=family["truth"], code_revision=code_revision)
        devb.verify_devb_truth_value(store, manifest["truth_record_hash"], family["truth"])
        estimator_hashes[replicate_id] = result_hash
    return verify_heldout_estimator_complete(
        store_root=store_root, artifact_root=root,
        estimator_hashes=estimator_hashes, truth_hash=family["truth"],
        code_revision=code_revision)


def persist_heldout_evaluations(*, store_root, artifact_root,
                                estimator_hashes, truth_hash, code_revision,
                                dev_a_artifact_root,
                                pre_heldout_artifact_root):
    """Persist evaluations only after full estimator completeness succeeds."""
    context = verify_pre_heldout_gate(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)
    verify_heldout_estimator_complete(
        store_root=store_root, artifact_root=artifact_root,
        estimator_hashes=estimator_hashes, truth_hash=truth_hash,
        code_revision=code_revision)
    store, root = CalibrationStore(store_root), Path(artifact_root).resolve()
    hashes = {}
    manifests = _manifest_inventory(store_root)
    for replicate_id in sorted(S2V2_HELDOUT_SEEDS):
        manifest_hash, manifest = manifests[replicate_id]
        estimator_hash = estimator_hashes[replicate_id]
        estimator = resolve_heldout_estimator_result(root, estimator_hash)
        estimate = verify_heldout_estimator_result(
            estimator, replicate_id=replicate_id, manifest_hash=manifest_hash,
            truth_hash=truth_hash, code_revision=code_revision)
        truth = devb.verify_devb_truth_value(
            store, manifest.get("truth_record_hash"), truth_hash)
        record = build_s2v2_heldout_evaluation(
            replicate_id=replicate_id, replicate_manifest_hash=manifest_hash,
            estimator_result_hash=estimator_hash,
            truth_record_hash=manifest.get("truth_record_hash"),
            estimate_D=estimate, truth_D=truth,
            pre_heldout_acknowledgment_hash=context["acknowledgment_hash"],
            calibration_package_hash=context["calibration_package_hash"],
            q_hat=context["q_hat"], code_revision=code_revision)
        content_hash, data = digest(record), canonical_bytes(record)
        path = inside(root, f"{EVALUATION_DIR}/{content_hash}.json")
        append_file(path, data)
        try:
            stored = path.read_bytes()
            persisted = json.loads(stored)
        except (OSError, ValueError) as exc:
            _fail(f"HELDOUT evaluation re-read failed: {exc}")
        if stored != data or digest(persisted) != content_hash or persisted != record:
            _fail(f"HELDOUT evaluation persistence mismatch: {replicate_id}")
        hashes[replicate_id] = content_hash
    return hashes


def verify_heldout_evaluation_complete(*, store_root, artifact_root,
                                       estimator_hashes, truth_hash,
                                       code_revision, dev_a_artifact_root,
                                       pre_heldout_artifact_root,
                                       calibration_package_hash=None,
                                       q_hat=None,
                                       pre_heldout_acknowledgment_hash=None):
    context = verify_pre_heldout_gate(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)
    # Legacy context arguments are assertions only. The independently replayed
    # acknowledgment remains authoritative and rejects any caller substitution.
    for supplied, expected, label in (
            (calibration_package_hash, context["calibration_package_hash"],
             "calibration package"),
            (q_hat, context["q_hat"], "q_hat"),
            (pre_heldout_acknowledgment_hash, context["acknowledgment_hash"],
             "acknowledgment hash")):
        if supplied is not None and supplied != expected:
            _fail(f"caller-supplied HELDOUT {label} differs from verified acknowledgment")
    verify_heldout_estimator_complete(
        store_root=store_root, artifact_root=artifact_root,
        estimator_hashes=estimator_hashes, truth_hash=truth_hash,
        code_revision=code_revision)
    root, store = Path(artifact_root), CalibrationStore(store_root)
    directory = root / EVALUATION_DIR
    records = {}
    entries = sorted(directory.iterdir()) if directory.is_dir() else []
    if any(not path.is_file() or path.suffix != ".json" for path in entries):
        _fail("HELDOUT evaluation namespace contains an unexpected entry")
    manifests = _manifest_inventory(store_root)
    for path in entries:
        path = inside(root, f"{EVALUATION_DIR}/{path.name}")
        data = inside(root, f"{EVALUATION_DIR}/{path.name}").read_bytes()
        record = _read_json(path)
        if not isinstance(record, dict) or digest(record) != path.stem:
            _fail(f"HELDOUT evaluation filename/hash mismatch: {path.name}")
        if canonical_bytes(record) != data:
            _fail(f"HELDOUT evaluation is not canonically serialized: {path.name}")
        replicate_id = record.get("replicate_id")
        if replicate_id not in S2V2_HELDOUT_SEEDS:
            _fail(f"foreign HELDOUT evaluation: {path.name}")
        records.setdefault(replicate_id, []).append(record)
    if any(len(rows) != 1 for rows in records.values()) \
            or set(records) != set(S2V2_HELDOUT_SEEDS):
        _fail("HELDOUT evaluations do not cover exactly one record per frozen ID")
    for replicate_id in sorted(S2V2_HELDOUT_SEEDS):
        manifest_hash, manifest = manifests[replicate_id]
        estimator_hash = estimator_hashes[replicate_id]
        estimator = resolve_heldout_estimator_result(root, estimator_hash)
        estimate = verify_heldout_estimator_result(
            estimator, replicate_id=replicate_id, manifest_hash=manifest_hash,
            truth_hash=truth_hash, code_revision=code_revision)
        truth = devb.verify_devb_truth_value(
            store, manifest.get("truth_record_hash"), truth_hash)
        expected = build_s2v2_heldout_evaluation(
            replicate_id=replicate_id, replicate_manifest_hash=manifest_hash,
            estimator_result_hash=estimator_hash,
            truth_record_hash=manifest.get("truth_record_hash"),
            estimate_D=estimate, truth_D=truth,
            pre_heldout_acknowledgment_hash=context["acknowledgment_hash"],
            calibration_package_hash=context["calibration_package_hash"],
            q_hat=context["q_hat"], code_revision=code_revision)
        if records[replicate_id][0] != expected:
            _fail(f"HELDOUT evaluation replay mismatch: {replicate_id}")
    return {"evaluated": 379, "replicates": sorted(S2V2_HELDOUT_SEEDS)}


def run_s2v2_heldout_evaluate(*, dev_a_artifact_root,
                              pre_heldout_artifact_root, store_root,
                              artifact_root, code_revision):
    gate = preflight_s2v2_heldout(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root,
        store_root=store_root, artifact_root=artifact_root,
        code_revision=code_revision)
    run_s2v2_heldout_materialize(
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root,
        store_root=store_root, artifact_root=artifact_root,
        code_revision=code_revision)
    store, root = CalibrationStore(store_root), Path(artifact_root).resolve()
    family = build_s1_plan_family(store)
    estimator_hashes = {}
    for replicate_id in sorted(S2V2_HELDOUT_SEEDS):
        manifest_hash, manifest = _find_manifest(store_root, replicate_id)
        _verify_manifest(manifest, replicate_id=replicate_id,
                         truth_hash=family["truth"], code_revision=code_revision)
        result = estimate_calibration_replicate(
            calibration_store=store, artifact_root=root,
            replicate_manifest_hash=manifest_hash,
            estimator_config=dict(EXPECTED_ESTIMATOR_CONFIG),
            code_revision=code_revision)
        result_hash = result.get("estimator_result_hash")
        estimator = resolve_heldout_estimator_result(root, result_hash)
        verify_heldout_estimator_result(
            estimator, replicate_id=replicate_id, manifest_hash=manifest_hash,
            truth_hash=family["truth"], code_revision=code_revision)
        devb.verify_devb_truth_value(store, manifest["truth_record_hash"], family["truth"])
        estimator_hashes[replicate_id] = result_hash
    # All estimator results are validated before evaluation persistence starts.
    verify_heldout_estimator_complete(
        store_root=store_root, artifact_root=root,
        estimator_hashes=estimator_hashes, truth_hash=family["truth"],
        code_revision=code_revision)
    persist_heldout_evaluations(
        store_root=store_root, artifact_root=root,
        estimator_hashes=estimator_hashes, truth_hash=family["truth"],
        code_revision=code_revision,
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)
    return verify_heldout_evaluation_complete(
        store_root=store_root, artifact_root=root,
        estimator_hashes=estimator_hashes, truth_hash=family["truth"],
        code_revision=code_revision,
        dev_a_artifact_root=dev_a_artifact_root,
        pre_heldout_artifact_root=pre_heldout_artifact_root)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-a-artifact-root", required=True)
    parser.add_argument("--pre-heldout-artifact-root", required=True)
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--code-revision", required=True)
    for mode in ("preflight-only", "materialize-only", "estimate-only", "evaluate-only"):
        parser.add_argument(f"--{mode}", action="store_true")
    args = parser.parse_args(argv)
    modes = (args.preflight_only, args.materialize_only,
             args.estimate_only, args.evaluate_only)
    if sum(bool(mode) for mode in modes) != 1:
        parser.error("exactly one HELDOUT runner mode is required")
    common = dict(dev_a_artifact_root=args.dev_a_artifact_root,
                  pre_heldout_artifact_root=args.pre_heldout_artifact_root,
                  store_root=args.store_root, artifact_root=args.artifact_root,
                  code_revision=args.code_revision)
    if args.preflight_only:
        preflight_s2v2_heldout(**common)
    elif args.materialize_only:
        run_s2v2_heldout_materialize(**common)
    elif args.estimate_only:
        run_s2v2_heldout_estimate(**common)
    elif args.evaluate_only:
        run_s2v2_heldout_evaluate(**common)


if __name__ == "__main__":
    main()
