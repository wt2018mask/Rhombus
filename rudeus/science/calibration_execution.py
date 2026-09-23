"""Commit A: G.1 calibration task construction and lineage validation.
Commit B: Brownian single-replicate materialization with artifact/attempt
binding.

Materialization only: runs the declared generator, persists the trajectory
artifact, execution attempt, and replicate manifest with hash-bound
provenance. No estimator logic, no uncertainty, no verdicts, no
qualification. A completed replicate means the computation completed and
was durably bound — nothing about scientific validity.

Calibration tasks intentionally sit beside the P3 follow-up execution path
(``FollowupRequest`` / ``generate_followups`` / ``execute_local``); this
module never calls that path and the task stage stays ``CALIBRATION``.
"""

from __future__ import annotations

import hashlib
import os
import platform
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from rudeus.execution.contracts import (
    ArtifactManifest,
    ExecutionAttempt,
    ExecutionError,
    TaskSpec,
    classify_failure,
)
from rudeus.science.calibration import (
    CalibrationClass,
    CalibrationDatasetManifest,
    CalibrationPlan,
    CalibrationReplicateManifest,
    CalibrationScope,
    GeneratorSpec,
    SplitAssignment,
    TruthRecord,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.calibration_validation import (
    VALID,
    validate_dataset,
    validate_plan,
)
from rudeus.science.contracts import canonical_bytes, digest, require_hash
from rudeus.science.evidence import append_file, inside, integrity_errors
from rudeus.science.synthetic import brownian


CALIBRATION_STAGE = "CALIBRATION"
CALIBRATION_OUTPUTS = ("trajectory",)

_CONFIG_KEYS = (
    "plan_hash",
    "scope_hash",
    "dataset_manifest_hash",
    "generator_spec_hash",
    "truth_record_hash",
    "replicate_id",
    "parameter_cell_id",
    "split_assignment",
    "seed",
)


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def _require_nonempty_str(value, name):
    if not isinstance(value, str) or not value:
        _fail(f"calibration task {name} must be a nonempty string")


def _normalize_split(split_assignment):
    if isinstance(split_assignment, SplitAssignment):
        return split_assignment.value
    if split_assignment in (SplitAssignment.DEV.value, SplitAssignment.HELD_OUT.value):
        return split_assignment
    _fail("calibration task split_assignment must be DEV or HELD_OUT")


def build_calibration_task(
    *,
    plan_hash,
    scope_hash,
    dataset_manifest_hash,
    generator_spec_hash,
    truth_record_hash,
    replicate_id,
    parameter_cell_id,
    split_assignment,
    seed,
    code_revision,
) -> TaskSpec:
    """Pure constructor for a single-replicate calibration ``TaskSpec``.

    Binds the complete G.1 lineage through the existing canonical identity:
    ``protocol_hash`` is the calibration scope hash; the remaining lineage
    lives in ``config`` (hashed via ``config_hash``) and ``input_artifact_hashes``.
    No store access, no timestamps, no random IDs.
    """
    for name, value in (
            ("plan_hash", plan_hash), ("scope_hash", scope_hash),
            ("dataset_manifest_hash", dataset_manifest_hash),
            ("generator_spec_hash", generator_spec_hash),
            ("truth_record_hash", truth_record_hash)):
        try:
            require_hash(value)
        except ValueError:
            _fail(f"calibration task {name} must be a content hash")
    _require_nonempty_str(replicate_id, "replicate_id")
    _require_nonempty_str(parameter_cell_id, "parameter_cell_id")
    split = _normalize_split(split_assignment)
    if isinstance(seed, bool) or not isinstance(seed, int):
        _fail("calibration task seed must be an integer")
    _require_nonempty_str(code_revision, "code_revision")
    return TaskSpec(
        candidate_id=replicate_id,
        stage=CALIBRATION_STAGE,
        protocol_hash=scope_hash,
        config={
            "plan_hash": plan_hash,
            "scope_hash": scope_hash,
            "dataset_manifest_hash": dataset_manifest_hash,
            "generator_spec_hash": generator_spec_hash,
            "truth_record_hash": truth_record_hash,
            "replicate_id": replicate_id,
            "parameter_cell_id": parameter_cell_id,
            "split_assignment": split,
            "seed": seed,
        },
        input_artifact_hashes=(
            plan_hash,
            scope_hash,
            dataset_manifest_hash,
            generator_spec_hash,
            truth_record_hash,
        ),
        dependencies=(),
        code_revision=code_revision,
        resource_requirements={},
        expected_outputs=CALIBRATION_OUTPUTS,
        retry_policy={},
        temperature=None,
        replica=None,
        seed=seed,
        provenance=None,
    )


def _config(task):
    if not isinstance(task, TaskSpec):
        _fail("calibration lineage requires a TaskSpec")
    config = dict(task.config)
    for key in _CONFIG_KEYS:
        if key not in config:
            _fail(f"calibration task config is missing {key}")
    return config


def validate_materialization_lineage(store: CalibrationStore, task: TaskSpec) -> None:
    """Validate a calibration task's frozen G.1 lineage (integrity only).

    Every failure raises ``ExecutionError`` with ``INTEGRITY``. No scientific
    verdict is produced. ``INCOMPLETE`` validator outcomes are integrity
    failures here, never executable lineage.
    """
    if not isinstance(store, CalibrationStore):
        _fail("calibration lineage requires a CalibrationStore")
    config = _config(task)
    if set(config) != set(_CONFIG_KEYS):
        _fail("calibration task config carries unexpected keys")
    if task.stage != CALIBRATION_STAGE:
        _fail("calibration task stage must be CALIBRATION")
    if task.protocol_hash != config["scope_hash"]:
        _fail("calibration task protocol must bind the scope hash")

    plan_hash = config["plan_hash"]
    if validate_plan(store, plan_hash).status != VALID:
        _fail("calibration plan lineage is not valid")
    try:
        plan = store.retrieve(CalibrationPlan, plan_hash)
    except ExecutionError:
        _fail("calibration plan lineage is not valid")

    scope_hash = config["scope_hash"]
    if scope_hash not in set(plan.scope_hashes):
        _fail("calibration scope is not part of the selected plan")
    try:
        scope = store.retrieve(CalibrationScope, scope_hash)
    except ExecutionError:
        _fail("calibration scope lineage is not valid")

    dataset_hash = config["dataset_manifest_hash"]
    if validate_dataset(store, dataset_hash, plan=plan).status != VALID:
        _fail("calibration dataset lineage is not valid")
    try:
        dataset = store.retrieve(CalibrationDatasetManifest, dataset_hash)
    except ExecutionError:
        _fail("calibration dataset lineage is not valid")

    generator_hash = config["generator_spec_hash"]
    if generator_hash not in set(dataset.generator_spec_hashes):
        _fail("calibration generator is not declared by the dataset")
    try:
        store.retrieve(GeneratorSpec, generator_hash)
    except ExecutionError:
        _fail("calibration generator lineage is not valid")

    truth_hash = config["truth_record_hash"]
    if truth_hash not in set(dataset.truth_record_hashes):
        _fail("calibration truth record is not declared by the dataset")
    try:
        truth = store.retrieve(TruthRecord, truth_hash)
    except ExecutionError:
        _fail("calibration truth lineage is not valid")
    if truth.estimand != scope.estimand or truth.units != scope.units:
        _fail("calibration truth is incompatible with the scope estimand")
    if truth.truth_type != scope.truth_type:
        _fail("calibration truth is incompatible with the scope truth type")

    replicate_id = config["replicate_id"]
    if replicate_id not in set(dataset.attempted_replicate_ids):
        _fail("calibration replicate is not declared by the dataset")
    if config["parameter_cell_id"] not in set(dataset.parameter_cell_ids):
        _fail("calibration parameter cell is not declared by the dataset")
    if dataset.split_assignment.value != config["split_assignment"]:
        _fail("calibration split disagrees with the dataset split")
    in_dev = replicate_id in plan.dev_replicate_ids
    in_held = replicate_id in plan.heldout_replicate_ids
    if config["split_assignment"] == SplitAssignment.DEV.value and not in_dev:
        _fail("calibration replicate is not permitted by the frozen plan")
    if config["split_assignment"] == SplitAssignment.HELD_OUT.value and not in_held:
        _fail("calibration replicate is not permitted by the frozen plan")
    if not in_dev and not in_held:
        _fail("calibration replicate is absent from the frozen plan")
    if task.candidate_id != replicate_id or task.seed != config["seed"]:
        _fail("calibration task identity disagrees with its lineage")
    if (plan_hash, scope_hash, dataset_hash, generator_hash, truth_hash) != tuple(
            task.input_artifact_hashes):
        _fail("calibration task inputs disagree with its lineage")


__all__ = ["CALIBRATION_STAGE", "CALIBRATION_OUTPUTS", "build_calibration_task",
           "validate_materialization_lineage", "materialize_replicate"]


TRAJECTORY_FORMAT = "calibration-trajectory-v1"


def _fail_class(message, failure_class):
    raise ExecutionError(message, failure_class)


def _brownian_parameters(generator_spec, scope):
    """Extract and domain-check Brownian inputs (infrastructure checks only)."""
    parameters = dict(generator_spec.parameters)
    try:
        n_frames = parameters["n_frames"]
        n_ions = parameters["n_ions"]
        tensor = parameters["diffusion_tensor"]
        dt_ps = parameters["dt_ps"]
    except KeyError as exc:
        _fail_class(f"calibration generator parameters omit {exc}", "UNSUPPORTED_INPUT")
    if isinstance(n_frames, bool) or not isinstance(n_frames, int) or n_frames < 1:
        _fail_class("calibration n_frames must be an integer >= 1", "UNSUPPORTED_INPUT")
    if isinstance(n_ions, bool) or not isinstance(n_ions, int) or n_ions < 1:
        _fail_class("calibration n_ions must be a positive integer", "UNSUPPORTED_INPUT")
    if n_ions != scope.n_particles:
        _fail_class("calibration n_ions disagrees with the scope particle count",
                    "UNSUPPORTED_INPUT")
    tensor = np.asarray(tensor, dtype=float)
    if tensor.shape != (3, 3) or not np.all(np.isfinite(tensor)):
        _fail_class("calibration diffusion tensor must be a finite 3x3 tensor",
                    "UNSUPPORTED_INPUT")
    if isinstance(dt_ps, bool) or not isinstance(dt_ps, (int, float)):
        _fail_class("calibration dt_ps must be numeric", "UNSUPPORTED_INPUT")
    dt_ps = float(dt_ps)
    if not np.isfinite(dt_ps) or dt_ps <= 0:
        _fail_class("calibration dt_ps must be finite and positive", "UNSUPPORTED_INPUT")
    return n_frames, n_ions, tensor, parameters["dt_ps"]


def _species_vector(scope, n_ions):
    expanded = [symbol for symbol in sorted(scope.species_composition)
                for _ in range(scope.species_composition[symbol])]
    if len(expanded) != n_ions:
        _fail_class("calibration species vector disagrees with n_ions",
                    "UNSUPPORTED_INPUT")
    return expanded


def _trajectory_object(*, replicate_id, species, cell, positions, dt_ps,
                       seed, generator_spec_hash, scope_hash):
    trajectory = np.asarray(positions, dtype=np.float64)
    if trajectory.ndim != 3 or trajectory.shape[2] != 3:
        _fail_class("calibration generator returned a non-trajectory array",
                    "SOFTWARE")
    if not np.all(np.isfinite(trajectory)):
        _fail_class("calibration generator returned non-finite positions",
                    "NUMERICAL")
    return {
        "format": TRAJECTORY_FORMAT,
        "replicate_id": replicate_id,
        "species": list(species),
        "cell": dict(cell) if cell is not None else None,
        "positions": trajectory.tolist(),
        "frame_steps": list(range(trajectory.shape[0])),
        "dt_ps": dt_ps,
        "seed": seed,
        "generator_spec_hash": generator_spec_hash,
        "scope_hash": scope_hash,
        "numpy_version": np.__version__,
    }


def materialize_replicate(
    *,
    task: TaskSpec,
    calibration_store: CalibrationStore,
    artifact_root,
    seed_override: int | None = None,
) -> dict:
    """Generate one Brownian replicate and persist its bound artifacts.

    Flow: lineage validation → resolve scope/generator/truth → dispatch →
    canonical trajectory bytes → ``ArtifactManifest`` → ``ExecutionAttempt``
    → trajectory bytes/manifest/attempt persistence →
    ``CalibrationReplicateManifest`` persistence → summary dict.

    Success returns ``artifact_status: "STORED"``. Any failure persists a
    FAILED attempt when possible and returns ``artifact_status: "FAILED"``
    with ``failure_class``/``reason``. No scientific verdict is ever emitted.
    """
    started = datetime.now(timezone.utc).isoformat()
    clock = time.perf_counter()
    attempt_id = digest({"task_id": task.task_id,
                         "execution_nonce": uuid.uuid4().hex})
    root = Path(artifact_root).resolve()

    def attempt(error=None, outputs=None):
        failure = None if error is None else classify_failure(error)
        return ExecutionAttempt(
            attempt_id=attempt_id, task_id=task.task_id, backend="local",
            task_content_hash=task.content_hash,
            remote_session_id=None, started_at=started,
            ended_at=datetime.now(timezone.utc).isoformat(),
            runtime_s=time.perf_counter() - clock,
            hardware={"machine": platform.machine(),
                      "logical_cpu_count": os.cpu_count()},
            environment={"numpy_version": np.__version__,
                         "platform": platform.platform(),
                         "python": platform.python_version(),
                         "code_revision": task.code_revision},
            precision="float64",
            exit_status=0 if error is None else 1,
            status="COMPLETED" if error is None else "FAILED",
            termination_reason="completed" if error is None else str(error),
            failure_class=failure,
            logs=() if error is None else (str(error),),
            output_manifest=outputs or {})

    def persist_attempt(record):
        append_file(inside(root, f"attempts/{record.content_hash}.json"),
                    canonical_bytes(record))

    try:
        with integrity_errors():
            validate_materialization_lineage(calibration_store, task)
            config = dict(task.config)
            scope = calibration_store.retrieve(CalibrationScope, config["scope_hash"])
            generator_spec = calibration_store.retrieve(
                GeneratorSpec, config["generator_spec_hash"])
            calibration_store.retrieve(TruthRecord, config["truth_record_hash"])
            dataset = calibration_store.retrieve(
                CalibrationDatasetManifest, config["dataset_manifest_hash"])
        if generator_spec.calibration_class != CalibrationClass.ISOTROPIC_BROWNIAN:
            _fail_class("calibration generator class is not supported by this slice",
                        "UNSUPPORTED_INPUT")
        n_frames, n_ions, tensor, dt_ps = _brownian_parameters(generator_spec, scope)
        if seed_override is not None:
            if isinstance(seed_override, bool) or not isinstance(seed_override, int):
                _fail_class("calibration seed_override must be an integer",
                            "UNSUPPORTED_INPUT")
            effective_seed = seed_override
        else:
            effective_seed = config["seed"]
        positions = brownian(n_frames=n_frames, n_ions=n_ions,
                             diffusion_tensor=tensor, dt_ps=dt_ps,
                             seed=effective_seed)
        species = _species_vector(scope, n_ions)
        trajectory = _trajectory_object(
            replicate_id=config["replicate_id"], species=species,
            cell=scope.cell_geometry, positions=positions, dt_ps=dt_ps,
            seed=effective_seed, generator_spec_hash=config["generator_spec_hash"],
            scope_hash=config["scope_hash"])
        data = canonical_bytes(trajectory)
        logical_hash = digest(trajectory)
        manifest = ArtifactManifest(
            logical_hash=logical_hash,
            raw_hash=hashlib.sha256(data).hexdigest(),
            size_bytes=len(data),
            format="json", format_version=TRAJECTORY_FORMAT,
            canonicalization_version="canonical-json-v1",
            durable_locator=f"blobs/{logical_hash}",
            producer_attempt=attempt_id,
            parent_artifact_hashes=tuple(sorted(task.input_artifact_hashes)),
            retrieval_verification={"status": "STORED", "verifier": "canonical-json-v1"})
        completed = attempt(outputs={task.expected_outputs[0]: manifest.content_hash})
        with integrity_errors():
            append_file(inside(root, manifest.durable_locator), data)
            append_file(inside(root, f"trajectory_manifests/{manifest.content_hash}.json"),
                        canonical_bytes(manifest))
            persist_attempt(completed)
            replicate = CalibrationReplicateManifest(
                replicate_id=config["replicate_id"], dataset_id=dataset.dataset_id,
                parameter_cell_id=config["parameter_cell_id"],
                split_assignment=config["split_assignment"],
                independence_declaration={},
                seed=effective_seed, initialization_hash=None,
                trajectory_artifact_hash=logical_hash,
                truth_record_hash=config["truth_record_hash"],
                conditions={"scope_hash": config["scope_hash"], "seed": effective_seed,
                            "numpy_version": np.__version__,
                            "code_revision": task.code_revision},
                dependence_descriptors=None, event_info=None,
                execution_attempt_hash=completed.content_hash,
                computational_outcome=None, scientific_outcome="COMPLETED",
                outcome_notes={"seed_override": seed_override is not None,
                               "task_seed": config["seed"]})
            replicate_hash = calibration_store.store(replicate)
        return {"replicate_manifest_hash": replicate_hash,
                "trajectory_logical_hash": logical_hash,
                "attempt_id": attempt_id,
                "artifact_status": "STORED"}
    except Exception as exc:
        failure = classify_failure(exc)
        try:
            with integrity_errors():
                persist_attempt(attempt(error=exc))
        except Exception:
            pass
        return {"artifact_status": "FAILED", "failure_class": failure.value,
                "reason": str(exc), "attempt_id": attempt_id}
