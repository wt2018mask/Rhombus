"""Representation-aware B5 DEV structure-unit tests."""
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_b3_split import load_b3_split_freeze
from rudeus.science.known_material_b5_dev_units import (
    DETERMINISTIC_GENERATOR,
    RETAINED_ARTIFACT,
    build_b5_dev_structure_unit_plan,
)
from scripts.benchmark.render_b5_dev_diagnostic_plan import (
    build_canonical_b5_dev_plan,
)
from scripts.benchmark.render_b5_dev_structure_units import (
    build_canonical_b5_dev_structure_units,
)


ROOT = Path("data/benchmarks/known_material")


def test_canonical_b5_dev_structure_units_expand_1_2_8():
    plan = build_canonical_b5_dev_structure_units()
    by_material = {}
    for unit in plan.units:
        by_material.setdefault(unit.material_key, []).append(unit)

    assert len(plan.units) == 11
    assert {key: len(value) for key, value in by_material.items()} == {
        "lialo2-gamma": 1,
        "libh4-phase-transition-pair": 2,
        "llzo-cubic-al-stabilized": 8,
    }

    direct = by_material["lialo2-gamma"]
    phase_set = by_material["libh4-phase-transition-pair"]
    ensemble = by_material["llzo-cubic-al-stabilized"]

    assert {unit.representation_mode for unit in direct} == {"DIRECT"}
    assert {unit.representation_mode for unit in phase_set} == {"PHASE_SET"}
    assert {unit.representation_mode for unit in ensemble} == {"ENSEMBLE"}

    assert all(unit.materialization_kind == RETAINED_ARTIFACT for unit in direct)
    assert all(unit.materialization_kind == RETAINED_ARTIFACT for unit in phase_set)
    assert all(unit.materialization_kind == DETERMINISTIC_GENERATOR for unit in ensemble)


def test_b5_dev_ensemble_units_preserve_exact_weights_and_generator_provenance():
    plan = build_canonical_b5_dev_structure_units()
    ensemble = [
        unit
        for unit in plan.units
        if unit.material_key == "llzo-cubic-al-stabilized"
    ]

    assert [unit.component_label for unit in ensemble] == [
        f"member-{index:02d}" for index in range(8)
    ]
    assert sum(
        Fraction(unit.weight_numerator, unit.weight_denominator)
        for unit in ensemble
    ) == 1
    assert len({unit.unit_structure_hash for unit in ensemble}) == 8
    assert len({unit.source_artifact_key for unit in ensemble}) == 1
    assert len({unit.source_path for unit in ensemble}) == 1
    assert len({unit.generator_id for unit in ensemble}) == 1
    assert all(unit.generator_id for unit in ensemble)


def test_b5_dev_phase_units_keep_retained_condition_scope():
    plan = build_canonical_b5_dev_structure_units()
    phases = {
        unit.component_label: unit
        for unit in plan.units
        if unit.material_key == "libh4-phase-transition-pair"
    }

    assert set(phases) == {"hexagonal", "orthorhombic"}
    assert "high-temperature" in phases["hexagonal"].condition_scope["temperature_scope"]
    assert "below structural transition" in phases["orthorhombic"].condition_scope[
        "temperature_scope"
    ]


def test_b5_dev_structure_units_are_reproducible_and_source_bound():
    first = build_canonical_b5_dev_structure_units()
    second = build_canonical_b5_dev_structure_units()

    assert first == second
    assert first.dev_diagnostic_plan_hash == build_canonical_b5_dev_plan().content_hash
    for unit in first.units:
        assert (Path(".") / unit.source_path).is_file()
        assert len(unit.unit_structure_hash) == 64
        assert len(unit.material_structure_hash) == 64


def test_b5_dev_structure_units_contain_no_held_out_identity():
    plan = build_canonical_b5_dev_structure_units()
    freeze = load_b3_split_freeze(ROOT / "b3_split_freeze_v1.json")
    held_out = {
        member.benchmark_id
        for member in freeze.members
        if member.split == "HELD_OUT"
    }

    serialized = json.dumps(plan.to_dict(), sort_keys=True)
    assert all(material_key not in serialized for material_key in held_out)
    assert plan.diagnostic_only is True
    assert plan.qualification_evidence_authorized is False
    assert plan.held_out_execution_authorized is False
    assert plan.production_search_authorized is False


def test_b5_dev_structure_expansion_rejects_composite_hash_drift():
    from rudeus.science.known_material_artifact_curation import (
        load_registry,
        load_retention_index,
    )
    from rudeus.science.known_material_representation_policy import (
        load_representation_evidence_ledger,
        load_representation_policy_registry,
    )
    from rudeus.science.known_material_structure_resolution import (
        load_structure_resolution_manifest,
        resolve_structure_manifest,
    )

    dev_plan = build_canonical_b5_dev_plan()
    members = list(dev_plan.members)
    members[0] = replace(members[0], structure_hash="0" * 64)
    tampered = replace(dev_plan, members=tuple(members))

    registry = load_registry(ROOT / "artifact_registry_v1.json")
    retention = load_retention_index(ROOT / "artifact_retention_index_v1.json")
    ledger = resolve_structure_manifest(
        load_structure_resolution_manifest(
            ROOT / "structure_resolution_manifest_v1.json"
        ),
        registry,
        retention,
        policy_registry=load_representation_policy_registry(
            ROOT / "representation_policy_registry_v1.json"
        ),
        policy_evidence_ledger=load_representation_evidence_ledger(
            ROOT / "representation_evidence_ledger_v1.json"
        ),
    )

    with pytest.raises(ValueError, match="differs from canonical resolution"):
        build_b5_dev_structure_unit_plan(
            tampered,
            repo_root=Path("."),
            structure_ledger=ledger,
            artifact_registry=registry,
            retention_index=retention,
        )
