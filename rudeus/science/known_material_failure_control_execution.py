"""Executable B2 failure-control harness.

Executors are generic and selected by data. A control passes only when the observed
behavior matches the contract. Execution errors remain explicitly classified and can
never satisfy a scientific failure control; infrastructure is not inferred by default.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from pymatgen.core import Lattice, Structure

from rudeus.filters.p0 import evaluate_p0
from rudeus.schema import ExistenceState
from rudeus.science.contracts import Record, digest, require_hash
from rudeus.science.known_material_artifact_curation import (
    load_registry,
    load_retention_index,
)
from rudeus.science.known_material_failure_control import (
    FailureControlCase,
    FailureControlCaseState,
    FailureControlExpectedBehavior,
    FailureControlPlan,
)
from rudeus.science.known_material_model_domain import (
    check_model_domain,
    deterministic_unsupported_atomic_number,
    load_model_domain_index,
    load_model_domain_registry,
    load_model_domain_snapshot,
    verify_model_domain_repository_state,
)
from rudeus.science.known_material_representation_policy import (
    REPRESENTATION_EVIDENCE_LEDGER_VERSION,
    REPRESENTATION_POLICY_VERSION,
    RepresentationEvidenceLedger,
    RepresentationPolicyKind,
    RepresentationPolicyRegistry,
    RepresentationPolicySpec,
    RepresentationPolicyStatus,
    load_representation_evidence_ledger,
    load_representation_policy_registry,
    resolve_representation_policy,
)
from rudeus.science.known_material_structure_resolution import (
    ResolutionStatus,
    load_structure_resolution_manifest,
    resolve_structure_manifest,
)


FAILURE_CONTROL_EXECUTION_VERSION = "known-material-failure-control-execution-v1"
FAILURE_CONTROL_FIXTURE_ROOT = Path(
    "data/benchmarks/known_material/failure_controls"
)


class FailureControlExecutionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class FailureControlErrorClass(str, Enum):
    DATA_OR_CONFIGURATION = "DATA_OR_CONFIGURATION"
    SOFTWARE = "SOFTWARE"
    INFRASTRUCTURE = "INFRASTRUCTURE"


@dataclass(frozen=True, kw_only=True)
class FailureControlObservation(Record):
    execution_version: str
    control_id: str
    control_kind: str
    executor_id: str
    expected_behavior: str
    observed_behavior: str
    status: str
    input_provenance_hash: str
    evidence_hashes: tuple[str, ...]
    details: Mapping[str, Any]
    error_class: str | None = None
    infrastructure_error: bool = False

    def validate(self):
        super().validate()
        if self.execution_version != FAILURE_CONTROL_EXECUTION_VERSION:
            raise ValueError("unsupported failure-control execution version")
        status = FailureControlExecutionStatus(self.status)
        FailureControlExpectedBehavior(self.expected_behavior)
        if not all((
            self.control_id,
            self.control_kind,
            self.executor_id,
            self.observed_behavior,
        )):
            raise ValueError("failure-control observation identity is incomplete")
        require_hash(self.input_provenance_hash)
        if not self.evidence_hashes:
            raise ValueError("failure-control observation requires evidence hashes")
        for value in self.evidence_hashes:
            require_hash(value)
        if status == FailureControlExecutionStatus.PASS:
            if self.observed_behavior != self.expected_behavior:
                raise ValueError("passing failure control must match expected behavior")
            if self.infrastructure_error or self.error_class is not None:
                raise ValueError("passing failure control cannot carry an error")
        elif status == FailureControlExecutionStatus.FAIL:
            if self.infrastructure_error or self.error_class is not None:
                raise ValueError("scientific control mismatch cannot carry an execution error")
        else:
            if self.error_class is None:
                raise ValueError("error status requires an explicit error class")
            error_class = FailureControlErrorClass(self.error_class)
            if self.infrastructure_error != (
                error_class == FailureControlErrorClass.INFRASTRUCTURE
            ):
                raise ValueError(
                    "infrastructure_error flag must match the explicit error class"
                )


@dataclass(frozen=True, kw_only=True)
class FailureControlExecutionReport(Record):
    execution_version: str
    observations: tuple[FailureControlObservation, ...]
    skipped_control_ids: tuple[str, ...]

    def validate(self):
        super().validate()
        if self.execution_version != FAILURE_CONTROL_EXECUTION_VERSION:
            raise ValueError("unsupported failure-control execution version")
        ids = [item.control_id for item in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("failure-control report contains duplicate observations")
        if len(self.skipped_control_ids) != len(set(self.skipped_control_ids)):
            raise ValueError("failure-control report contains duplicate skipped ids")
        if set(ids) & set(self.skipped_control_ids):
            raise ValueError("failure control cannot be both executed and skipped")


ExecutorResult = tuple[str, Mapping[str, Any], tuple[str, ...]]
Executor = Callable[[FailureControlCase, Path], ExecutorResult]


def _repository_relative_path(repo_root: Path, raw: str) -> Path:
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("failure-control fixture path must be repository-relative")
    path = repo_root / relative
    return path


def _p0_static_filter_executor(
    case: FailureControlCase,
    repo_root: Path,
) -> ExecutorResult:
    fixture_path = str(case.executor_config["fixture_path"])
    path = _repository_relative_path(repo_root, fixture_path)
    relative = Path(fixture_path)
    if not relative.is_relative_to(FAILURE_CONTROL_FIXTURE_ROOT):
        raise ValueError("P0 failure-control fixture escapes fixture root")
    payload_bytes = path.read_bytes()
    actual_hash = hashlib.sha256(payload_bytes).hexdigest()
    if actual_hash != case.provenance_hash:
        raise ValueError("P0 failure-control fixture provenance hash mismatch")

    payload = json.loads(payload_bytes.decode("utf-8"))
    structure = Structure(
        Lattice(payload["lattice_matrix_A"]),
        payload["species"],
        payload["fractional_coordinates"],
    )
    result = evaluate_p0(payload["formula"], structure=structure)

    if (
        result.existence_state == ExistenceState.FAIL
        and result.geometry_ok is False
        and result.details["geometry"].get("clash_detected") is True
    ):
        observed = FailureControlExpectedBehavior.REJECT_INPUT.value
    elif result.existence_state == ExistenceState.UNKNOWN:
        observed = FailureControlExpectedBehavior.RETURN_UNKNOWN_OR_INDETERMINATE.value
    else:
        observed = "INPUT_NOT_REJECTED"

    result_hash = digest({
        "existence_state": result.existence_state.value,
        "neutrality_ok": result.neutrality_ok,
        "pauling_ok": result.pauling_ok,
        "geometry_ok": result.geometry_ok,
        "details": result.details,
    })
    return (
        observed,
        {
            "fixture_id": payload["fixture_id"],
            "existence_state": result.existence_state.value,
            "neutrality_ok": result.neutrality_ok,
            "pauling_ok": result.pauling_ok,
            "geometry_ok": result.geometry_ok,
            "p0_details": result.details,
        },
        (actual_hash, result_hash),
    )


def _representation_policy_executor(
    case: FailureControlCase,
    repo_root: Path,
) -> ExecutorResult:
    fixture_path = str(case.executor_config["fixture_path"])
    path = _repository_relative_path(repo_root, fixture_path)
    relative = Path(fixture_path)
    if not relative.is_relative_to(FAILURE_CONTROL_FIXTURE_ROOT):
        raise ValueError("representation failure-control fixture escapes fixture root")

    payload_bytes = path.read_bytes()
    actual_hash = hashlib.sha256(payload_bytes).hexdigest()
    if actual_hash != case.provenance_hash:
        raise ValueError(
            "representation failure-control fixture provenance hash mismatch"
        )
    payload = json.loads(payload_bytes.decode("utf-8"))

    spec = RepresentationPolicySpec(
        policy_id=str(payload["policy_id"]),
        policy_kind=RepresentationPolicyKind(
            str(payload["policy_kind"])
        ).value,
        applicable_modes=(str(payload["resolution_mode"]),),
        required_inputs=tuple(str(v) for v in payload["required_inputs"]),
        optional_inputs=tuple(str(v) for v in payload["optional_inputs"]),
        forbidden_shortcuts=tuple(
            str(v) for v in payload["forbidden_shortcuts"]
        ),
        rationale=tuple(str(v) for v in payload["rationale"]),
    )
    registry = RepresentationPolicyRegistry(
        registry_version=REPRESENTATION_POLICY_VERSION,
        policies=(spec,),
    )
    ledger = RepresentationEvidenceLedger(
        ledger_version=REPRESENTATION_EVIDENCE_LEDGER_VERSION,
        entries=(),
    )
    resolution = resolve_representation_policy(
        policy_id=spec.policy_id,
        resolution_mode=str(payload["resolution_mode"]),
        registry=registry,
        evidence_ledger=ledger,
    )

    if (
        resolution.status
        == RepresentationPolicyStatus.BLOCKED_MISSING_EVIDENCE.value
        and resolution.missing_inputs == spec.required_inputs
    ):
        observed = FailureControlExpectedBehavior.BLOCK_BEFORE_EXECUTION.value
    elif resolution.status == RepresentationPolicyStatus.SATISFIED.value:
        observed = "EXECUTION_ALLOWED"
    else:
        observed = "UNEXPECTED_REPRESENTATION_POLICY_STATE"

    return (
        observed,
        {
            "fixture_id": str(payload["fixture_id"]),
            "policy_id": spec.policy_id,
            "resolution_mode": str(payload["resolution_mode"]),
            "policy_status": resolution.status,
            "missing_inputs": list(resolution.missing_inputs),
        },
        (
            actual_hash,
            registry.content_hash,
            ledger.content_hash,
            resolution.content_hash,
        ),
    )


def _structure_resolution_executor(
    case: FailureControlCase,
    repo_root: Path,
) -> ExecutorResult:
    data_root = _repository_relative_path(
        repo_root,
        str(case.executor_config["data_root"]),
    )
    resolution_key = str(case.executor_config["resolution_key"])

    manifest = load_structure_resolution_manifest(
        data_root / "structure_resolution_manifest_v1.json"
    )
    registry = load_registry(data_root / "artifact_registry_v1.json")
    retention_index = load_retention_index(
        data_root / "artifact_retention_index_v1.json"
    )
    policy_registry = load_representation_policy_registry(
        data_root / "representation_policy_registry_v1.json"
    )
    evidence_ledger = load_representation_evidence_ledger(
        data_root / "representation_evidence_ledger_v1.json"
    )
    ledger = resolve_structure_manifest(
        manifest,
        registry,
        retention_index,
        policy_registry=policy_registry,
        policy_evidence_ledger=evidence_ledger,
    )
    by_key = {item.resolution_key: item for item in ledger.cases}
    try:
        resolved = by_key[resolution_key]
    except KeyError as exc:
        raise ValueError(
            "failure-control resolution key is absent from canonical manifest"
        ) from exc

    if case.provenance_hash not in resolved.artifact_hashes:
        raise ValueError(
            "representation failure-control provenance is not retained by case"
        )

    if resolved.status in {
        ResolutionStatus.BLOCKED_POLICY.value,
        ResolutionStatus.UNREPRESENTABLE.value,
    }:
        observed = FailureControlExpectedBehavior.BLOCK_BEFORE_EXECUTION.value
    elif resolved.status == ResolutionStatus.READY.value:
        observed = "EXECUTION_ALLOWED"
    else:
        observed = "BLOCKED_FOR_NON_REPRESENTATION_REASON"

    evidence_hashes = (
        manifest.content_hash,
        registry.content_hash,
        retention_index.content_hash,
        policy_registry.content_hash,
        evidence_ledger.content_hash,
        *resolved.artifact_hashes,
    )
    return (
        observed,
        {
            "resolution_key": resolved.resolution_key,
            "material_key": resolved.material_key,
            "resolution_status": resolved.status,
            "representation_policy_id": resolved.representation_policy_id,
            "unresolved_requirements": list(resolved.unresolved_requirements),
            "scientific_blockers": list(resolved.scientific_blockers),
        },
        tuple(dict.fromkeys(evidence_hashes)),
    )


def _model_domain_support_executor(
    case: FailureControlCase,
    repo_root: Path,
) -> ExecutorResult:
    data_root = _repository_relative_path(
        repo_root,
        str(case.executor_config["data_root"]),
    )
    domain_key = str(case.executor_config["domain_key"])
    selection_strategy = str(case.executor_config["selection_strategy"])
    if selection_strategy != "first-unsupported-atomic-number-v1":
        raise ValueError("unsupported model-domain stress selection strategy")

    registry = load_model_domain_registry(
        data_root / "model_domain_registry_v1.json"
    )
    index = load_model_domain_index(
        data_root / "model_domain_snapshot_index_v1.json"
    )
    checked = verify_model_domain_repository_state(
        registry,
        index,
        repo_root=repo_root,
    )
    if domain_key not in checked:
        raise ValueError(
            "model-domain failure control requires a verified retained snapshot"
        )

    registry_by_key = {item.domain_key: item for item in registry.entries}
    index_by_key = {item.domain_key: item for item in index.entries}
    try:
        registry_entry = registry_by_key[domain_key]
        index_entry = index_by_key[domain_key]
    except KeyError as exc:
        raise ValueError(
            "model-domain failure-control key is absent from canonical evidence"
        ) from exc

    if index_entry.snapshot_content_hash != case.provenance_hash:
        raise ValueError(
            "model-domain failure-control provenance does not match snapshot"
        )
    if index_entry.checkpoint_sha256 != registry_entry.checkpoint_sha256:
        raise ValueError("model-domain checkpoint identity is inconsistent")

    snapshot = load_model_domain_snapshot(
        _repository_relative_path(repo_root, index_entry.snapshot_path)
    )
    if snapshot.content_hash != case.provenance_hash:
        raise ValueError("model-domain snapshot semantic hash mismatch")
    if snapshot.domain_key != domain_key:
        raise ValueError("model-domain snapshot key mismatch")

    unsupported_z = deterministic_unsupported_atomic_number(snapshot)
    check = check_model_domain(snapshot, (unsupported_z,))
    if check.disposition == "UNKNOWN_MODEL_DOMAIN_UNSUPPORTED":
        observed = (
            FailureControlExpectedBehavior.RETURN_UNKNOWN_OR_INDETERMINATE.value
        )
    else:
        observed = "UNSUPPORTED_STRESS_INPUT_ACCEPTED_BY_MODEL_DOMAIN"

    return (
        observed,
        {
            "domain_key": domain_key,
            "model_id": snapshot.model_id,
            "selection_strategy": selection_strategy,
            "selected_unsupported_atomic_number": unsupported_z,
            "model_domain_disposition": check.disposition,
            "reason_codes": list(check.reason_codes),
            "unsupported_atomic_numbers": list(
                check.unsupported_atomic_numbers
            ),
            "supported_element_count": snapshot.element_count,
            "snapshot_content_hash": snapshot.content_hash,
            "checkpoint_sha256": snapshot.checkpoint_sha256,
        },
        tuple(dict.fromkeys((
            registry.content_hash,
            index.content_hash,
            snapshot.content_hash,
            index_entry.snapshot_file_sha256,
            index_entry.checkpoint_sha256,
        ))),
    )


_EXECUTORS: dict[str, Executor] = {
    "p0-static-filter-v1": _p0_static_filter_executor,
    "representation-policy-v1": _representation_policy_executor,
    "structure-resolution-v1": _structure_resolution_executor,
    "model-domain-support-v1": _model_domain_support_executor,
}


def execute_failure_control(
    case: FailureControlCase,
    *,
    repo_root: Path,
) -> FailureControlObservation:
    if case.state != FailureControlCaseState.EXECUTABLE.value:
        raise ValueError("only executable failure controls may be executed")
    if case.provenance_hash is None or case.executor_id is None:
        raise ValueError("executable failure control is missing execution identity")

    try:
        executor = _EXECUTORS[case.executor_id]
    except KeyError as exc:
        raise ValueError(
            f"unsupported failure-control executor: {case.executor_id}"
        ) from exc

    try:
        observed, details, evidence_hashes = executor(case, repo_root)
        status = (
            FailureControlExecutionStatus.PASS.value
            if observed == case.expected_behavior
            else FailureControlExecutionStatus.FAIL.value
        )
        return FailureControlObservation(
            execution_version=FAILURE_CONTROL_EXECUTION_VERSION,
            control_id=case.control_id,
            control_kind=case.control_kind,
            executor_id=case.executor_id,
            expected_behavior=case.expected_behavior,
            observed_behavior=observed,
            status=status,
            input_provenance_hash=case.provenance_hash,
            evidence_hashes=evidence_hashes,
            details=details,
            error_class=None,
            infrastructure_error=False,
        )
    except (ValueError, KeyError, FileNotFoundError, json.JSONDecodeError) as exc:
        return FailureControlObservation(
            execution_version=FAILURE_CONTROL_EXECUTION_VERSION,
            control_id=case.control_id,
            control_kind=case.control_kind,
            executor_id=case.executor_id,
            expected_behavior=case.expected_behavior,
            observed_behavior="ERROR",
            status=FailureControlExecutionStatus.ERROR.value,
            input_provenance_hash=case.provenance_hash,
            evidence_hashes=(case.provenance_hash,),
            details={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
            error_class=FailureControlErrorClass.DATA_OR_CONFIGURATION.value,
            infrastructure_error=False,
        )
    except Exception as exc:
        return FailureControlObservation(
            execution_version=FAILURE_CONTROL_EXECUTION_VERSION,
            control_id=case.control_id,
            control_kind=case.control_kind,
            executor_id=case.executor_id,
            expected_behavior=case.expected_behavior,
            observed_behavior="ERROR",
            status=FailureControlExecutionStatus.ERROR.value,
            input_provenance_hash=case.provenance_hash,
            evidence_hashes=(case.provenance_hash,),
            details={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
            error_class=FailureControlErrorClass.SOFTWARE.value,
            infrastructure_error=False,
        )


def run_failure_control_plan(
    plan: FailureControlPlan,
    *,
    repo_root: Path,
) -> FailureControlExecutionReport:
    observations: list[FailureControlObservation] = []
    skipped: list[str] = []
    for case in plan.cases:
        if case.state != FailureControlCaseState.EXECUTABLE.value:
            skipped.append(case.control_id)
            continue
        observations.append(
            execute_failure_control(case, repo_root=repo_root)
        )

    return FailureControlExecutionReport(
        execution_version=FAILURE_CONTROL_EXECUTION_VERSION,
        observations=tuple(observations),
        skipped_control_ids=tuple(skipped),
    )
