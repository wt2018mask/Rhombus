"""Commit A: G.1 calibration task construction and lineage validation.

Adapter only: builds an explicit calibration ``TaskSpec`` and validates its
frozen G.1 lineage against a ``CalibrationStore``. No trajectory generation,
no artifact persistence, no estimator logic, no scientific verdicts.

Calibration tasks intentionally sit beside the P3 follow-up execution path
(``FollowupRequest`` / ``generate_followups`` / ``execute_local``); this
module never calls that path and the task stage stays ``CALIBRATION``.
"""

from __future__ import annotations

from rudeus.execution.contracts import ExecutionError, TaskSpec
from rudeus.science.calibration import (
    CalibrationDatasetManifest,
    CalibrationPlan,
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
from rudeus.science.contracts import require_hash


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
           "validate_materialization_lineage"]
