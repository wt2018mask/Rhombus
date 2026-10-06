import hashlib
from fractions import Fraction
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_policy_evidence import (
    PRE_AMENDMENT_EXECUTION_HASH,
)
from rudeus.science.known_material_cubic_llzo_representation_amendment import (
    build_cubic_llzo_representation_amendment_candidate,
)

CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")

def test_amendment_candidate_is_geometry_clean_weight_exact_and_non_mutating():
    source_hash = hashlib.sha256(CIF.read_bytes()).hexdigest()
    candidate = build_cubic_llzo_representation_amendment_candidate(
        CIF,
        source_artifact_hash=source_hash,
        old_binding_hash=PRE_AMENDMENT_EXECUTION_HASH,
    )

    assert candidate.all_geometry_ok is True
    assert candidate.canonical_evidence_mutated is False
    assert len(candidate.candidate_binding.components) == 8
    assert sum(
        Fraction(item.weight_numerator, item.weight_denominator)
        for item in candidate.candidate_binding.components
    ) == 1
    assert candidate.candidate_binding.visible_structure_hash != PRE_AMENDMENT_EXECUTION_HASH
