"""S2 v2 DEV-B runner: preflight, materialization, and estimation slices.

Answers two questions and nothing more: are the frozen DEV-A calibration
inputs exactly valid, and is the requested DEV-B target root clean enough
for a first execution? No plan/dataset creation, no materialization, no
estimation, no evaluation, no summary, no owner acknowledgment, no
HELD_OUT access. Importing this module executes nothing; use ``main()``
or the ``__main__`` guard (``--preflight-only`` is the sole permitted
operational behavior).

Frozen pins below (package hash, identity hash, q_hat) are the audited
real-DEV-A outputs, recorded here as resolution targets -- never learned,
never recomputed.
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
from rudeus.science.calibration_estimator import (
    ESTIMATOR_MODULE,
    ESTIMATOR_NAME,
    estimate_calibration_replicate,
)
from rudeus.science.calibration_s1 import (
    S1_CODE_REVISION,
    S1_ESTIMATOR_CONFIG,
    S1_TRUTH_D_M2_PER_S,
    build_s1_plan_family,
)
from rudeus.science.calibration_s2v2 import (
    S2V2_CRITERION_HASH,
    S2V2_METHOD,
    S2V2_METHOD_HASH,
    assert_frozen_v2_policy,
)
from rudeus.science.calibration_s2v2_populations import (
    S2V2_DEV_A_HASH,
    S2V2_DEV_B_HASH,
    S2V2_DEV_B_SEEDS,
    S2V2_HELDOUT_HASH,
    S2V2_POPULATIONS_HASH,
    assert_frozen_v2_populations,
)
from rudeus.science.calibration_s2v2_stageb import PACKAGE_STATUS
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import (
    VALID,
    validate_dataset,
    validate_plan,
)
from rudeus.science.contracts import digest, require_hash

# Audited real-DEV-A outputs (C:\s2v2-dev-a-v3 completeness audit): pinned
# as resolution targets so future runs resolve exactly this evidence. ----
S2V2_FROZEN_PACKAGE_HASH = (
    "a79fe85256a34317b7512f1a51d627653b5b9c530b5b75b0914102b1cc067a30"
)
S2V2_FROZEN_IDENTITY_HASH = (
    "1947732e97cf14659b3d2c100ba2ce8c1905aa9998ce69f95e9c466529494dba"
)
S2V2_FROZEN_Q_HAT = 7.195845360795594e-10

# DEV-A artifact namespaces (mirror the DEV-A runner layout; literals keep
# this module free of execution-pipeline imports).
DEV_A_PACKAGE_DIR = "calibration_packages"
DEV_A_IDENTITY_DIR = "pre_heldout_identities"

# DEV-B target-root namespaces scanned by preflight. ------------------------
DEV_B_EVALUATION_DIR = "dev_b_evaluations"
DEV_B_SUMMARY_DIR = "dev_b_summaries"


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _read_json(path):
    try:
        return json.loads(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        _fail(f"unreadable evidence file {Path(path).name}: {exc}")


def resolve_s2v2_calibration_package(*, dev_a_artifact_root,
                                     package_hash=S2V2_FROZEN_PACKAGE_HASH):
    """Resolve and verify a DEV-A calibration package (read-only).

    Opens artifacts/calibration_packages/<hash>.json, requires digest
    equality, then enforces the frozen package contract: method, criterion,
    and DEV-A population bindings; n == 99; k == 90; target 0.90; exact
    frozen q_hat. The default hash pins the audited real package; callers
    may supply an explicit hash (validated identically) for testing. No
    writes. q_hat is consumed, never derived.
    """
    record = _read_json(
        Path(dev_a_artifact_root) / DEV_A_PACKAGE_DIR / f"{package_hash}.json")
    if not isinstance(record, dict) or digest(record) != package_hash:
        _fail("calibration package content does not match its content hash")
    if record.get("method_hash") != S2V2_METHOD_HASH:
        _fail("calibration package binds a foreign method")
    if record.get("criterion_hash") != S2V2_CRITERION_HASH:
        _fail("calibration package binds a foreign criterion")
    if record.get("dev_a_population_hash") != S2V2_DEV_A_HASH:
        _fail("calibration package binds a foreign population")
    if record.get("n") != 99:
        _fail("calibration package replicate count is not frozen DEV-A")
    if record.get("k") != 90:
        _fail("calibration package conformal rank is not frozen")
    if record.get("target_coverage") != 0.90:
        _fail("calibration package target coverage is not frozen")
    if record.get("q_hat") != S2V2_FROZEN_Q_HAT:
        _fail("calibration package q_hat is not the frozen value")
    if record.get("package_status") != PACKAGE_STATUS:
        _fail("calibration package status is not frozen non-qualification")
    estimator = record.get("estimator")
    expected_estimator = S2V2_METHOD.get("estimator", {})
    if not isinstance(estimator, dict) or any(
            estimator.get(key) != expected_estimator.get(key)
            for key in ("name", "module", "config_hash")):
        _fail("calibration package estimator binding disagrees with method")
    for key in ("truth", "scope", "generator_protocol"):
        if record.get(key) != S2V2_METHOD.get(key):
            _fail(f"calibration package {key} binding disagrees with method")
    revision = record.get("code_revision")
    if not isinstance(revision, str) or not revision:
        _fail("calibration package code revision is not valid provenance")
    return record


def resolve_s2v2_pre_heldout_identity(*, dev_a_artifact_root,
                                      identity_hash=S2V2_FROZEN_IDENTITY_HASH):
    """Resolve and verify a pre-HELDOUT identity record (read-only).

    Requires digest equality, all six frozen population/method/criterion/
    package bindings, and phase {frozen, not-evaluated, unopened}. The
    default hash pins the audited real identity; explicit hashes are
    validated identically. No mutation, no writes.
    """
    record = _read_json(
        Path(dev_a_artifact_root) / DEV_A_IDENTITY_DIR / f"{identity_hash}.json")
    if not isinstance(record, dict) or digest(record) != identity_hash:
        _fail("pre-HELDOUT identity content does not match its content hash")
    for key, expected in (
            ("method_hash", S2V2_METHOD_HASH),
            ("criterion_hash", S2V2_CRITERION_HASH),
            ("dev_a_population_hash", S2V2_DEV_A_HASH),
            ("dev_b_population_hash", S2V2_DEV_B_HASH),
            ("heldout_population_hash", S2V2_HELDOUT_HASH)):
        if record.get(key) != expected:
            _fail(f"pre-HELDOUT identity binding mismatch: {key}")
    # The calibration_package_hash binding is verified by
    # verify_s2v2_devb_inputs against the resolved package itself, not here.
    try:
        require_hash(record.get("calibration_package_hash"))
    except (ValueError, TypeError, AttributeError) as exc:
        _fail(f"pre-HELDOUT identity package binding malformed: {exc}")
    if record.get("populations_hash") != S2V2_POPULATIONS_HASH:
        _fail("pre-HELDOUT identity combined population binding mismatch")
    revision = record.get("code_revision")
    if not isinstance(revision, str) or not revision:
        _fail("pre-HELDOUT identity code revision is not valid provenance")
    phase = record.get("phase")
    if not isinstance(phase, dict) or phase.get("calibration") != "frozen" \
            or phase.get("dev_b") != "not-evaluated" \
            or phase.get("heldout") != "unopened":
        _fail("pre-HELDOUT identity phase is not frozen pre-DEV-B state")
    return record


def verify_s2v2_devb_inputs(package, identity):
    """Cross-verify resolved package and identity (pure, read-only).

    Requires identity.calibration_package_hash == digest(package) with all
    frozen bindings agreeing. Returns a small immutable summary for the
    future runner; it is not scientific evidence and not a verdict.
    """
    package_hash = digest(package)
    if identity.get("calibration_package_hash") != package_hash:
        _fail("pre-HELDOUT identity does not bind the resolved package")
    for key, expected in (
            ("method_hash", S2V2_METHOD_HASH),
            ("criterion_hash", S2V2_CRITERION_HASH),
            ("dev_a_population_hash", S2V2_DEV_A_HASH)):
        if package.get(key) != expected or identity.get(key) != expected:
            _fail(f"package/identity binding mismatch: {key}")
    if package.get("q_hat") != S2V2_FROZEN_Q_HAT:
        _fail("resolved package q_hat is not the frozen value")
    if identity.get("code_revision") != package.get("code_revision"):
        _fail("pre-HELDOUT identity revision does not match package revision")
    return {
        "package_hash": package_hash,
        "identity_hash": digest(identity),
        "q_hat": package["q_hat"],
        "dev_b_population_hash": S2V2_DEV_B_HASH,
        "frozen_dev_a_code_revision": package.get("code_revision"),
        "preflight": "INPUTS-VERIFIED",
    }


def check_devb_target_root_empty(*, store_root, artifact_root):
    """Fresh-root exclusivity guard for DEV-B (read-only, no writes).

    Conservative policy for greenfield DEV-B roots: ANY *.json file under
    the scanned evidence namespaces refuses (replicate manifests, estimator
    results, DEV-B evaluations/summaries, calibration packages, pre-HELDOUT
    identities), as does any unreadable file there (absence unprovable).
    Absent roots and genuinely empty directories pass. No resume, no
    skip-complete, no overwrite, no cleanup, no directory creation.
    """
    store = Path(store_root)
    root = Path(artifact_root)
    for dirname in ("calibration_replicates",):
        directory = store / dirname
        if directory.is_dir() and any(directory.glob("*.json")):
            _fail(f"target root already holds evidence: store/{dirname}")
    for dirname in ("estimator_results", DEV_B_EVALUATION_DIR,
                    DEV_B_SUMMARY_DIR, DEV_A_PACKAGE_DIR, DEV_A_IDENTITY_DIR):
        directory = root / dirname
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            _read_json(path)  # fail-closed on unreadable content
            _fail(f"target root already holds evidence: {dirname}/{path.name}")


def preflight_s2v2_dev_b(*, dev_a_artifact_root, store_root, artifact_root,
                         code_revision):
    """DEV-B preflight orchestration (read-only; zero scientific writes)."""
    assert_frozen_v2_policy()
    assert_frozen_v2_populations()
    if not isinstance(code_revision, str) or not code_revision:
        _fail("code revision must be explicit")
    package = resolve_s2v2_calibration_package(
        dev_a_artifact_root=dev_a_artifact_root,
        package_hash=S2V2_FROZEN_PACKAGE_HASH)
    identity = resolve_s2v2_pre_heldout_identity(
        dev_a_artifact_root=dev_a_artifact_root,
        identity_hash=S2V2_FROZEN_IDENTITY_HASH)
    verified = verify_s2v2_devb_inputs(package, identity)
    check_devb_target_root_empty(store_root=store_root, artifact_root=artifact_root)
    return {**verified,
            "dev_b_replicates": len(S2V2_DEV_B_SEEDS),
            "code_revision": code_revision,
            "preflight": "PASS"}


S2V2_DEV_B_DATASET_ID = "ds-s2v2-dev-b-114"
S2V2_DEV_B_PLAN_OBJECTIVE = "s2v2-dev-b-isotropic-brownian"
S2V2_EXPECTED_ESTIMATOR_CONFIG = dict(S1_ESTIMATOR_CONFIG)


def build_s2v2_devb_plan(store, family):
    """Author and store the frozen ds-s2v2-dev-b-114 plan (DEV-B IDs only)."""
    plan = CalibrationPlan(
        objective=S2V2_DEV_B_PLAN_OBJECTIVE,
        scope_hashes=(family["scope"],),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",),
        truth_requirements={},
        split_rules={},
        seed_policy={},
        dev_replicate_ids=tuple(S2V2_DEV_B_SEEDS),
        heldout_replicate_ids=(),
        independence_rules={},
        selection_stopping_policy={},
        frozen_analysis_fields=("estimator",),
        code_revision=S1_CODE_REVISION,
    )
    plan_hash = store.store(plan)
    if validate_plan(store, plan_hash).status != VALID:
        _fail("S2 v2 DEV-B plan lineage is not valid")
    return plan_hash


def build_s2v2_devb_dataset(store, family):
    """Author, store, and validate the frozen ds-s2v2-dev-b-114 dataset."""
    plan_hash = build_s2v2_devb_plan(store, family)
    dataset = CalibrationDatasetManifest(
        dataset_id=S2V2_DEV_B_DATASET_ID,
        plan_hash=plan_hash,
        scope_hash=family["scope"],
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
        parameter_cell_ids=("cell-a",),
        trajectory_ids=tuple(f"traj-{rep}" for rep in S2V2_DEV_B_SEEDS),
        truth_record_hashes=(family["truth"],),
        split_assignment=SplitAssignment.DEV,
        generator_spec_hashes=(family["generator"],),
        artifact_manifest_hashes=(),
        attempted_replicate_ids=tuple(S2V2_DEV_B_SEEDS),
    )
    dataset_hash = store.store(dataset)
    if validate_dataset(store, dataset_hash).status != VALID:
        _fail("S2 v2 DEV-B dataset lineage is not valid")
    return dataset_hash


def verify_devb_materialization_complete(*, store_root, artifact_root,
                                        dataset_id, truth_hash, code_revision):
    """Re-read persisted materialization evidence for all 114 DEV-B units.

    Requires exactly one replicate manifest per frozen ID with exact seed,
    dataset, split, and truth bindings; one COMPLETED exit-0 attempt with
    matching run revision; and a hash-verified trajectory manifest + blob.
    Content hashes (never filenames alone) are authoritative. Fail-closed.
    """
    import hashlib

    store = Path(store_root)
    root = Path(artifact_root)
    seen_ids = set()
    for path in sorted((store / "calibration_replicates").glob("*.json")):
        record = _read_json(path)
        replicate_id = record.get("replicate_id")
        if replicate_id not in S2V2_DEV_B_SEEDS:
            _fail(f"unexpected replicate evidence in DEV-B root: {path.name}")
        seen_ids.add(replicate_id)
    for replicate_id in sorted(S2V2_DEV_B_SEEDS):
        found = []
        for path in sorted((store / "calibration_replicates").glob("*.json")):
            record = _read_json(path)
            if record.get("replicate_id") == replicate_id:
                found.append((path.stem, record))
        if len(found) != 1:
            _fail(f"DEV-B replicate manifest for {replicate_id} is ambiguous "
                  "or missing")
        manifest_hash, manifest = found[0]
        if manifest.get("seed") != S2V2_DEV_B_SEEDS[replicate_id]:
            _fail(f"DEV-B replicate manifest seed mismatch: {replicate_id}")
        if manifest.get("dataset_id") != dataset_id:
            _fail(f"DEV-B replicate manifest dataset mismatch: {replicate_id}")
        if manifest.get("split_assignment") != SplitAssignment.DEV.value:
            _fail(f"DEV-B replicate manifest split mismatch: {replicate_id}")
        if manifest.get("truth_record_hash") != truth_hash:
            _fail(f"DEV-B replicate manifest truth mismatch: {replicate_id}")
        if (manifest.get("conditions") or {}).get("code_revision") != code_revision:
            _fail(f"DEV-B replicate manifest revision mismatch: {replicate_id}")
        attempt_hash = manifest.get("execution_attempt_hash")
        attempt_path = root / "attempts" / f"{attempt_hash}.json"
        attempt = _read_json(attempt_path)
        if digest(attempt) != attempt_hash:
            _fail(f"DEV-B attempt content mismatch: {replicate_id}")
        if attempt.get("status") != "COMPLETED" or attempt.get("exit_status") != 0:
            _fail(f"DEV-B attempt did not complete: {replicate_id}")
        if (attempt.get("environment") or {}).get("code_revision") != code_revision:
            _fail(f"DEV-B attempt revision mismatch: {replicate_id}")
        trajectory_hash = manifest.get("trajectory_artifact_hash")
        traj_found = []
        for path in sorted((root / "trajectory_manifests").glob("*.json")):
            candidate = _read_json(path)
            if candidate.get("logical_hash") == trajectory_hash:
                traj_found.append(candidate)
        if len(traj_found) != 1:
            _fail(f"DEV-B trajectory manifest ambiguous or missing: {replicate_id}")
        blob = root / "blobs" / trajectory_hash
        try:
            data = blob.read_bytes()
        except OSError as exc:
            _fail(f"DEV-B trajectory blob missing: {replicate_id}: {exc}")
        if hashlib.sha256(data).hexdigest() != traj_found[0].get("raw_hash"):
            _fail(f"DEV-B trajectory blob hash mismatch: {replicate_id}")
        if digest(json.loads(data)) != trajectory_hash:
            _fail(f"DEV-B trajectory logical hash mismatch: {replicate_id}")
    return {"materialized": len(S2V2_DEV_B_SEEDS),
            "replicates": sorted(S2V2_DEV_B_SEEDS)}


def run_s2v2_dev_b_materialize(*, dev_a_artifact_root, store_root,
                               artifact_root, code_revision):
    """Preflight + frozen DEV-B plan/dataset + 114 materialization + verify.

    Stops after materialization completeness verification. No estimator
    execution, no evaluation, no summary, no acknowledgment, no HELD_OUT.
    """
    verified = preflight_s2v2_dev_b(
        dev_a_artifact_root=dev_a_artifact_root, store_root=store_root,
        artifact_root=artifact_root, code_revision=code_revision)
    store = CalibrationStore(store_root)
    root = Path(artifact_root).resolve()
    family = build_s1_plan_family(store)
    dataset_hash = build_s2v2_devb_dataset(store, family)
    batch = materialize_calibration_dataset(
        calibration_store=store,
        dataset_manifest_hash=dataset_hash,
        artifact_root=root,
        seeds=dict(S2V2_DEV_B_SEEDS),
        code_revision=code_revision,
    )
    if batch["failed"]:
        _fail(f"S2 v2 DEV-B materialization failures: {sorted(batch['failed'])}")
    materialized = verify_devb_materialization_complete(
        store_root=store_root, artifact_root=root,
        dataset_id=S2V2_DEV_B_DATASET_ID, truth_hash=family["truth"],
        code_revision=code_revision)
    summary = {
        "dataset_hash": dataset_hash,
        "requested": len(S2V2_DEV_B_SEEDS),
        "materialized": materialized["materialized"],
        "package_hash": verified["package_hash"],
        "failures": [],
    }
    print(f"dataset={summary['dataset_hash'][:12]} "
          f"requested={summary['requested']} "
          f"materialized={summary['materialized']} failures=none")
    return summary


def find_devb_replicate_manifest(store_root, replicate_id):
    """Resolve exactly one replicate manifest for a DEV-B ID (fail-closed).

    Returns the (content-hash, record) pair so callers never re-scan.
    """
    if replicate_id not in S2V2_DEV_B_SEEDS:
        _fail(f"replicate {replicate_id!r} is not frozen DEV-B evidence")
    found = []
    for path in sorted((Path(store_root) / "calibration_replicates").glob("*.json")):
        record = _read_json(path)
        if record.get("replicate_id") == replicate_id:
            found.append((path.stem, record))
    if len(found) != 1:
        _fail(f"replicate manifest for {replicate_id} is ambiguous or missing")
    return found[0]


def verify_devb_manifest_for_estimate(manifest, *, replicate_id, seed,
                                      dataset_id, truth_hash):
    """Verify a loaded manifest binds the frozen DEV-B lineage."""
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


def resolve_devb_estimator_result(artifact_root, estimator_result_hash):
    """Resolve one estimator result directly by its content hash (fail-closed).

    Uses the authoritative hash returned by estimate_calibration_replicate:
    opens artifacts/estimator_results/<hash>.json, requires the resolved
    content digest to equal the requested hash. Missing files, malformed
    content, and digest mismatches all refuse; no directory search and no
    manifest-hash lookup (the historical DEV-A ambiguity bug class).
    """
    try:
        require_hash(estimator_result_hash)
    except ValueError as exc:
        _fail(f"estimator result hash is not a content hash: {exc}")
    record = _read_json(
        Path(artifact_root) / "estimator_results" / f"{estimator_result_hash}.json")
    try:
        content_hash = digest(record) if isinstance(record, dict) else None
    except ValueError:
        content_hash = None
    if content_hash != estimator_result_hash:
        _fail("estimator result content does not match its content hash")
    return record


def verify_devb_estimator_result(estimator, *, replicate_id, manifest_hash,
                                 truth_hash, expected_config, code_revision):
    """Verify an estimator result and extract finite D_hat (fail-closed).

    Requires exact replicate/manifest/truth bindings, the frozen estimator
    name, per-field frozen S1 config (normalized pipeline form carries an
    explicit charge_numbers entry, which must be None here), the run code
    revision, and a finite D_hat.
    """
    if estimator.get("replicate_id") != replicate_id:
        _fail("estimator result replicate mismatch")
    if estimator.get("replicate_manifest_hash") != manifest_hash:
        _fail("estimator result manifest binding mismatch")
    if estimator.get("truth_record_hash") != truth_hash:
        _fail("estimator result truth binding mismatch")
    if estimator.get("estimator") != ESTIMATOR_NAME:
        _fail("estimator result estimator mismatch")
    if estimator.get("estimator_module") != ESTIMATOR_MODULE:
        _fail("estimator result estimator module mismatch")
    stored_config = estimator.get("estimator_config")
    if not isinstance(stored_config, dict):
        _fail("estimator result has no estimator configuration")
    for key in ("lag_steps", "fit_window_ps", "selected_species", "volume_A3",
                "temperature_K", "reference_frame"):
        if stored_config.get(key) != expected_config.get(key):
            _fail("estimator result config mismatch")
    if stored_config.get("charge_numbers") is not None:
        _fail("estimator result charge map is not frozen DEV-B content")
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


def verify_devb_truth_value(store, truth_hash, family_truth_hash):
    """Verify the truth record is the frozen S2 v2 truth (fail-closed).

    Accepts the repository's frozen Mapping representation (never requires
    a concrete dict) and requires D_true == 1e-9 m2/s through the
    content-hash-valid resolved record.
    """
    if truth_hash != family_truth_hash:
        _fail("truth record is not the frozen DEV-B truth")
    record = store.retrieve(TruthRecord, truth_hash)
    value = record.value
    if not isinstance(value, Mapping) or value.get("D_m2_per_s") != S1_TRUTH_D_M2_PER_S:
        _fail("truth record value is not the frozen S2 v2 truth")
    return float(value["D_m2_per_s"])


def verify_devb_estimator_complete(*, store_root, artifact_root,
                                   estimator_hashes, dataset_id, truth_hash,
                                   code_revision):
    """Re-verify estimator evidence for all 114 DEV-B replicates (fail-closed).

    For each frozen ID: exactly one replicate manifest, exact returned-hash
    resolution of its estimator result, full semantic verification
    (replicate/manifest/truth/name/config/revision/finite D_hat), and frozen
    truth value. A directory-wide sweep then requires every estimator file
    to belong to a frozen DEV-B replicate with a matching manifest binding
    (exactly one per replicate): foreign or duplicate logical results
    refuse. No manifest-hash search is used for resolution anywhere.
    """
    if set(estimator_hashes) != set(S2V2_DEV_B_SEEDS):
        _fail("estimator hash inventory does not equal the frozen DEV-B set")
    store = CalibrationStore(store_root)
    store_path = Path(store_root)
    root = Path(artifact_root)
    manifest_hashes = {}
    for replicate_id in sorted(S2V2_DEV_B_SEEDS):
        found = []
        for path in sorted((store_path / "calibration_replicates").glob("*.json")):
            record = _read_json(path)
            if record.get("replicate_id") == replicate_id:
                found.append((path.stem, record))
        if len(found) != 1:
            _fail(f"DEV-B replicate manifest for {replicate_id} is ambiguous "
                  "or missing")
        manifest_hash, manifest = found[0]
        if manifest.get("seed") != S2V2_DEV_B_SEEDS[replicate_id]:
            _fail(f"DEV-B replicate manifest seed mismatch: {replicate_id}")
        if manifest.get("dataset_id") != dataset_id:
            _fail(f"DEV-B replicate manifest dataset mismatch: {replicate_id}")
        estimator_hash = estimator_hashes[replicate_id]
        estimator = resolve_devb_estimator_result(root, estimator_hash)
        verify_devb_estimator_result(
            estimator, replicate_id=replicate_id, manifest_hash=manifest_hash,
            truth_hash=truth_hash, expected_config=S2V2_EXPECTED_ESTIMATOR_CONFIG,
            code_revision=code_revision)
        verify_devb_truth_value(store, manifest.get("truth_record_hash"),
                                truth_hash)
        manifest_hashes[replicate_id] = manifest_hash
    per_replicate = {}
    for path in sorted((root / "estimator_results").glob("*.json")):
        record = _read_json(path)
        replicate_id = record.get("replicate_id")
        if replicate_id not in S2V2_DEV_B_SEEDS:
            _fail(f"foreign estimator evidence in DEV-B root: {path.name}")
        if record.get("replicate_manifest_hash") != manifest_hashes.get(replicate_id):
            _fail(f"estimator result manifest binding mismatch: {path.name}")
        per_replicate.setdefault(replicate_id, []).append(path.name)
    for replicate_id, names in per_replicate.items():
        if len(names) != 1:
            _fail(f"duplicate estimator evidence for {replicate_id}")
    if set(per_replicate) != set(S2V2_DEV_B_SEEDS):
        _fail("estimator evidence does not cover the frozen DEV-B set")
    return {"estimated": len(S2V2_DEV_B_SEEDS),
            "replicates": sorted(S2V2_DEV_B_SEEDS)}


def run_s2v2_dev_b_estimate(*, dev_a_artifact_root, store_root,
                            artifact_root, code_revision):
    """Preflight + materialize + estimate + estimator completeness + stop.

    Stops after estimator completeness verification. No interval
    application, no evaluation records, no coverage/bias statistics, no
    summary, no owner acknowledgment, no HELD_OUT. q_hat plays no role.
    """
    run_s2v2_dev_b_materialize(
        dev_a_artifact_root=dev_a_artifact_root, store_root=store_root,
        artifact_root=artifact_root, code_revision=code_revision)
    store = CalibrationStore(store_root)
    root = Path(artifact_root).resolve()
    family = build_s1_plan_family(store)
    expected_config = dict(S2V2_EXPECTED_ESTIMATOR_CONFIG)
    estimator_hashes = {}
    for replicate_id in sorted(S2V2_DEV_B_SEEDS):
        manifest_hash, manifest = find_devb_replicate_manifest(
            store_root, replicate_id)
        verify_devb_manifest_for_estimate(
            manifest, replicate_id=replicate_id,
            seed=S2V2_DEV_B_SEEDS[replicate_id],
            dataset_id=S2V2_DEV_B_DATASET_ID, truth_hash=family["truth"])
        estimated = estimate_calibration_replicate(
            calibration_store=store, artifact_root=root,
            replicate_manifest_hash=manifest_hash,
            estimator_config=dict(expected_config),
            code_revision=code_revision)
        estimator = resolve_devb_estimator_result(
            artifact_root, estimated["estimator_result_hash"])
        verify_devb_estimator_result(
            estimator, replicate_id=replicate_id, manifest_hash=manifest_hash,
            truth_hash=family["truth"], expected_config=expected_config,
            code_revision=code_revision)
        verify_devb_truth_value(store, manifest["truth_record_hash"],
                                family["truth"])
        estimator_hashes[replicate_id] = estimated["estimator_result_hash"]
    estimated = verify_devb_estimator_complete(
        store_root=store_root, artifact_root=root,
        estimator_hashes=estimator_hashes,
        dataset_id=S2V2_DEV_B_DATASET_ID, truth_hash=family["truth"],
        code_revision=code_revision)
    summary = {
        "requested": len(S2V2_DEV_B_SEEDS),
        "estimated": estimated["estimated"],
        "failures": [],
    }
    print(f"requested={summary['requested']} "
          f"estimated={summary['estimated']} failures=none")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-a-artifact-root", required=True)
    parser.add_argument("--store-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--code-revision", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--materialize-only", action="store_true")
    parser.add_argument("--estimate-only", action="store_true")
    args = parser.parse_args(argv)
    modes = (args.preflight_only, args.materialize_only, args.estimate_only)
    if sum(bool(mode) for mode in modes) != 1:
        parser.error("exactly one of --preflight-only, --materialize-only, "
                     "or --estimate-only is required")
    if args.preflight_only:
        preflight_s2v2_dev_b(dev_a_artifact_root=args.dev_a_artifact_root,
                             store_root=args.store_root,
                             artifact_root=args.artifact_root,
                             code_revision=args.code_revision)
        return
    if args.materialize_only:
        run_s2v2_dev_b_materialize(
            dev_a_artifact_root=args.dev_a_artifact_root,
            store_root=args.store_root, artifact_root=args.artifact_root,
            code_revision=args.code_revision)
        return
    run_s2v2_dev_b_estimate(
        dev_a_artifact_root=args.dev_a_artifact_root,
        store_root=args.store_root, artifact_root=args.artifact_root,
        code_revision=args.code_revision)


if __name__ == "__main__":
    main()
