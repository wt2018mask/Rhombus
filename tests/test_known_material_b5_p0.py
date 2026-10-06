"""Raw P0 execution semantics for B5 DEV structure units."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import rudeus.science.known_material_b5_p0 as b5_p0_module
from rudeus.schema import ExistenceState
from rudeus.science.known_material_b5_dev_units import B5DevStructureUnitPlan
from rudeus.science.known_material_b5_p0 import (
    B5P0UnitExecutionStatus,
    execute_b5_p0_unit,
    materialize_b5_p0_structure,
    require_clean_b5_p0_execution,
    run_b5_p0_raw_execution,
)
from scripts.benchmark.render_b5_dev_structure_units import (
    build_canonical_b5_dev_structure_units,
)


def _unit_plan():
    return build_canonical_b5_dev_structure_units()


def test_p0_materialization_reconstructs_retained_and_generated_units():
    plan = _unit_plan()
    direct = next(
        unit for unit in plan.units
        if unit.material_key == "lialo2-gamma"
    )
    generated = next(
        unit for unit in plan.units
        if unit.material_key == "llzo-cubic-al-stabilized"
    )

    direct_structure = materialize_b5_p0_structure(direct, repo_root=Path("."))
    generated_structure = materialize_b5_p0_structure(generated, repo_root=Path("."))

    assert len(direct_structure) > 0
    assert len(generated_structure) > 0
    assert direct_structure.composition.reduced_formula
    assert generated_structure.composition.reduced_formula


def test_generated_ensemble_materialization_is_reused(monkeypatch):
    plan = _unit_plan()
    generated = [
        unit for unit in plan.units
        if unit.material_key == "llzo-cubic-al-stabilized"
    ]
    assert len(generated) >= 2

    original = b5_p0_module.build_weighted_cubic_llzo_ordered_structures
    calls = []

    def counted(path):
        calls.append(path)
        return original(path)

    b5_p0_module._cached_weighted_generated_members.cache_clear()
    monkeypatch.setattr(
        b5_p0_module,
        "build_weighted_cubic_llzo_ordered_structures",
        counted,
    )
    materialize_b5_p0_structure(generated[0], repo_root=Path("."))
    materialize_b5_p0_structure(generated[1], repo_root=Path("."))
    assert len(calls) == 1
    b5_p0_module._cached_weighted_generated_members.cache_clear()


def test_p0_execution_error_never_becomes_scientific_verdict():
    plan = _unit_plan()
    phase = next(
        unit for unit in plan.units
        if unit.material_key == "libh4-phase-transition-pair"
    )
    tampered = replace(phase, unit_structure_hash="0" * 64)

    observation = execute_b5_p0_unit(tampered, repo_root=Path("."))

    assert observation.execution_status == B5P0UnitExecutionStatus.ERROR.value
    assert observation.existence_state is None
    assert observation.passed is None
    assert observation.neutrality_ok is None
    assert observation.pauling_ok is None
    assert observation.geometry_ok is None
    assert observation.error_type == "ValueError"


def test_raw_p0_report_does_not_aggregate_material_verdicts(monkeypatch):
    plan = _unit_plan()
    direct = next(
        unit for unit in plan.units
        if unit.material_key == "lialo2-gamma"
    )
    one_unit_plan = B5DevStructureUnitPlan(
        plan_version=plan.plan_version,
        dev_diagnostic_plan_hash=plan.dev_diagnostic_plan_hash,
        units=(direct,),
        diagnostic_only=True,
        qualification_evidence_authorized=False,
        held_out_execution_authorized=False,
        production_search_authorized=False,
    )

    def fake_evaluate_p0(formula, *, structure):
        return SimpleNamespace(
            existence_state=ExistenceState.PLAUSIBLE,
            passed=True,
            neutrality_ok=True,
            pauling_ok=True,
            geometry_ok=True,
            details={"test_only": True},
        )

    monkeypatch.setattr(
        "rudeus.science.known_material_b5_p0.evaluate_p0",
        fake_evaluate_p0,
    )
    report = run_b5_p0_raw_execution(one_unit_plan, repo_root=Path("."))

    assert report.completed_count == 1
    assert report.error_count == 0
    assert report.material_verdicts_aggregated is False
    assert report.diagnostic_only is True
    assert report.qualification_evidence_authorized is False
    assert report.held_out_execution_authorized is False
    assert report.production_search_authorized is False
    require_clean_b5_p0_execution(report)


def test_clean_execution_gate_fails_only_on_operational_error():
    plan = _unit_plan()
    phase = next(
        unit for unit in plan.units
        if unit.material_key == "libh4-phase-transition-pair"
    )
    tampered = replace(phase, unit_structure_hash="0" * 64)
    one_unit_plan = B5DevStructureUnitPlan(
        plan_version=plan.plan_version,
        dev_diagnostic_plan_hash=plan.dev_diagnostic_plan_hash,
        units=(tampered,),
        diagnostic_only=True,
        qualification_evidence_authorized=False,
        held_out_execution_authorized=False,
        production_search_authorized=False,
    )
    report = run_b5_p0_raw_execution(one_unit_plan, repo_root=Path("."))

    assert report.error_count == 1
    with pytest.raises(RuntimeError, match="execution errors"):
        require_clean_b5_p0_execution(report)
