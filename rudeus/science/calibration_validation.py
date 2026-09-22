"""Read-only integrity/immutability validation for stored G.1 records.

Provenance only: verifies internal consistency, hash resolution, split
membership, inventory completeness, held-out separation, and post-freeze
immutability. Answers NOTHING about estimator accuracy, bias, coverage,
uncertainty adequacy, sufficiency, qualification, or candidate verdicts.

Result semantics (integrity only, never scientific verdicts):
- VALID: every requested invariant holds.
- INVALID: at least one deterministic integrity invariant is violated.
- INCOMPLETE: required evidence cannot be resolved, or the frozen schema
  cannot establish the invariant (reported, never invented).

Violations are deterministic mappings with stable reason codes identifying
the invariant, record type, identity, and expected vs observed values. No
timestamps, paths, or exception strings leak into results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration import (
    CalibrationDatasetManifest,
    CalibrationPlan,
    CalibrationReplicateManifest,
    CalibrationScope,
    GeneratorSpec,
    HeldoutEvaluationManifest,
    SplitAssignment,
    TruthRecord,
)
from rudeus.science.calibration_store import CalibrationStore, directory_for
from rudeus.science.contracts import require_hash


VALID = "VALID"
INVALID = "INVALID"
INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class ValidationResult:
    """Deterministic integrity outcome with stable reason-coded violations."""

    status: str
    violations: tuple = ()
    notes: tuple = ()

    def __post_init__(self):
        if self.status not in (VALID, INVALID, INCOMPLETE):
            raise ValueError("unknown validation status")
        object.__setattr__(self, "violations", tuple(self.violations))
        object.__setattr__(self, "notes", tuple(self.notes))

    def merged(self, other):
        """Combine two results; INVALID dominates INCOMPLETE dominates VALID."""
        status = self.status
        if other.status == INVALID or status == INVALID:
            status = INVALID
        elif other.status == INCOMPLETE or status == INCOMPLETE:
            status = INCOMPLETE
        return ValidationResult(status, self.violations + other.violations,
                                self.notes + other.notes)


def _violation(code, *, record_type=None, identity=None, expected=None,
               observed=None, reference=None):
    entry = {"code": code}
    if record_type is not None:
        entry["record_type"] = record_type
    if identity is not None:
        entry["identity"] = identity
    if expected is not None:
        entry["expected"] = expected
    if observed is not None:
        entry["observed"] = observed
    if reference is not None:
        entry["reference"] = reference
    return entry


def _resolve(store, cls, identity, record_type):
    """Retrieve a record; missing bytes -> INCOMPLETE, tamper -> INVALID."""
    try:
        return store.retrieve(cls, identity), None
    except ExecutionError:
        try:
            exists = store.path(f"{directory_for(cls)}/{identity}.json").exists()
        except (ValueError, OSError):
            exists = False
        if not exists:
            return None, _violation("unresolved_reference", record_type=record_type,
                                    identity=identity)
        return None, _violation("content_integrity_mismatch", record_type=record_type,
                                identity=identity)


def _resolve_many(store, cls, identities, record_type):
    records, result = {}, ValidationResult(VALID)
    for identity in sorted(set(identities)):
        try:
            require_hash(identity)
        except ValueError:
            result = result.merged(ValidationResult(
                INVALID, (_violation("malformed_hash_reference",
                                     record_type=record_type, identity=identity),)))
            continue
        record, violation = _resolve(store, cls, identity, record_type)
        if violation is not None:
            status = INCOMPLETE if violation["code"] == "unresolved_reference" else INVALID
            result = result.merged(ValidationResult(status, (violation,)))
        else:
            records[identity] = record
    return records, result


def validate_plan(store, plan_hash):
    """Verify a stored plan resolves and its scope hashes resolve."""
    try:
        require_hash(plan_hash)
    except ValueError:
        return ValidationResult(INVALID, (_violation("malformed_hash_reference",
                                                     record_type="CalibrationPlan",
                                                     identity=plan_hash),))
    plan, violation = _resolve(store, CalibrationPlan, plan_hash, "CalibrationPlan")
    if violation is not None:
        status = INCOMPLETE if violation["code"] == "unresolved_reference" else INVALID
        return ValidationResult(status, (violation,))
    _, scopes = _resolve_many(store, CalibrationScope, plan.scope_hashes,
                              "CalibrationScope")
    return scopes


def validate_dataset(store, dataset_hash, *, plan=None):
    """Verify dataset binding: plan, scope, class, cells, references."""
    try:
        require_hash(dataset_hash)
    except ValueError:
        return ValidationResult(INVALID, (_violation("malformed_hash_reference",
                                                     record_type="CalibrationDatasetManifest",
                                                     identity=dataset_hash),))
    dataset, violation = _resolve(store, CalibrationDatasetManifest, dataset_hash,
                                  "CalibrationDatasetManifest")
    if violation is not None:
        status = INCOMPLETE if violation["code"] == "unresolved_reference" else INVALID
        return ValidationResult(status, (violation,))
    result = ValidationResult(VALID)
    if plan is None:
        plan, violation = _resolve(store, CalibrationPlan, dataset.plan_hash,
                                   "CalibrationPlan")
        if violation is not None:
            status = INCOMPLETE if violation["code"] == "unresolved_reference" else INVALID
            return ValidationResult(status, (violation,))
    if dataset.plan_hash != plan.content_hash:
        result = result.merged(ValidationResult(INVALID, (_violation(
            "plan_hash_mismatch", record_type="CalibrationDatasetManifest",
            identity=dataset_hash, expected=plan.content_hash,
            observed=dataset.plan_hash),)))
    if dataset.scope_hash not in set(plan.scope_hashes):
        result = result.merged(ValidationResult(INVALID, (_violation(
            "scope_not_in_plan", record_type="CalibrationDatasetManifest",
            identity=dataset_hash, observed=dataset.scope_hash,
            reference=plan.content_hash),)))
    if dataset.calibration_class not in set(plan.class_inventory):
        result = result.merged(ValidationResult(INVALID, (_violation(
            "class_not_in_plan", record_type="CalibrationDatasetManifest",
            identity=dataset_hash, observed=dataset.calibration_class.value),)))
    unknown_cells = sorted(set(dataset.parameter_cell_ids) - set(plan.parameter_cell_ids))
    if unknown_cells:
        result = result.merged(ValidationResult(INVALID, (_violation(
            "parameter_cell_not_in_plan", record_type="CalibrationDatasetManifest",
            identity=dataset_hash, observed=unknown_cells),)))
    for hashes, cls, name in (
            (dataset.truth_record_hashes, TruthRecord, "TruthRecord"),
            (dataset.generator_spec_hashes, GeneratorSpec, "GeneratorSpec"),
            (dataset.artifact_manifest_hashes, None, None)):
        if cls is None:
            continue
        _, resolved = _resolve_many(store, cls, hashes, name)
        result = result.merged(resolved)
    return result


def _replicate_view(store, replicate_hashes):
    records, result = _resolve_many(store, CalibrationReplicateManifest,
                                    replicate_hashes, "CalibrationReplicateManifest")
    return records, result


def validate_replicates(store, replicate_hashes, *, datasets=(), plan_hash=None):
    """Verify replicate inventory: conflicts, splits, lineage, completeness."""
    records, result = _replicate_view(store, replicate_hashes)
    by_id = {}
    for identity in sorted(records):
        record = records[identity]
        if record.replicate_id in by_id and by_id[record.replicate_id] != identity:
            result = result.merged(ValidationResult(INVALID, (_violation(
                "conflicting_replicate_definition",
                record_type="CalibrationReplicateManifest", identity=record.replicate_id,
                expected=by_id[record.replicate_id], observed=identity),)))
        by_id.setdefault(record.replicate_id, identity)
    identities = sorted(records)
    by_trajectory = {}
    for identity in identities:
        record = records[identity]
        if record.trajectory_artifact_hash is None:
            continue
        by_trajectory.setdefault(record.trajectory_artifact_hash, []).append(identity)
    for trajectory in sorted(by_trajectory):
        owners = by_trajectory[trajectory]
        rep_ids = sorted({records[i].replicate_id for i in owners})
        if len(rep_ids) < 2:
            continue
        splits = {records[i].split_assignment for i in owners}
        code = ("trajectory_in_both_splits" if len(splits) > 1
                else "duplicate_trajectory_hash")
        result = result.merged(ValidationResult(INVALID, (_violation(
            code, record_type="CalibrationReplicateManifest", identity=trajectory,
            observed=rep_ids),)))
    dataset_records = {}
    for dataset_hash in sorted(set(datasets)):
        dataset, violation = _resolve(store, CalibrationDatasetManifest, dataset_hash,
                                      "CalibrationDatasetManifest")
        if violation is not None:
            status = INCOMPLETE if violation["code"] == "unresolved_reference" else INVALID
            result = result.merged(ValidationResult(status, (violation,)))
        else:
            dataset_records[dataset_hash] = dataset
    for identity in identities:
        record = records[identity]
        owners = [h for h, d in dataset_records.items()
                  if record.replicate_id in d.attempted_replicate_ids]
        if datasets and not owners:
            result = result.merged(ValidationResult(INVALID, (_violation(
                "undeclared_replicate", record_type="CalibrationReplicateManifest",
                identity=record.replicate_id),)))
        for owner in owners:
            dataset = dataset_records[owner]
            if record.split_assignment != dataset.split_assignment:
                result = result.merged(ValidationResult(INVALID, (_violation(
                    "split_mismatch", record_type="CalibrationReplicateManifest",
                    identity=record.replicate_id,
                    expected=dataset.split_assignment.value,
                    observed=record.split_assignment.value, reference=owner),)))
    declared = {r for d in dataset_records.values() for r in d.attempted_replicate_ids}
    supplied = {records[i].replicate_id for i in identities}
    for missing in sorted(declared - supplied):
        result = result.merged(ValidationResult(INCOMPLETE, (_violation(
            "missing_replicate", record_type="CalibrationReplicateManifest",
            identity=missing),)))
    if plan_hash is not None:
        plan, violation = _resolve(store, CalibrationPlan, plan_hash, "CalibrationPlan")
        if violation is not None:
            status = INCOMPLETE if violation["code"] == "unresolved_reference" else INVALID
            result = result.merged(ValidationResult(status, (violation,)))
        else:
            for identity in identities:
                record = records[identity]
                in_dev = record.replicate_id in plan.dev_replicate_ids
                in_held = record.replicate_id in plan.heldout_replicate_ids
                if not in_dev and not in_held:
                    result = result.merged(ValidationResult(INVALID, (_violation(
                        "undeclared_replicate", record_type="CalibrationReplicateManifest",
                        identity=record.replicate_id, reference=plan.content_hash),)))
                elif ((record.split_assignment == SplitAssignment.DEV and not in_dev)
                        or (record.split_assignment == SplitAssignment.HELD_OUT
                            and not in_held)):
                    result = result.merged(ValidationResult(INVALID, (_violation(
                        "split_mismatch", record_type="CalibrationReplicateManifest",
                        identity=record.replicate_id,
                        expected=SplitAssignment.HELD_OUT.value
                        if in_held else SplitAssignment.DEV.value,
                        observed=record.split_assignment.value,
                        reference=plan.content_hash),)))
    return result


def validate_heldout_evaluation(store, evaluation_hash, *, plan_hash=None,
                                heldout_dataset_hashes=()):
    """Verify held-out evaluation provenance (not scientific validity)."""
    try:
        require_hash(evaluation_hash)
    except ValueError:
        return ValidationResult(INVALID, (_violation("malformed_hash_reference",
                                                     record_type="HeldoutEvaluationManifest",
                                                     identity=evaluation_hash),))
    evaluation, violation = _resolve(store, HeldoutEvaluationManifest, evaluation_hash,
                                     "HeldoutEvaluationManifest")
    if violation is not None:
        status = INCOMPLETE if violation["code"] == "unresolved_reference" else INVALID
        return ValidationResult(status, (violation,))
    result = ValidationResult(VALID)
    if plan_hash is not None and evaluation.plan_hash != plan_hash:
        result = result.merged(ValidationResult(INVALID, (_violation(
            "plan_hash_mismatch", record_type="HeldoutEvaluationManifest",
            identity=evaluation_hash, expected=plan_hash,
            observed=evaluation.plan_hash),)))
    if heldout_dataset_hashes and (set(evaluation.heldout_dataset_hashes)
                                   != set(heldout_dataset_hashes)):
        result = result.merged(ValidationResult(INVALID, (_violation(
            "heldout_set_mismatch", record_type="HeldoutEvaluationManifest",
            identity=evaluation_hash, expected=sorted(heldout_dataset_hashes),
            observed=sorted(evaluation.heldout_dataset_hashes)),)))
    _, resolved = _resolve_many(store, CalibrationDatasetManifest,
                                evaluation.heldout_dataset_hashes,
                                "CalibrationDatasetManifest")
    result = result.merged(resolved)
    if evaluation.unblinding_declaration is None:
        result = result.merged(ValidationResult(INCOMPLETE, (_violation(
            "unblinding_undeclared", record_type="HeldoutEvaluationManifest",
            identity=evaluation_hash),)))
    notes = ("unblinding temporal order is not provable from the frozen schema; "
             "declaration presence is provenance only",)
    return ValidationResult(result.status, result.violations,
                            result.notes + notes)


def _contamination(dev_hashes, heldout_hashes, kind):
    shared = sorted(set(dev_hashes) & set(heldout_hashes))
    if not shared:
        return ValidationResult(VALID)
    return ValidationResult(INVALID, (_violation(
        "heldout_contamination", record_type=kind, observed=shared),))


def validate_graph(store, plan_hash, dataset_hashes=(), replicate_hashes=(),
                   evaluation_hashes=()):
    """Validate a full calibration graph: plan, datasets, replicates, held-out."""
    result = validate_plan(store, plan_hash)
    plan = None
    if result.status != INVALID:
        try:
            plan = store.retrieve(CalibrationPlan, plan_hash)
        except ExecutionError:
            plan = None
    datasets, seen = {}, result
    for dataset_hash in sorted(set(dataset_hashes)):
        dataset_result = validate_dataset(store, dataset_hash, plan=plan)
        seen = seen.merged(dataset_result)
        try:
            datasets[dataset_hash] = store.retrieve(CalibrationDatasetManifest,
                                                    dataset_hash)
        except ExecutionError:
            continue
    replicates, _ = _replicate_view(store, replicate_hashes)
    seen = seen.merged(validate_replicates(
        store, replicate_hashes, datasets=tuple(datasets),
        plan_hash=plan_hash if plan is not None else None))
    for evaluation_hash in sorted(set(evaluation_hashes)):
        seen = seen.merged(validate_heldout_evaluation(store, evaluation_hash,
                                                       plan_hash=plan_hash))
    dev_sets = [h for h, d in datasets.items()
                if d.split_assignment == SplitAssignment.DEV]
    held_sets = [h for h, d in datasets.items()
                 if d.split_assignment == SplitAssignment.HELD_OUT]
    if dev_sets and held_sets:
        dev_ids = {d.dataset_id for d in (datasets[h] for h in dev_sets)}
        held_ids = {d.dataset_id for d in (datasets[h] for h in held_sets)}
        if dev_ids & held_ids:
            seen = seen.merged(ValidationResult(INVALID, (_violation(
                "heldout_contamination", record_type="CalibrationDatasetManifest",
                observed=sorted(dev_ids & held_ids)),)))
        dev_trajs = {t for h in dev_sets for t in datasets[h].trajectory_ids}
        held_trajs = {t for h in held_sets for t in datasets[h].trajectory_ids}
        seen = seen.merged(_contamination(dev_trajs, held_trajs,
                                          "CalibrationDatasetManifest"))
        seen = seen.merged(_contamination(
            {h for h in dev_sets}, {h for h in held_sets},
            "CalibrationDatasetManifest"))
        dev_rep = {r for h in dev_sets for r in datasets[h].attempted_replicate_ids}
        held_rep = {r for h in held_sets for r in datasets[h].attempted_replicate_ids}
        seen = seen.merged(_contamination(dev_rep, held_rep,
                                          "CalibrationReplicateManifest"))
        dev_truth = {t for h in dev_sets
                     for t in datasets[h].truth_record_hashes}
        held_truth = {t for h in held_sets
                      for t in datasets[h].truth_record_hashes}
        for truth in sorted(dev_truth & held_truth):
            seen = seen.merged(ValidationResult(
                VALID, (),
                (f"shared truth definition across splits (identical bytes): {truth}",)))
        by_cell_truth = {}
        for identity in sorted(replicates):
            record = replicates[identity]
            if record.truth_record_hash is not None:
                by_cell_truth.setdefault(record.parameter_cell_id, {}).setdefault(
                    record.split_assignment, set()).add(record.truth_record_hash)
        for cell in sorted(by_cell_truth):
            per_split = by_cell_truth[cell]
            if (SplitAssignment.DEV in per_split and SplitAssignment.HELD_OUT in per_split
                    and len(per_split[SplitAssignment.DEV]
                            | per_split[SplitAssignment.HELD_OUT]) > 1):
                seen = seen.merged(ValidationResult(INVALID, (_violation(
                    "truth_substituted_across_splits",
                    record_type="CalibrationReplicateManifest", identity=cell,
                    observed=sorted(per_split[SplitAssignment.DEV]
                                    | per_split[SplitAssignment.HELD_OUT])),)))
    return seen


__all__ = ["VALID", "INVALID", "INCOMPLETE", "ValidationResult", "validate_plan",
           "validate_dataset", "validate_replicates", "validate_heldout_evaluation",
           "validate_graph"]
