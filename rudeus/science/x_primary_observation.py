"""Adapt the primary P3 D_self record into the generic X observation contract.

The adapter does not infer a primary model identity. Callers must supply the
already-provenanced XModelIdentity for the primary model. It verifies the P3
observation against the admitted candidate, shared scientific protocol, and
primary trajectory before producing an XObservation.
"""

from __future__ import annotations

from typing import Any, Mapping

from rudeus.science.contracts import require_hash
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec
from rudeus.science.xcheck import XInputBinding, XModelIdentity, XObservation


def primary_p3_observation(
    *,
    p3_payload: Mapping[str, Any],
    admission: MatterSimXExecutionSpec,
    primary_model: XModelIdentity,
) -> tuple[XInputBinding, XObservation]:
    record = p3_payload.get("p3_scientific_record")
    provenance = p3_payload.get("p3_provenance")
    if not isinstance(record, Mapping) or not isinstance(provenance, Mapping):
        raise ValueError("primary P3 scientific record/provenance missing")

    raw = record.get("observation")
    if not isinstance(raw, Mapping):
        raise ValueError("primary P3 D_self observation missing")
    if raw.get("quantity") != "D_self" or raw.get("units") != "m2/s":
        raise ValueError("primary P3 observation is not D_self in m2/s")

    protocol_hash = raw.get("protocol_hash")
    require_hash(protocol_hash)
    if protocol_hash != admission.p3_protocol_hash:
        raise ValueError("primary P3 protocol binding mismatch")
    if provenance.get("p3_config_hash") != admission.p3_protocol_hash:
        raise ValueError("primary P3 provenance protocol mismatch")

    conditions = raw.get("conditions")
    if not isinstance(conditions, Mapping):
        raise ValueError("primary P3 observation conditions missing")
    if conditions.get("candidate_id") != admission.candidate_id:
        raise ValueError("primary P3 candidate mismatch")
    if conditions.get("temperature_K") != admission.temperature_K:
        raise ValueError("primary P3 temperature mismatch")
    if list(conditions.get("species") or []) != [admission.target_species]:
        raise ValueError("primary P3 species mismatch")
    reference_frame = conditions.get("reference_frame")
    if not isinstance(reference_frame, str) or not reference_frame:
        raise ValueError("primary P3 reference frame missing")

    artifact_hashes = raw.get("artifact_hashes")
    if not isinstance(artifact_hashes, (list, tuple)) or admission.trajectory_sha256 not in artifact_hashes:
        raise ValueError("primary P3 trajectory evidence mismatch")
    if provenance.get("trajectory_sha256") != admission.trajectory_sha256:
        raise ValueError("primary P3 provenance trajectory mismatch")

    value = raw.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("primary P3 D_self must be numeric")

    estimator = raw.get("estimator")
    if not isinstance(estimator, str) or not estimator:
        raise ValueError("primary P3 estimator missing")

    binding = XInputBinding(
        candidate_id=admission.candidate_id,
        structure_sha256=admission.start_structure_sha256,
        protocol_hash=admission.p3_protocol_hash,
        quantity="D_self",
        units="m2/s",
        conditions={
            "temperature_K": admission.temperature_K,
            "species": [admission.target_species],
            "reference_frame": reference_frame,
        },
    )
    observation = XObservation(
        model_hash=primary_model.content_hash,
        input_binding_hash=binding.content_hash,
        quantity="D_self",
        units="m2/s",
        value=float(value),
        evidence_hash=admission.trajectory_sha256,
        estimator_id=estimator,
    )
    return binding, observation
