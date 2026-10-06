"""Build source-bound representation-policy evidence for cubic Al-LLZO."""
from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from rudeus.science.known_material_b4_execution_structure import (
    EXECUTION_STRUCTURE_BINDING_VERSION,
    ExecutionStructureBinding,
    ExecutionStructureComponent,
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
GENERATION_METHOD = "exact-weighted-two-cell-independent-marginals-v1"


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

    fractions = tuple(item.weight for item in weighted.bindings)
    structure_hashes = tuple(item.structure_hash for item in weighted.bindings)
    strategy = FractionalOccupancyExecutionStrategy(
        strategy_version=FRACTIONAL_OCCUPANCY_STRATEGY_VERSION,
        source_artifact_hash=source_artifact_hash,
        realization_hashes=structure_hashes,
        realization_weights=tuple(float(value) for value in fractions),
        composition_preserved=True,
        occupancy_statistics_preserved=True,
        deterministic_generation=True,
        generation_method=GENERATION_METHOD,
        provenance_refs=(
            f"source-artifact:{source_artifact_hash}",
            f"weighted-evidence:{weighted.content_hash}",
        ),
        bias_assessment=(
            "declared Li1, Al1, and Li2 marginal occupancies are preserved exactly by rational weights",
            "occupancy-derived Li6.06 is exact; Al0.1959 is consistent with the retained reported Al0.196 rounding",
            "the diffraction source does not resolve cross-sublattice configurational correlations; no such correlation claim is made",
        ),
    )

    components = tuple(
        ExecutionStructureComponent(
            label=f"member-{item.member_index:02d}",
            structure_hash=item.structure_hash,
            weight_numerator=item.weight_numerator,
            weight_denominator=item.weight_denominator,
        )
        for item in weighted.bindings
    )
    execution = ExecutionStructureBinding(
        binding_version=EXECUTION_STRUCTURE_BINDING_VERSION,
        mode="ENSEMBLE",
        components=components,
        weighting_assumption=weighted.weighting_assumption,
    )

    entry = RepresentationPolicyEvidence(
        policy_id=POLICY_ID,
        input_key=INPUT_KEY,
        disposition=RepresentationEvidenceDisposition.SATISFIED.value,
        provenance_hash=weighted.content_hash,
        evidence_refs=(
            source_artifact_hash,
            weighted.content_hash,
            strategy.content_hash,
            execution.visible_structure_hash,
        ),
        payload={
            "strategy_hash": strategy.content_hash,
            "weighted_representation_evidence_hash": weighted.content_hash,
            "execution_structure_hash": execution.visible_structure_hash,
            "weighting_assumption": weighted.weighting_assumption,
            "correlation_scope": weighted.correlation_scope,
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
            "use multiple deterministic ordered realizations rather than one arbitrary ordered proxy",
            "derive exact rational weights only from retained source marginal occupancies",
            "preserve source-limited semantics by making no unresolved configurational-correlation claim",
        ),
    )
    return strategy, execution, entry
