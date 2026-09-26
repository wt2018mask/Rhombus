"""Versioned, deeply immutable scientific sidecars. Legacy schema is untouched."""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

UNRESOLVED = "UNKNOWN / NEEDS EVIDENCE"
VERSION = "scientific-freeze-v1"


def plain(value):
    if is_dataclass(value):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)
                if not (f.metadata.get("omit_none") and getattr(value, f.name) is None)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def canonical_bytes(value) -> bytes:
    return json.dumps(plain(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def freeze(value):
    if isinstance(value, Mapping):
        if any(not isinstance(k, str) for k in value):
            raise ValueError("contract mapping keys must be strings")
        return MappingProxyType({k: freeze(v) for k, v in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(v) for v in value)
    return value


def require_hash(value: str):
    if not isinstance(value, str) or len(value) != 64 or any(
            c not in "0123456789abcdef" for c in value):
        raise ValueError("expected full lowercase SHA256")


@dataclass(frozen=True, kw_only=True)
class Record:
    schema_version: str = VERSION

    def __post_init__(self):
        for f in fields(self):
            object.__setattr__(self, f.name, freeze(getattr(self, f.name)))
        canonical_bytes(self)  # Reject nonfinite/nonserializable metadata.
        self.validate()

    def validate(self):
        if self.schema_version != VERSION:
            raise ValueError("unsupported sidecar schema version")

    def to_dict(self):
        return plain(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**value)

    @property
    def content_hash(self):
        return digest(self)


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    UNKNOWN = "UNKNOWN"


class ObservableType(str, Enum):
    SIMULATED = "simulated_observable"
    DERIVED = "derived_quantity"
    ESTIMATE = "model_estimate"
    PARAMETER = "fitted_parameter"
    PREDICTION = "prediction"
    EXTRAPOLATION = "extrapolation"
    EXPERIMENTAL = "experimental_measurement"


@dataclass(frozen=True, kw_only=True)
class AcceptanceRegion(Record):
    """Closed interval or exact boolean predicate; no implicit acceptance region."""
    kind: str
    justification: str
    lower: float | None = None
    upper: float | None = None
    expected: bool | None = None
    status: str = "PROVISIONAL"

    def validate(self):
        super().validate()
        if not self.justification or self.status != "PROVISIONAL":
            raise ValueError("acceptance criteria require justification and PROVISIONAL status")
        if self.kind == "interval":
            if self.lower is None and self.upper is None:
                raise ValueError("an unbounded interval cannot define acceptance")
            if self.lower is not None and self.upper is not None and self.lower > self.upper:
                raise ValueError("reversed acceptance bounds")
        elif self.kind != "exact" or not isinstance(self.expected, bool):
            raise ValueError("only interval and explicit boolean predicates are supported")


@dataclass(frozen=True, kw_only=True)
class ClaimSpec(Record):
    claim_id: str
    protocol_hash: str
    estimand: str
    units: str
    scope: Mapping[str, Any]
    assumptions: tuple[str, ...]
    applicability_requirements: tuple[str, ...]
    sufficiency_requirements: tuple[str, ...]
    admissible_evidence: tuple[str, ...]
    independence_requirements: tuple[str, ...]
    provenance_identity: str
    acceptance: AcceptanceRegion | None = None
    uncertainty_requirements: Mapping[str, Any] | None = None

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        if value.get("acceptance") is not None:
            value["acceptance"] = AcceptanceRegion.from_dict(value["acceptance"])
        return cls(**value)

    def validate(self):
        super().validate()
        require_hash(self.protocol_hash)
        require_hash(self.provenance_identity)
        if not self.claim_id or not self.estimand or not self.scope:
            raise ValueError("claim identity, estimand and scope are required")
        if self.acceptance is not None and not isinstance(self.acceptance, AcceptanceRegion):
            raise ValueError("acceptance must be a typed AcceptanceRegion")


@dataclass(frozen=True, kw_only=True)
class Observation(Record):
    quantity: str
    units: str
    value: Any
    species: tuple[str, ...]
    conditions: Mapping[str, Any]
    reference_frame: str
    data_support: Mapping[str, Any]
    estimator: str
    estimator_version: str
    protocol_hash: str
    artifact_hashes: tuple[str, ...]
    observable_type: ObservableType
    fit_window: tuple[float, float] | None = None
    sample_counts: Mapping[str, Any] | None = None
    dependence_counts: Mapping[str, Any] | None = None

    def validate(self):
        super().validate()
        require_hash(self.protocol_hash)
        for h in self.artifact_hashes:
            require_hash(h)
        ObservableType(self.observable_type)
        if not self.estimator or not self.reference_frame or not self.quantity:
            raise ValueError("observation definition is incomplete")


@dataclass(frozen=True, kw_only=True)
class Uncertainty(Record):
    observation_hash: str | None = None
    method: str | None = None
    method_version: str | None = None
    nominal_coverage: float | None = None
    bounds: tuple[float, float] | None = None
    covariance: tuple[tuple[float, ...], ...] | None = None
    resampling_scheme: Mapping[str, Any] | None = None
    block_scheme: Mapping[str, Any] | None = None
    replica_scheme: Mapping[str, Any] | None = None
    seed: int | None = None
    calibration_reference: str | None = None
    covered_error_sources: tuple[str, ...] = ()
    unavailable_reasons: tuple[str, ...] = (UNRESOLVED,)
    qualification: str = UNRESOLVED

    def validate(self):
        super().validate()
        if self.observation_hash is not None:
            require_hash(self.observation_hash)
        if self.nominal_coverage is not None and not 0 < self.nominal_coverage < 1:
            raise ValueError("nominal coverage must lie strictly between zero and one")
        if self.bounds is not None:
            if len(self.bounds) != 2 or self.bounds[0] > self.bounds[1]:
                raise ValueError("invalid confidence interval")
            if self.method is None or self.nominal_coverage is None:
                raise ValueError("interval requires a method and nominal coverage")


@dataclass(frozen=True, kw_only=True)
class ClaimAssessment(Record):
    claim_id: str
    claim_hash: str
    protocol_hash: str
    verdict: Verdict

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["verdict"] = Verdict(value["verdict"])
        return cls(**value)
    assumptions: Mapping[str, Any]
    applicability: Mapping[str, Any]
    statistical_sufficiency: Mapping[str, Any]
    reason_codes: tuple[str, ...]
    supporting_evidence: tuple[str, ...] = ()
    conflicting_evidence: tuple[str, ...] = ()
    unresolved_requirements: tuple[str, ...] = ()

    def validate(self):
        super().validate()
        Verdict(self.verdict)
        require_hash(self.claim_hash)
        require_hash(self.protocol_hash)
