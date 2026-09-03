"""Core data schemas, enums, and state machines for the Rhombus discovery pipeline.

HARD ARCHITECTURAL RULE:
Every candidate material carries THREE independent state fields, never a single collapsed score:
1. existence_state: UNKNOWN | FAIL | PLAUSIBLE | SUPPORTED
2. dynamic_state: NOT_RUN | FAIL | INDETERMINATE | PASS
3. transport_state: NOT_RUN | NONDIFFUSIVE | INDETERMINATE | DIFFUSIVE

Each candidate maintains an append-only evidence-event log. Prior verdicts are NEVER
overwritten; instead, a new EvidenceEvent is appended to the log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ExistenceState(str, Enum):
    """Evaluation of whether the material can exist (thermodynamic/compositional stability)."""
    UNKNOWN = "UNKNOWN"
    FAIL = "FAIL"
    PLAUSIBLE = "PLAUSIBLE"
    SUPPORTED = "SUPPORTED"


class DynamicState(str, Enum):
    """Evaluation of finite-temperature dynamic stability (e.g. no spontaneous disintegration/melting)."""
    NOT_RUN = "NOT_RUN"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"
    PASS = "PASS"


class TransportState(str, Enum):
    """Evaluation of ionic transport and conductivity."""
    NOT_RUN = "NOT_RUN"
    NONDIFFUSIVE = "NONDIFFUSIVE"
    INDETERMINATE = "INDETERMINATE"
    DIFFUSIVE = "DIFFUSIVE"


@dataclass(frozen=True)
class EvidenceEvent:
    """An immutable, append-only record of an empirical or computational evaluation.

    Attributes:
        level: Pipeline level or evaluation stage (e.g. 'P0', 'F2', 'P1', 'P2', 'P3', 'E').
        method: Method or algorithm used (e.g. 'mace_relaxation', 'bvse', 'msd_alpha2').
        conditions: Simulation or experimental conditions (e.g. temperature, timesteps, pressure).
        uncertainty: Optional quantified uncertainty or error estimate.
        source: Provenance identifier (e.g. 'kaggle_shard_042', 'obelix_train', 'colab_worker').
        artifact_hash: Deterministic cryptographic hash of raw input/output artifacts.
        model_or_data_version: Checkpoint version or dataset release tag (e.g. 'medium-mpa-0', 'obelix-v1').
        timestamp: ISO 8601 UTC timestamp of the event.
    """
    level: str
    method: str
    conditions: Dict[str, Any] = field(default_factory=dict)
    uncertainty: Optional[float] = None
    source: str = ""
    artifact_hash: str = ""
    model_or_data_version: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert evidence event to a plain dictionary representation."""
        return {
            "level": self.level,
            "method": self.method,
            "conditions": dict(self.conditions),
            "uncertainty": self.uncertainty,
            "source": self.source,
            "artifact_hash": self.artifact_hash,
            "model_or_data_version": self.model_or_data_version,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceEvent:
        """Create an EvidenceEvent from a dictionary."""
        return cls(
            level=data["level"],
            method=data["method"],
            conditions=dict(data.get("conditions", {})),
            uncertainty=data.get("uncertainty"),
            source=data.get("source", ""),
            artifact_hash=data.get("artifact_hash", ""),
            model_or_data_version=data.get("model_or_data_version", ""),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class CandidateMaterial:
    """A solid-state electrolyte candidate material carrying the three-state-machine verdicts.

    Attributes:
        material_id: Unique deterministic identifier (e.g. hash of normalized composition/structure).
        formula: Chemical formula.
        structure_dict: Optional serialized crystal structure (e.g. pymatgen structure dict).
        existence_state: Current existence classification.
        dynamic_state: Current dynamic stability classification.
        transport_state: Current ionic transport classification.
        evidence_log: Chronological, append-only history of evaluation events.
        metadata: Additional non-verdict metadata (e.g. generation parent, tags).
    """
    material_id: str
    formula: str
    structure_dict: Optional[Dict[str, Any]] = None
    existence_state: ExistenceState = ExistenceState.UNKNOWN
    dynamic_state: DynamicState = DynamicState.NOT_RUN
    transport_state: TransportState = TransportState.NOT_RUN
    evidence_log: List[EvidenceEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_evidence(
        self,
        event: EvidenceEvent,
        new_existence_state: Optional[ExistenceState] = None,
        new_dynamic_state: Optional[DynamicState] = None,
        new_transport_state: Optional[TransportState] = None,
    ) -> None:
        """Append an evidence event and optionally update current tri-state verdicts.

        Prior verdicts are never destroyed; the full history remains in evidence_log.
        """
        self.evidence_log.append(event)
        if new_existence_state is not None:
            self.existence_state = new_existence_state
        if new_dynamic_state is not None:
            self.dynamic_state = new_dynamic_state
        if new_transport_state is not None:
            self.transport_state = new_transport_state

    def to_dict(self) -> Dict[str, Any]:
        """Serialize candidate material to dictionary."""
        return {
            "material_id": self.material_id,
            "formula": self.formula,
            "structure_dict": self.structure_dict,
            "existence_state": self.existence_state.value,
            "dynamic_state": self.dynamic_state.value,
            "transport_state": self.transport_state.value,
            "evidence_log": [e.to_dict() for e in self.evidence_log],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CandidateMaterial:
        """Reconstruct candidate material from dictionary."""
        return cls(
            material_id=data["material_id"],
            formula=data["formula"],
            structure_dict=data.get("structure_dict"),
            existence_state=ExistenceState(data.get("existence_state", ExistenceState.UNKNOWN.value)),
            dynamic_state=DynamicState(data.get("dynamic_state", DynamicState.NOT_RUN.value)),
            transport_state=TransportState(data.get("transport_state", TransportState.NOT_RUN.value)),
            evidence_log=[EvidenceEvent.from_dict(e) for e in data.get("evidence_log", [])],
            metadata=dict(data.get("metadata", {})),
        )
