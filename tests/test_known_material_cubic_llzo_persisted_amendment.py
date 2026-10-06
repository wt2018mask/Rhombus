import hashlib
import json
from pathlib import Path

from rudeus.science.known_material_cubic_llzo_policy_evidence import (
    GENERATION_METHOD,
    build_cubic_llzo_fractional_occupancy_policy_evidence,
)
from scripts.benchmark.render_b5_dev_structure_units import (
    build_canonical_b5_dev_structure_units,
)


ROOT = Path("data/benchmarks/known_material")
CIF = ROOT / "structures/cod/7215448-r176453.cif"
EXPECTED_EXECUTION_HASH = (
    "ab7b207f312975143f961fd2327ed2a99421de78fd652c1cc04fac7c863375c7"
)
EXPECTED_STRATEGY_HASH = (
    "9ee0dff4199e913ceec7f4b461ef0a85a504400fa57a40bbbd1bac0f2e5be307"
)
EXPECTED_EVIDENCE_HASH = (
    "380ad0b969f8155d09964b52fe4a546d588c873046abf2bc596297b41a0e27bd"
)


def test_persisted_llzo_amendment_matches_builder_manifest_and_b5_units():
    source_hash = hashlib.sha256(CIF.read_bytes()).hexdigest()
    strategy, execution, entry = build_cubic_llzo_fractional_occupancy_policy_evidence(
        CIF, source_artifact_hash=source_hash
    )

    assert strategy.generation_method == GENERATION_METHOD
    assert strategy.content_hash == EXPECTED_STRATEGY_HASH
    assert execution.visible_structure_hash == EXPECTED_EXECUTION_HASH
    assert entry.content_hash == EXPECTED_EVIDENCE_HASH

    ledger = json.loads((ROOT / "representation_evidence_ledger_v1.json").read_text())
    assert ledger["entries"] == [entry.to_dict()]

    manifest = json.loads((ROOT / "structure_resolution_manifest_v1.json").read_text())
    llzo = next(
        item for item in manifest["specs"]
        if item["material_key"] == "llzo-cubic-al-stabilized"
    )
    ensemble = llzo["reference_conditions"]["ensemble_execution"]
    assert ensemble["execution_structure_hash"] == EXPECTED_EXECUTION_HASH
    assert ensemble["constraint_scope"] == entry.payload["constraint_scope"]

    units = build_canonical_b5_dev_structure_units()
    llzo_units = [
        item for item in units.units
        if item.material_key == "llzo-cubic-al-stabilized"
    ]
    assert len(llzo_units) == 8
    assert {item.generator_id for item in llzo_units} == {GENERATION_METHOD}
    assert tuple(item.unit_structure_hash for item in llzo_units) == tuple(
        item.structure_hash for item in execution.components
    )
