import hashlib
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_formal_amendment_proposal import (
    GENERATION_METHOD,
    build_cubic_llzo_formal_amendment_proposal,
)

CIF = Path("data/benchmarks/known_material/structures/cod/7215448-r176453.cif")

def test_formal_amendment_proposal_is_complete_and_non_mutating():
    source_hash = hashlib.sha256(CIF.read_bytes()).hexdigest()
    candidate, strategy, execution, entry = build_cubic_llzo_formal_amendment_proposal(
        CIF, source_artifact_hash=source_hash
    )
    assert candidate.all_geometry_ok is True
    assert strategy.generation_method == GENERATION_METHOD
    assert strategy.realization_hashes == tuple(
        item.structure_hash for item in execution.components
    )
    assert entry.payload["execution_structure_hash"] == execution.visible_structure_hash
    assert entry.payload["constraint_scope"]
    assert entry.provenance_hash == candidate.content_hash
