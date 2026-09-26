"""MatterSim scientific-X admission gate.

This module does not execute MatterSim or MD. It converts verified upstream
P2/P2.5 state into an execution authorization only when the candidate is a
qualified transport entrant. Preflight-only G/P1 structures and NONDIFFUSIVE
controls cannot enter scientific X.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from rudeus.science.contracts import Record, digest, require_hash
from rudeus.science.x_mattersim_preflight import (
    CHECKPOINT_LABEL,
    EXPECTED_CHECKPOINT_SHA256,
    EXPECTED_MATTERSIM_VERSION,
    MODEL_FAMILY,
    TRAINING_DATA_ID,
)


@dataclass(frozen=True, kw_only=True)
class MatterSimXExecutionSpec(Record):
    candidate_id: str
    batch_id: str
    target_species: str
    temperature_K: float
    source_p2_hash: str
    source_p25_hash: str
    p3_protocol_hash: str
    trajectory_sha256: str
    model_name: str = CHECKPOINT_LABEL
    model_family: str = MODEL_FAMILY
    checkpoint_sha256: str = EXPECTED_CHECKPOINT_SHA256
    training_data_id: str = TRAINING_DATA_ID
    mattersim_version: str = EXPECTED_MATTERSIM_VERSION
    purpose: str = "independent_transport_crosscheck"

    def validate(self):
        super().validate()
        for value in (
            self.source_p2_hash,
            self.source_p25_hash,
            self.p3_protocol_hash,
            self.trajectory_sha256,
            self.checkpoint_sha256,
        ):
            require_hash(value)
        if not self.candidate_id or not self.batch_id or not self.target_species:
            raise ValueError("complete MatterSim X execution identity is required")
        if self.temperature_K <= 0:
            raise ValueError("MatterSim X requires positive temperature")
        if self.purpose != "independent_transport_crosscheck":
            raise ValueError("unsupported MatterSim X purpose")


def _result(payload: Mapping[str, Any], stage: str) -> Mapping[str, Any]:
    value = payload.get("result")
    if not isinstance(value, Mapping):
        raise ValueError(f"{stage} payload missing result mapping")
    return value


def admit_mattersim_x(
    p2_payload: Mapping[str, Any],
    p25_payload: Mapping[str, Any],
    *,
    p3_protocol_hash: str,
) -> MatterSimXExecutionSpec:
    """Fail closed unless exact P2/P2.5 DIFFUSIVE admission requirements hold."""
    require_hash(p3_protocol_hash)
    p2 = _result(p2_payload, "P2")
    p25 = _result(p25_payload, "P2.5")

    if p2.get("p2_verdict") != "PASS" or p2.get("dynamic_state") != "PASS":
        raise ValueError("MatterSim X requires P2 PASS dynamic stability")
    if p25.get("p2_verdict") != "PASS" or p25.get("p2_dynamic_state") != "PASS":
        raise ValueError("MatterSim X requires P2.5 bound to P2 PASS")
    if p25.get("transport_state") != "DIFFUSIVE" or p25.get("p25_verdict") != "DIFFUSIVE":
        raise ValueError("MatterSim X requires P2.5 DIFFUSIVE transport state")

    candidate_id = p2.get("candidate_material_id")
    batch_id = p2_payload.get("batch_id")
    temperature = p2.get("temperature_K")
    target_species = p25.get("target_species")
    binding = p2.get("trajectory_artifact")
    provenance = p25.get("provenance")

    if not isinstance(binding, Mapping) or not isinstance(provenance, Mapping):
        raise ValueError("MatterSim X requires bound trajectory provenance")
    trajectory_sha = binding.get("sha256")
    require_hash(trajectory_sha)

    pairs = (
        ("candidate", p25.get("candidate_material_id"), candidate_id),
        ("batch", p25.get("batch_id"), batch_id),
        ("temperature", p25.get("temperature_K"), temperature),
        ("trajectory", provenance.get("trajectory_artifact_sha256"), trajectory_sha),
        ("p2_config", provenance.get("p2_config_hash"), p2.get("p2_config_hash")),
        ("p2_protocol", provenance.get("p2_protocol_version"), p2.get("p2_protocol_version")),
        ("p2_seed", provenance.get("p2_seed"), p2.get("seed")),
        ("artifact_format", provenance.get("artifact_format_version"), binding.get("format_version")),
    )
    for label, left, right in pairs:
        if left != right:
            raise ValueError(f"MatterSim X {label} provenance mismatch")

    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("MatterSim X candidate identity missing")
    if not isinstance(batch_id, str) or not batch_id:
        raise ValueError("MatterSim X batch identity missing")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or temperature <= 0:
        raise ValueError("MatterSim X temperature missing or invalid")
    if not isinstance(target_species, str) or not target_species:
        raise ValueError("MatterSim X target species missing")

    return MatterSimXExecutionSpec(
        candidate_id=candidate_id,
        batch_id=batch_id,
        target_species=target_species,
        temperature_K=float(temperature),
        source_p2_hash=digest(p2_payload),
        source_p25_hash=digest(p25_payload),
        p3_protocol_hash=p3_protocol_hash,
        trajectory_sha256=trajectory_sha,
    )
