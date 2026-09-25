"""G.1 calibration dataset & truth identity schemas (schema-only, no qualification).

Scope: immutable identity for calibration scope, truth, dataset, replicate,
and development/held-out provenance. This module establishes NO thresholds,
coverage rules, acceptance regions, candidate verdicts, or qualification.
P3 remains DIAGNOSTIC_ONLY / UNKNOWN / NEEDS EVIDENCE.

Canonicalization policy (frozen with these schemas):
- Explicit null: every ``None`` is serialized as JSON ``null`` and IS part of
  the content hash. No field in this module uses ``omit_none``; absence must
  never silently disappear from scope identity.
- Numerics: no normalization is performed. ``1`` and ``1.0`` hash differently,
  as do ``0.0`` and ``-0.0``. Non-finite values are rejected by
  ``canonical_bytes`` (``allow_nan=False``); non-serializable types (e.g.
  numpy scalars) are likewise rejected. Prefer rejection over silent coercion.
- Version binding: every record carries an explicit ``version`` string pinned
  to its schema identity; the version is part of the hashed bytes. Versions
  are never inferred from module, branch, or filename.
- Hash references: records reference other artifacts by full SHA-256 content
  hash (validated with ``require_hash``). Large payloads (trajectories,
  coordinates) are never embedded.
- Failure lanes: computational outcomes reuse the ``FailureClass`` vocabulary
  from ``rudeus.execution.contracts``; scientific/censoring outcomes use a
  separate free reason-code string. The two lanes are never merged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rudeus.execution.contracts import FailureClass
from rudeus.science.contracts import Record, require_hash


class CalibrationClass(str, Enum):
    ISOTROPIC_BROWNIAN = "isotropic_brownian"
    ANISOTROPIC_BROWNIAN = "anisotropic_brownian"
    CAGED_CONFINED = "caged_confined"
    HOPPING_INTERMITTENT = "hopping_intermittent"
    TEMPORALLY_CORRELATED = "temporally_correlated"
    PARTICLE_CORRELATED = "particle_correlated"
    FINITE_TRAJECTORY = "finite_trajectory"
    PBC_RECONSTRUCTION = "pbc_reconstruction"
    FINITE_CELL = "finite_cell"
    REALISTIC_TRAJECTORY = "realistic_trajectory"
    SELECTION_STOPPING = "selection_stopping"


class TruthType(str, Enum):
    ANALYTICAL = "analytical"
    GENERATED_MODEL = "generated_model"
    REFERENCE_COMPUTATION = "reference_computation"
    EMPIRICAL_REFERENCE = "empirical_reference"
    UNKNOWN = "unknown"


class SplitAssignment(str, Enum):
    DEV = "DEV"
    HELD_OUT = "HELD_OUT"


STATISTICAL_INTERPRETATIONS = ("ensemble", "pathwise", "unspecified")
WINDOW_INTERPRETATIONS = ("finite_window", "long_time", "unspecified")
CELL_INTERPRETATIONS = ("finite_cell", "bulk", "unspecified")


def _require_nonempty_str(value, name):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a nonempty string")


def _require_hashes(values, name):
    for value in values:
        require_hash(value)


@dataclass(frozen=True, kw_only=True)
class CalibrationScope(Record):
    """Canonical calibration scope tuple with a stable content hash.

    ``content_hash`` of this record IS the ``calibration_scope_hash``. Any
    change to estimator, resampler, window, cadence, duration, composition,
    temperature regime, dependence model, reconstruction policy, cell regime,
    truth model, generator version, or selection policy yields a new scope.
    No inheritance or applicability rules are defined here.
    """

    estimator: str
    estimator_version: str
    resampling_method: str
    resampling_version: str
    protocol_hash: str
    estimand: str
    units: str
    generator_class: CalibrationClass
    generator_version: str
    truth_type: TruthType
    truth_model_version: str
    species_composition: dict
    n_particles: int
    duration_ps: float
    sampling_interval_ps: float
    lag_steps: tuple[int, ...]
    fit_window_ps: tuple[float, float] | None = None
    temperature_K: float | None = None
    cell_geometry: dict | None = None
    coordinate_regime: str | None = None
    reference_frame: str | None = None
    dependence_regime: str | None = None
    selection_policy: str | None = None
    code_revision: str = ""
    generator_hash: str | None = None
    reference_computation_hash: str | None = None
    version: str = "calibration-scope-v1"

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        if isinstance(value.get("generator_class"), str):
            value["generator_class"] = CalibrationClass(value["generator_class"])
        if isinstance(value.get("truth_type"), str):
            value["truth_type"] = TruthType(value["truth_type"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.version != "calibration-scope-v1":
            raise ValueError("unsupported calibration scope version")
        for name in ("estimator", "estimator_version", "resampling_method",
                     "resampling_version", "estimand", "units",
                     "generator_version", "truth_model_version", "code_revision"):
            _require_nonempty_str(getattr(self, name), name)
        CalibrationClass(self.generator_class)
        TruthType(self.truth_type)
        require_hash(self.protocol_hash)
        if (not self.species_composition
                or any(not isinstance(k, str) or not k for k in self.species_composition)
                or any(isinstance(v, bool) or not isinstance(v, int) or v < 1
                       for v in self.species_composition.values())):
            raise ValueError("species composition must map nonempty symbols to positive counts")
        if isinstance(self.n_particles, bool) or not isinstance(self.n_particles, int):
            raise ValueError("particle count must be an integer")
        if sum(self.species_composition.values()) != self.n_particles:
            raise ValueError("species counts must sum to the particle count")
        for name in ("duration_ps", "sampling_interval_ps"):
            number = getattr(self, name)
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                raise ValueError(f"{name} must be numeric")
        if (not self.lag_steps or len(set(self.lag_steps)) != len(self.lag_steps)
                or any(isinstance(v, bool) or not isinstance(v, int) or v < 1
                       for v in self.lag_steps)
                or any(b <= a for a, b in zip(self.lag_steps, self.lag_steps[1:]))):
            raise ValueError("lag steps must be increasing positive integers")
        if self.fit_window_ps is not None and (
                len(self.fit_window_ps) != 2
                or not 0 <= self.fit_window_ps[0] < self.fit_window_ps[1]):
            raise ValueError("invalid explicit fit window")
        for name in ("coordinate_regime", "reference_frame", "dependence_regime",
                     "selection_policy"):
            if getattr(self, name) is not None:
                _require_nonempty_str(getattr(self, name), name)
        for name in ("generator_hash", "reference_computation_hash"):
            if getattr(self, name) is not None:
                require_hash(getattr(self, name))


@dataclass(frozen=True, kw_only=True)
class GeneratorSpec(Record):
    """Hashable specification of a calibration data generator procedure."""

    calibration_class: CalibrationClass
    generator_name: str
    generator_version: str
    parameters: dict
    initialization_spec: dict
    seed_semantics: str
    output_coordinate_contract: dict
    cell_pbc_contract: dict | None = None
    truth_definition: dict | None = None
    limitations: tuple[str, ...] = ()
    code_hash: str = ""
    config_hash: str | None = None
    version: str = "generator-spec-v1"

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        if isinstance(value.get("calibration_class"), str):
            value["calibration_class"] = CalibrationClass(value["calibration_class"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.version != "generator-spec-v1":
            raise ValueError("unsupported generator specification version")
        CalibrationClass(self.calibration_class)
        for name in ("generator_name", "generator_version", "seed_semantics"):
            _require_nonempty_str(getattr(self, name), name)
        for limitation in self.limitations:
            _require_nonempty_str(limitation, "limitation")
        require_hash(self.code_hash)
        if self.config_hash is not None:
            require_hash(self.config_hash)


@dataclass(frozen=True, kw_only=True)
class TruthRecord(Record):
    """Typed scientific truth/reference for a calibration scope or replicate.

    Ensemble, pathwise, finite-window, long-time, finite-cell, and bulk
    quantities are distinct interpretation axes; this schema cannot equate
    them. ``UNKNOWN`` truth carries no value, only an unavailable reason.
    """

    estimand: str
    units: str
    truth_type: TruthType
    value: dict | None = None
    unavailable_reason: str | None = None
    statistical_interpretation: str = "unspecified"
    window_interpretation: str = "unspecified"
    cell_interpretation: str = "unspecified"
    generator_spec_hash: str | None = None
    parameter_set_hash: str | None = None
    seed: int | None = None
    initialization_hash: str | None = None
    code_revision: str = ""
    protocol_hash: str | None = None
    derivation_hashes: tuple[str, ...] = ()
    approximation_notes: dict | None = None
    version: str = "truth-record-v1"

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        if isinstance(value.get("truth_type"), str):
            value["truth_type"] = TruthType(value["truth_type"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.version != "truth-record-v1":
            raise ValueError("unsupported truth record version")
        for name in ("estimand", "units"):
            _require_nonempty_str(getattr(self, name), name)
        TruthType(self.truth_type)
        if (self.value is None) == (self.unavailable_reason is None):
            raise ValueError("truth carries either a value or an unavailable reason, not both")
        if self.unavailable_reason is not None:
            _require_nonempty_str(self.unavailable_reason, "unavailable_reason")
        if self.statistical_interpretation not in STATISTICAL_INTERPRETATIONS:
            raise ValueError("unknown statistical interpretation")
        if self.window_interpretation not in WINDOW_INTERPRETATIONS:
            raise ValueError("unknown window interpretation")
        if self.cell_interpretation not in CELL_INTERPRETATIONS:
            raise ValueError("unknown cell interpretation")
        for name in ("generator_spec_hash", "parameter_set_hash",
                     "initialization_hash", "protocol_hash"):
            if getattr(self, name) is not None:
                require_hash(getattr(self, name))
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise ValueError("seed identity must be an integer")
        _require_nonempty_str(self.code_revision, "code_revision")
        _require_hashes(self.derivation_hashes, "derivation_hashes")


@dataclass(frozen=True, kw_only=True)
class CalibrationPlan(Record):
    """Frozen calibration plan: scope/split inventory with explicit exclusions."""

    objective: str
    scope_hashes: tuple[str, ...]
    class_inventory: tuple[CalibrationClass, ...]
    parameter_cell_ids: tuple[str, ...]
    truth_requirements: dict
    split_rules: dict
    seed_policy: dict
    dev_replicate_ids: tuple[str, ...]
    heldout_replicate_ids: tuple[str, ...]
    independence_rules: dict
    selection_stopping_policy: dict
    frozen_analysis_fields: tuple[str, ...]
    exclusions: tuple[dict, ...] = ()
    protocol_config_hashes: dict | None = None
    code_revision: str = ""
    version: str = "calibration-plan-v1"

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["class_inventory"] = tuple(
            CalibrationClass(v) if isinstance(v, str) else v
            for v in value.get("class_inventory", ()))
        return cls(**value)

    def validate(self):
        super().validate()
        if self.version != "calibration-plan-v1":
            raise ValueError("unsupported calibration plan version")
        _require_nonempty_str(self.objective, "objective")
        if not self.scope_hashes:
            raise ValueError("at least one calibration scope hash is required")
        _require_hashes(self.scope_hashes, "scope_hashes")
        if not self.class_inventory:
            raise ValueError("at least one calibration class is required")
        for member in self.class_inventory:
            CalibrationClass(member)
        for name in ("parameter_cell_ids", "frozen_analysis_fields"):
            ids = getattr(self, name)
            if not ids or len(set(ids)) != len(ids):
                raise ValueError(f"{name} must be nonempty and unique")
            for _id in ids:
                _require_nonempty_str(_id, name)
        for name in ("dev_replicate_ids", "heldout_replicate_ids"):
            for _id in getattr(self, name):
                _require_nonempty_str(_id, name)
        if set(self.dev_replicate_ids) & set(self.heldout_replicate_ids):
            raise ValueError("development and held-out replicate sets must be disjoint")
        for exclusion in self.exclusions:
            if not isinstance(exclusion.get("id"), str) or not exclusion["id"]:
                raise ValueError("exclusions require an id")
            if not isinstance(exclusion.get("reason"), str) or not exclusion["reason"]:
                raise ValueError("exclusions require a reason")
        if self.protocol_config_hashes is not None:
            for value in self.protocol_config_hashes.values():
                require_hash(value)
        _require_nonempty_str(self.code_revision, "code_revision")


@dataclass(frozen=True, kw_only=True)
class CalibrationDatasetManifest(Record):
    """Immutable inventory of calibration replicates for one scope and split.

    Split assignment is a hashed enum field of this record, never a sidecar
    label. Trajectories and truth records are referenced by hash only.
    """

    dataset_id: str
    plan_hash: str
    scope_hash: str
    calibration_class: CalibrationClass
    parameter_cell_ids: tuple[str, ...]
    trajectory_ids: tuple[str, ...]
    truth_record_hashes: tuple[str, ...]
    split_assignment: SplitAssignment
    generator_spec_hashes: tuple[str, ...]
    artifact_manifest_hashes: tuple[str, ...]
    attempted_replicate_ids: tuple[str, ...]
    version: str = "calibration-dataset-v1"

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        if isinstance(value.get("calibration_class"), str):
            value["calibration_class"] = CalibrationClass(value["calibration_class"])
        if isinstance(value.get("split_assignment"), str):
            value["split_assignment"] = SplitAssignment(value["split_assignment"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.version != "calibration-dataset-v1":
            raise ValueError("unsupported calibration dataset version")
        _require_nonempty_str(self.dataset_id, "dataset_id")
        require_hash(self.plan_hash)
        require_hash(self.scope_hash)
        CalibrationClass(self.calibration_class)
        SplitAssignment(self.split_assignment)
        if not self.parameter_cell_ids:
            raise ValueError("at least one parameter cell is required")
        for name in ("parameter_cell_ids", "trajectory_ids", "attempted_replicate_ids"):
            for _id in getattr(self, name):
                _require_nonempty_str(_id, name)
        for name in ("truth_record_hashes", "generator_spec_hashes",
                     "artifact_manifest_hashes"):
            _require_hashes(getattr(self, name), name)


@dataclass(frozen=True, kw_only=True)
class CalibrationReplicateManifest(Record):
    """Identity, lineage, and dual-lane status of one calibration replicate.

    Computational outcome (``FailureClass`` vocabulary) and scientific outcome
    (diagnostic reason-code string) are independent fields and are never
    merged. A zero-event hopping replicate (``event_count`` 0) is a valid
    completed replicate, not a failure; no minimum event count exists.
    """

    replicate_id: str
    dataset_id: str
    parameter_cell_id: str
    split_assignment: SplitAssignment
    independence_declaration: dict
    shared_parent_refs: tuple[str, ...] = ()
    seed: int | None = None
    initialization_hash: str | None = None
    trajectory_artifact_hash: str | None = None
    truth_record_hash: str | None = None
    conditions: dict | None = None
    dependence_descriptors: dict | None = None
    event_info: dict | None = None
    execution_attempt_hash: str | None = None
    computational_outcome: str | None = None
    scientific_outcome: str | None = None
    outcome_notes: dict | None = None
    version: str = "calibration-replicate-v1"

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        if isinstance(value.get("split_assignment"), str):
            value["split_assignment"] = SplitAssignment(value["split_assignment"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.version != "calibration-replicate-v1":
            raise ValueError("unsupported calibration replicate version")
        for name in ("replicate_id", "dataset_id", "parameter_cell_id"):
            _require_nonempty_str(getattr(self, name), name)
        SplitAssignment(self.split_assignment)
        for ref in self.shared_parent_refs:
            _require_nonempty_str(ref, "shared_parent_ref")
        if self.seed is not None and (isinstance(self.seed, bool) or not isinstance(self.seed, int)):
            raise ValueError("seed identity must be an integer")
        for name in ("initialization_hash", "trajectory_artifact_hash",
                     "truth_record_hash", "execution_attempt_hash"):
            if getattr(self, name) is not None:
                require_hash(getattr(self, name))
        if self.event_info is not None and "event_count" in self.event_info:
            count = self.event_info["event_count"]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError("event count must be a nonnegative integer")
        if self.computational_outcome is not None:
            FailureClass(self.computational_outcome)
        if self.scientific_outcome is not None:
            _require_nonempty_str(self.scientific_outcome, "scientific_outcome")


@dataclass(frozen=True, kw_only=True)
class HeldoutEvaluationManifest(Record):
    """Provenance identity of one held-out evaluation execution.

    Records what was evaluated, on what frozen data, with what code — it does
    not qualify the estimator, assign confidence bounds, or decide verdicts.
    """

    plan_hash: str
    heldout_dataset_hashes: tuple[str, ...]
    estimator_spec_hash: str
    resampling_spec_hash: str
    protocol_hash: str
    code_revision: str
    bundle_hash: str | None = None
    execution_attempt_hashes: tuple[str, ...] = ()
    result_artifact_hashes: tuple[str, ...] = ()
    outcome_inventory: tuple[dict, ...] = ()
    unblinding_declaration: dict | None = None
    version: str = "heldout-evaluation-v1"

    def validate(self):
        super().validate()
        if self.version != "heldout-evaluation-v1":
            raise ValueError("unsupported held-out evaluation version")
        require_hash(self.plan_hash)
        if not self.heldout_dataset_hashes:
            raise ValueError("at least one held-out dataset hash is required")
        _require_hashes(self.heldout_dataset_hashes, "heldout_dataset_hashes")
        for name in ("estimator_spec_hash", "resampling_spec_hash", "protocol_hash"):
            require_hash(getattr(self, name))
        _require_nonempty_str(self.code_revision, "code_revision")
        if self.bundle_hash is not None:
            require_hash(self.bundle_hash)
        for name in ("execution_attempt_hashes", "result_artifact_hashes"):
            _require_hashes(getattr(self, name), name)
        for row in self.outcome_inventory:
            if not isinstance(row.get("replicate_id"), str) or not row["replicate_id"]:
                raise ValueError("outcome inventory rows require a replicate_id")
            if ("computational_outcome" in row and row["computational_outcome"] is not None):
                FailureClass(row["computational_outcome"])
        if self.unblinding_declaration is not None and (
                not isinstance(self.unblinding_declaration.get("state"), str)
                or not self.unblinding_declaration["state"]):
            raise ValueError("unblinding declaration requires a state")
