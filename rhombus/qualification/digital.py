"""Pilot-specific digital claim assessment using the existing claim engine.

Physical experimental gates are intentionally absent from these requirements.
Missing computational applicability/convergence still prevents qualification.
This does not expose an approval or compute-dispatch capability.
"""
from __future__ import annotations

from rudeus.science.claims import evaluate_claim, final_claim_vector
from rudeus.science.contracts import AcceptanceRegion, ClaimSpec, Observation, ObservableType


def assess_pilot_claims(*, candidate_id: str, protocol_hash: str,
                       artifact_hashes: tuple[str, ...], source_verified: bool,
                       numerically_replayed: bool) -> dict:
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("exact candidate identity required")
    if type(source_verified) is not bool or type(numerically_replayed) is not bool:
        raise ValueError("numerical predicates must be booleans, not coerced values")
    if not artifact_hashes:
        raise ValueError("digital assessment requires bound artifacts")
    predicates = {"source_and_structure_identity": source_verified,
                  "numerical_protocol_compliance": numerically_replayed}
    names = (*predicates, "model_applicability", "simulation_convergence",
             "transport_claim_support", "uncertainty")
    specs, assessments = [], []
    for name in names:
        spec = ClaimSpec(
            claim_id=f"digital-pilot:{candidate_id}:{name}", protocol_hash=protocol_hash,
            estimand=name, units="boolean", scope={"candidate_id": candidate_id},
            assumptions=(), applicability_requirements=(), sufficiency_requirements=(),
            admissible_evidence=(ObservableType.DERIVED,), independence_requirements=(),
            provenance_identity=artifact_hashes[0],
            acceptance=AcceptanceRegion(kind="exact", expected=True,
                justification="Explicit pilot digital requirement; does not certify physical experimentation"),
        )
        observation = None
        if name in predicates:
            observation = Observation(
                quantity=name, units="boolean", value=predicates[name], species=(),
                conditions={"candidate_id": candidate_id}, reference_frame="source-bound-pilot",
                data_support={"kind": "numerical_integration_not_material_qualification"},
                estimator="bound-artifact-verification", estimator_version="v1",
                protocol_hash=protocol_hash, artifact_hashes=artifact_hashes,
                observable_type=ObservableType.DERIVED,
            )
        specs.append(spec)
        assessments.append(evaluate_claim(spec, observation))
    vector = final_claim_vector(tuple(specs), tuple(assessments))
    return {"schema_version": "rhombus-digital-pilot-qualification-v1",
        "candidate_id": candidate_id, "claim_vector": vector,
        "assessments": [a.to_dict() for a in assessments],
        "qualification": "ABSTAIN", "qualified_survivor": False,
        "physical_experimental_confirmation": "NOT_ASSESSED_OUTSIDE_REQUIRED_DIGITAL_SCOPE",
        "limitations": ["PILOT_MODEL_APPLICABILITY_UNQUALIFIED", "SUB_PS_UNIT_CELL_NOT_CONVERGED_TRANSPORT",
                        "UNCERTAINTY_UNCALIBRATED", "NO_PRODUCTION_AUTHORIZATION"]}
