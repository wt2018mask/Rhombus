"""Build source-bound representation-policy evidence for cubic Al-LLZO."""
from __future__ import annotations

from pathlib import Path

from rudeus.science.known_material_b4_execution_structure import ExecutionStructureBinding
from rudeus.science.known_material_cubic_llzo_representation_amendment import (
    CONSTRAINT_SCOPE,
    build_cubic_llzo_representation_amendment_candidate,
)
from rudeus.science.known_material_cubic_llzo_weighted_evidence import (
    build_cubic_llzo_weighted_representation_evidence,
)
from rudeus.science.known_material_fractional_occupancy import (
    FRACTIONAL_OCCUPANCY_STRATEGY_VERSION,
    FractionalOccupancyExecutionStrategy,
)
from rudeus.science.known_material_representation_policy import (
    RepresentationEvidenceDisposition,
    RepresentationPolicyEvidence,
)


POLICY_ID = "fractional-occupancy-explicit-v1"
INPUT_KEY = "fractional_occupancy_execution_strategy"
GENERATION_METHOD = "exact-weighted-two-cell-constraint-aware-v2"
PRE_AMENDMENT_EXECUTION_HASH = (
    "0ce55065f464292b34919e31bab12947cddea8c26bf2521323fd3f8714d5e475"
)
WEIGHTING_ASSUMPTION = "independent-marginal-product-no-source-correlation-claim-v1"


def build_cubic_llzo_fractional_occupancy_policy_evidence(
    cif_path: Path,
    *,
    source_artifact_hash: str,
) -> tuple[
    FractionalOccupancyExecutionStrategy,
    ExecutionStructureBinding,
    RepresentationPolicyEvidence,
]:
    weighted = build_cubic_llzo_weighted_representation_evidence(
        cif_path,
        source_artifact_hash=source_artifact_hash,
    )
    candidate = build_cubic_llzo_representation_amendment_candidate(
        cif_path,
        source_artifact_hash=source_artifact_hash,
        old_binding_hash=PRE_AMENDMENT_EXECUTION_HASH,
    )
    execution = candidate.candidate_binding
    fractions = tuple(item.weight for item in weighted.bindings)

    strategy = FractionalOccupancyExecutionStrategy(
        strategy_version=FRACTIONAL_OCCUPANCY_STRATEGY_VERSION,
        source_artifact_hash=source_artifact_hash,
        realization_hashes=tuple(
            component.structure_hash for component in execution.components
        ),
        realization_weights=tuple(float(value) for value in fractions),
        composition_preserved=True,
        occupancy_statistics_preserved=True,
        deterministic_generation=True,
        generation_method=GENERATION_METHOD,
        provenance_refs=(
            f"source-artifact:{source_artifact_hash}",
            f"weighted-marginal-evidence:{weighted.content_hash}",
            f"b5-representation-amendment:{candidate.content_hash}",
        ),
        bias_assessment=(
            "declared Li1, Al1, and Li2 marginal occupancies remain exactly preserved by rational weights",
            "execution realizations enforce only explicit P0 geometry exclusions discovered during DEV falsification",
            "the diffraction source does not resolve configurational correlations; no source-correlation claim is introduced",
        ),
    )

    entry = RepresentationPolicyEvidence(
        policy_id=POLICY_ID,
        input_key=INPUT_KEY,
        disposition=RepresentationEvidenceDisposition.SATISFIED.value,
        provenance_hash=candidate.content_hash,
        evidence_refs=(
            source_artifact_hash,
            weighted.content_hash,
            candidate.content_hash,
            strategy.content_hash,
            execution.visible_structure_hash,
        ),
        payload={
            "strategy_hash": strategy.content_hash,
            "weighted_marginal_evidence_hash": weighted.content_hash,
            "representation_amendment_hash": candidate.content_hash,
            "execution_structure_hash": execution.visible_structure_hash,
            "weighting_assumption": WEIGHTING_ASSUMPTION,
            "correlation_scope": weighted.correlation_scope,
            "constraint_scope": CONSTRAINT_SCOPE,
            "exact_weight_fractions": tuple(
                (value.numerator, value.denominator) for value in fractions
            ),
            "declared_marginal_occupancies": {
                "Li1": weighted.declared_li1_occupancy,
                "Al1": weighted.declared_al1_occupancy,
                "Li2": weighted.declared_li2_occupancy,
            },
            "weighted_formula": {
                "Li": weighted.weighted_li_formula,
                "Al": weighted.weighted_al_formula,
            },
            "reported_formula": {
                "Li": weighted.reported_li_formula,
                "Al": weighted.reported_al_formula,
            },
        },
        rationale=(
            "retain the exact source-derived eight-member rational-weight marginal schedule",
            "replace only the nonphysical independent ordered realization with deterministic geometry-constraint-aware realization",
            "treat execution geometry exclusions as representation validity constraints, not as inferred source configurational correlations",
        ),
    )
    return strategy, execution, entry
