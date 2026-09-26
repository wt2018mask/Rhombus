"""Bind MatterSim transport results into the generic X observation contract.

This module converts a verified X trajectory-derived D_self result into
XModelIdentity/XInputBinding/XObservation objects. It does not invent comparison
tolerances and therefore cannot by itself produce AGREEMENT/DISAGREEMENT.
"""

from __future__ import annotations

from typing import Any, Mapping

from rudeus.science.contracts import digest, require_hash
from rudeus.science.x_mattersim_protocol import MatterSimXProtocol
from rudeus.science.x_mattersim_scientific import MatterSimXExecutionSpec
from rudeus.science.xcheck import XInputBinding, XModelIdentity, XObservation


IMPLEMENTATION_ID = "rudeus.science.x_mattersim_observation.v1"


def mattersim_model_identity(
    admission: MatterSimXExecutionSpec,
    *,
    code_revision: str,
) -> XModelIdentity:
    require_hash(code_revision)
    return XModelIdentity(
        model_name=admission.model_name,
        model_family=admission.model_family,
        checkpoint_sha256=admission.checkpoint_sha256,
        code_revision=code_revision,
        implementation_id=IMPLEMENTATION_ID,
        training_data_id=admission.training_data_id,
    )


def mattersim_input_binding(
    admission: MatterSimXExecutionSpec,
    protocol: MatterSimXProtocol,
) -> XInputBinding:
    if protocol.target_species != admission.target_species:
        raise ValueError("MatterSim X observation target species mismatch")
    if protocol.temperature_K != admission.temperature_K:
        raise ValueError("MatterSim X observation temperature mismatch")
    if protocol.source_p3_protocol_hash != admission.p3_protocol_hash:
        raise ValueError("MatterSim X observation P3 protocol binding mismatch")

    return XInputBinding(
        candidate_id=admission.candidate_id,
        structure_sha256=admission.start_structure_sha256,
        protocol_hash=protocol.content_hash,
        quantity="D_self",
        units="m2/s",
        conditions={
            "temperature_K": protocol.temperature_K,
            "species": [protocol.target_species],
            "reference_frame": protocol.reference_frame,
            "ensemble": protocol.ensemble,
            "cell_mode": protocol.cell_mode,
        },
    )


def mattersim_observation(
    *,
    admission: MatterSimXExecutionSpec,
    protocol: MatterSimXProtocol,
    transport_result: Mapping[str, Any],
    code_revision: str,
) -> tuple[XModelIdentity, XInputBinding, XObservation]:
    model = mattersim_model_identity(admission, code_revision=code_revision)
    binding = mattersim_input_binding(admission, protocol)

    required = {
        "quantity", "units", "value", "estimator_id", "trajectory_sha256",
        "scientific_verdict_changed",
    }
    if not required.issubset(transport_result):
        raise ValueError("MatterSim X transport result incomplete")
    if transport_result["quantity"] != binding.quantity:
        raise ValueError("MatterSim X transport quantity mismatch")
    if transport_result["units"] != binding.units:
        raise ValueError("MatterSim X transport units mismatch")
    if transport_result["estimator_id"] != protocol.estimator_id:
        raise ValueError("MatterSim X estimator mismatch")
    if transport_result["scientific_verdict_changed"] is not False:
        raise ValueError("MatterSim X transport result must not change verdict")

    evidence_hash = transport_result["trajectory_sha256"]
    require_hash(evidence_hash)
    value = transport_result["value"]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("MatterSim X D_self must be numeric")

    observation = XObservation(
        model_hash=model.content_hash,
        input_binding_hash=binding.content_hash,
        quantity=binding.quantity,
        units=binding.units,
        value=float(value),
        evidence_hash=evidence_hash,
        estimator_id=protocol.estimator_id,
    )
    return model, binding, observation


def comparison_ready(
    *,
    primary_binding: XInputBinding,
    cross_binding: XInputBinding,
) -> dict:
    """Report whether both sides share an exactly comparable X input scope."""
    if primary_binding == cross_binding:
        return {
            "status": "READY",
            "binding_hash": primary_binding.content_hash,
            "reason_codes": (),
        }
    return {
        "status": "BLOCKED_SCOPE_MISMATCH",
        "binding_hash": primary_binding.content_hash,
        "cross_binding_hash": cross_binding.content_hash,
        "reason_codes": ("input_binding_mismatch",),
    }
