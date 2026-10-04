"""Frozen S2 v2 DEV-A execution runner (calibration evidence only).

Executes the frozen 99-replicate DEV-A inventory (seeds 265..363) through
materialization and point estimation, persists one conformal score record
per replicate, then freezes the calibration package and the complete
pre-HELDOUT identity. Importing this module executes nothing; use ``main()``
or the ``__main__`` guard.

DEV-A-specific by construction: no population selector exists, so this
runner cannot become a DEV-B or non-DEV-A runner. No v1 interval machinery
is used or imported. No qualification state is produced.
Pre-flight exclusivity (refuse-before-first-write) replaces resume: any
existing DEV-A scientific evidence under the target root aborts execution.
"""
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping
from pathlib import Path

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import (
    CalibrationClass,
    CalibrationDatasetManifest,
    CalibrationPlan,
    SplitAssignment,
    TruthRecord,
)
from rudeus.science.calibration_batch import materialize_calibration_dataset
from rudeus.science.calibration_estimator import estimate_calibration_replicate
from rudeus.science.calibration_s1 import (
    S1_CODE_REVISION,
    S1_ESTIMATOR_CONFIG,
    S1_TRUTH_D_M2_PER_S,
    build_s1_plan_family,
)
from rudeus.science.calibration_s2v2 import (
    S2V2_METHOD_HASH,
    assert_frozen_v2_policy,
)
from rudeus.science.calibration_s2v2_populations import (
    S2V2_DEV_A_SEEDS,
    assert_frozen_v2_populations,
)
from rudeus.science.calibration_s2v2_stageb import (
    build_complete_pre_heldout_identity,
    build_s2v2_score_record,
    freeze_s2v2_calibration_package,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import VALID, validate_dataset, validate_plan
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside, integrity_errors, require

S2V2_DEV_A_DATASET_ID = "ds-s2v2-dev-a-99"
S2V2_DEV_A_PLAN_OBJECTIVE = "s2v2-dev-a-isotropic-brownian"
S2V2_EXPECTED_CONFIG = dict(S1_ESTIMATOR_CONFIG)

SCORE_DIR = "calibration_scores"
PACKAGE_DIR = "calibration_packages"
IDENTITY_DIR = "pre_heldout_identities"


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _read_json(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        _fail(f"unreadable evidence file {Path(path).name}: {exc}")


def check_deva_target_root_empty(*, store_root, artifact_root):
    """Pre-flight exclusivity guard: refuse if ANY DEV-A evidence exists.

    Scans replicate manifests (by DEV-A replicate_id), score records (by
    DEV-A replicate_id), estimator results attributable to DEV-A manifests,
    and any calibration-package / pre-HELDOUT-identity files. Unreadable
    files in scanned DEV-A namespaces also refuse (fail-closed: absence
    cannot be proven). Unrelated evidence is ignored. Must run before the
    first scientific write; rerun after ANY partial write refuses.
    """
    store = Path(store_root)
    root = Path(artifact_root)
    for manifest_path in sorted((store / "calibration_replicates").glob("*.json")) \
            if (store / "calibration_replicates").is_dir() else []:
        record = _read_json(manifest_path)
        if record.get("replicate_id") in S2V2_DEV_A_SEEDS:
            _fail(f"target root already holds DEV-A evidence: {manifest_path.name}")
    score_dir = root / SCORE_DIR
    if score_dir.is_dir():
        for score_path in sorted(score_dir.glob("*.json")):
            record = _read_json(score_path)
            if record.get("replicate_id") in S2V2_DEV_A_SEEDS:
                _fail(f"target root already holds DEV-A evidence: {score_path.name}")
    estimator_dir = root / "estimator_results"
    if estimator_dir.is_dir():
        for estimator_path in sorted(estimator_dir.glob("*.json")):
            try:
                record = json.loads(estimator_path.read_bytes())
            except (OSError, ValueError):
                continue  # unattributable without parsing; manifests govern
            manifest_hash = record.get("replicate_manifest_hash")
            if not manifest_hash:
                continue
            manifest_path = store / "calibration_replicates" / f"{manifest_hash}.json"
            if not manifest_path.is_file():
                continue
            manifest = _read_json(manifest_path)
            if manifest.get("replicate_id") in S2V2_DEV_A_SEEDS:
                _fail(f"target root already holds DEV-A evidence: {estimator_path.name}")
    for dirname in (PACKAGE_DIR, IDENTITY_DIR):
        directory = root / dirname
        if directory.is_dir() and any(directory.glob("*.json")):
            _fail(f"target root already holds v2 calibration evidence: {dirname}")


def build_s2v2_deva_plan(store, family):
    """Author and store the frozen ds-s2v2-dev-a-99 plan (DEV-A IDs only)."""
    plan = CalibrationPlan(
        objective=S2V2_DEV_A_PLAN_OBJECTIVE,
        scope_hashes=(family["scope"],),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",),
        truth_requirements={},
        split_rules={},
        seed_policy={},
        dev_replicate_ids=tuple(S2V2_DEV_A_SEEDS),
        heldout_replicate_ids=(),
        independence_rules={},
        selection_stopping_policy={},
        frozen_analysis_fields=("estimator",),
        code_revision=S1_CODE_REVISION,
    )
    plan_hash = store.store(plan)
    if validate_plan(store, plan_hash).status != VALID:
        _fail("S2 v2 DEV-A plan lineage is not valid")
    return plan_hash


def build_s2v2_deva_dataset(store, family):
    """Author, store, and validate the frozen ds-s2v2-dev-a-99 dataset."""
    plan_hash = build_s2v2_deva_plan(store, family)
    dataset = CalibrationDatasetManifest(
        dataset_id=S2V2_DEV_A_DATASET_ID,
        plan_hash=plan_hash,
        scope_hash=family["scope"],
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",),
        trajectory_ids=tuple(f"traj-{rep}" for rep in S2V2_DEV_A_SEEDS),
        truth_record_hashes=(family["truth"],),
        split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(family["generator"],),
        artifact_manifest_hashes=(),
        attempted_replicate_ids=tuple(S2V2_DEV_A_SEEDS),
    )
    dataset_hash = store.store(dataset)
    if validate_dataset(store, dataset_hash).status != VALID:
        _fail("S2 v2 DEV-A dataset lineage is not valid")
    return dataset_hash


def find_deva_replicate_manifest(store_root, replicate_id):
    """Resolve exactly one replicate manifest for a DEV-A ID (fail-closed).

    Returns the (content-hash, record) pair so callers never re-scan.
    """
    if replicate_id not in S2V2_DEV_A_SEEDS:
        _fail(f"replicate {replicate_id!r} is not frozen DEV-A evidence")
    found = []
    for path in sorted((Path(store_root) / "calibration_replicates").glob("*.json")):
        record = _read_json(path)
        if record.get("replicate_id") == replicate_id:
            found.append((path.stem, record))
    if len(found) != 1:
        _fail(f"replicate manifest for {replicate_id} is ambiguous or missing")
    return found[0]


def verify_manifest_for_scoring(manifest, *, replicate_id, seed, dataset_id,
                                truth_hash):
    """Verify a loaded manifest binds the frozen DEV-A lineage."""
    if manifest.get("replicate_id") != replicate_id:
        _fail("replicate manifest identity mismatch")
    if manifest.get("seed") != seed:
        _fail("replicate manifest seed mismatch")
    if manifest.get("dataset_id") != dataset_id:
        _fail("replicate manifest dataset mismatch")
    if manifest.get("split_assignment") != SplitAssignment.DEV.value:
        _fail("replicate manifest split mismatch")
    if manifest.get("truth_record_hash") != truth_hash:
        _fail("replicate manifest truth mismatch")


def find_estimator_result(artifact_root, replicate_manifest_hash):
    """Resolve exactly one estimator result for a manifest hash (fail-closed)."""
    found = []
    for path in sorted((Path(artifact_root) / "estimator_results").glob("*.json")):
        record = _read_json(path)
        if record.get("replicate_manifest_hash") == replicate_manifest_hash:
            found.append((path, record))
    if len(found) != 1:
        _fail("estimator result for DEV-A manifest is ambiguous or missing")
    return found[0][1]


def resolve_estimator_result(artifact_root, estimator_result_hash):
    """Resolve one estimator result directly by its content hash (fail-closed).

    Uses the authoritative hash returned by estimate_calibration_replicate:
    opens artifacts/estimator_results/<hash>.json, requires the resolved
    content digest to equal the requested hash, and returns the record for
    semantic verification. Missing files, malformed content, and digest
    mismatches all refuse; no directory search, no fallback.
    """
    try:
        require_hash(estimator_result_hash)
    except ValueError as exc:
        _fail(f"estimator result hash is not a content hash: {exc}")
    record = _read_json(
        Path(artifact_root) / "estimator_results" / f"{estimator_result_hash}.json")
    if not isinstance(record, dict) or digest(record) != estimator_result_hash:
        _fail("estimator result content does not match its content hash")
    return record


def verify_estimator_for_scoring(estimator, *, replicate_id, manifest_hash,
                                 expected_config, code_revision):
    """Verify an estimator result and extract finite D_hat (fail-closed).

    The persisted estimator config is the normalized form produced by the
    estimator pipeline (normalized numerics plus an explicit charge_numbers
    entry); each frozen S1 field is therefore compared by value, and the
    frozen S2 v2 scope requires no charge map (charge_numbers must be None).
    """
    if estimator.get("replicate_id") != replicate_id:
        _fail("estimator result replicate mismatch")
    if estimator.get("replicate_manifest_hash") != manifest_hash:
        _fail("estimator result manifest binding mismatch")
    stored_config = estimator.get("estimator_config")
    if not isinstance(stored_config, dict):
        _fail("estimator result has no estimator configuration")
    for key in ("lag_steps", "fit_window_ps", "selected_species", "volume_A3",
                "temperature_K", "reference_frame"):
        if stored_config.get(key) != expected_config.get(key):
            _fail("estimator result config mismatch")
    if stored_config.get("charge_numbers") is not None:
        _fail("estimator result charge map is not frozen DEV-A content")
    if estimator.get("code_revision") != code_revision:
        _fail("estimator result code revision mismatch")
    try:
        estimate = estimator["result"]["self_diffusion_by_species"]["Li"]["D_m2_per_s"]
    except (KeyError, TypeError) as exc:
        _fail(f"estimator result has no D_hat: {exc}")
    if isinstance(estimate, bool) or not isinstance(estimate, (int, float)):
        _fail("estimator D_hat is not numeric")
    if not math.isfinite(estimate):
        _fail("estimator D_hat is not finite")
    return float(estimate)


def verify_truth_value(store, truth_hash, family_truth_hash):
    """Verify the truth record is the frozen S2 v2 truth (fail-closed)."""
    if truth_hash != family_truth_hash:
        _fail("truth record is not the frozen DEV-A truth")
    record = store.retrieve(TruthRecord, truth_hash)
    value = record.value
    if not isinstance(value, Mapping) or value.get("D_m2_per_s") != S1_TRUTH_D_M2_PER_S:
        _fail("truth record value is not the frozen S2 v2 truth")
    return float(value["D_m2_per_s"])


def persist_json_record(artifact_root, dirname, record):
    """Persist a record content-addressably (append-only, readback-verified)."""
    root = Path(artifact_root).resolve()
    with integrity_errors():
        data = canonical_bytes(record)
        identity = digest(record)
        append_file(inside(root, f"{dirname}/{identity}.json"), data)
        stored = inside(root, f"{dirname}/{identity}.json").read_bytes()
        require(stored == data, f"stored {dirname} record differs from canonical")
        return identity


def run_s2v2_dev_a(*, store_root, artifact_root, code_revision, preflight_only=False):
    """Execute the frozen 99-replicate S2 v2 DEV-A evidence run."""
    assert_frozen_v2_policy()
    assert_frozen_v2_populations()
    if not isinstance(code_revision, str) or not code_revision:
        _fail("code revision must be explicit")
    check_deva_target_root_empty(store_root=store_root, artifact_root=artifact_root)
    if preflight_only:
        return {"preflight": "PASS",
                "replicates": len(S2V2_DEV_A_SEEDS),
                "method_hash": S2V2_METHOD_HASH}
    store = CalibrationStore(store_root)
    root = Path(artifact_root).resolve()
    family = build_s1_plan_family(store)
    dataset_hash = build_s2v2_deva_dataset(store, family)

    batch = materialize_calibration_dataset(
        calibration_store=store,
        dataset_manifest_hash=dataset_hash,
        artifact_root=root,
        seeds=dict(S2V2_DEV_A_SEEDS),
        code_revision=code_revision,
    )
    if batch["failed"]:
        _fail(f"S2 v2 DEV-A materialization failures: {sorted(batch['failed'])}")

    expected_config = dict(S2V2_EXPECTED_CONFIG)
    score_identities = {}
    for replicate_id in sorted(S2V2_DEV_A_SEEDS):
        manifest_hash, manifest = find_deva_replicate_manifest(store_root, replicate_id)
        verify_manifest_for_scoring(
            manifest, replicate_id=replicate_id,
            seed=S2V2_DEV_A_SEEDS[replicate_id],
            dataset_id=S2V2_DEV_A_DATASET_ID, truth_hash=family["truth"])
        estimated = estimate_calibration_replicate(
            calibration_store=store, artifact_root=root,
            replicate_manifest_hash=manifest_hash,
            estimator_config=dict(expected_config),
            code_revision=code_revision)
        estimator = resolve_estimator_result(
            artifact_root, estimated["estimator_result_hash"])
        estimate = verify_estimator_for_scoring(
            estimator, replicate_id=replicate_id,
            manifest_hash=manifest_hash, expected_config=expected_config,
            code_revision=code_revision)
        truth_value = verify_truth_value(store, manifest["truth_record_hash"],
                                         family["truth"])
        record = build_s2v2_score_record(
            replicate_id=replicate_id,
            replicate_manifest_hash=manifest_hash,
            estimator_result_hash=estimated["estimator_result_hash"],
            truth_record_hash=manifest["truth_record_hash"],
            estimate_D=estimate, truth_D=truth_value,
            code_revision=code_revision)
        score_identities[replicate_id] = persist_json_record(root, SCORE_DIR, record)

    score_records = []
    for replicate_id in sorted(S2V2_DEV_A_SEEDS):
        matches = []
        for path in sorted((root / SCORE_DIR).glob("*.json")):
            record = _read_json(path)
            if record.get("replicate_id") == replicate_id:
                matches.append(record)
        if len(matches) != 1:
            _fail(f"persisted score for {replicate_id} is ambiguous or missing")
        score_records.append(matches[0])
    package = freeze_s2v2_calibration_package(
        score_records=score_records, code_revision=code_revision)
    package_hash = persist_json_record(root, PACKAGE_DIR, package)
    identity = build_complete_pre_heldout_identity(
        calibration_package_hash=package_hash, code_revision=code_revision)
    identity_hash = persist_json_record(root, IDENTITY_DIR, identity)
    summary = {
        "dataset_hash": dataset_hash,
        "requested": len(S2V2_DEV_A_SEEDS),
        "materialized": len(batch["succeeded"]),
        "score_records": len(score_identities),
        "package_hash": package_hash,
        "identity_hash": identity_hash,
        "q_hat": package["q_hat"],
        "failures": [],
    }
    print(f"dataset={summary['dataset_hash'][:12]} "
          f"requested={summary['requested']} "
          f"materialized={summary['materialized']} "
          f"scores={summary['score_records']} "
          f"package={summary['package_hash'][:12]} "
          f"identity={summary['identity_hash'][:12]} failures=none")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    run_s2v2_dev_a(store_root=args.store_root, artifact_root=args.artifact_root,
                   code_revision=args.code_revision,
                   preflight_only=args.preflight_only)


if __name__ == "__main__":
    main()
