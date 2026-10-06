from types import SimpleNamespace

from rudeus.science.known_material_b5_p1_execution_plan import (
    B5_P1_EXECUTION_PLAN_VERSION,
    build_b5_p1_execution_plan,
)
from rudeus.science.known_material_b5_p1_entry import (
    B5P1EntryDecision,
    B5_P1_ENTRY_GATE_VERSION,
    P1EntryDisposition,
)


def decision(key, disposition):
    return B5P1EntryDecision(
        gate_version=B5_P1_ENTRY_GATE_VERSION,
        material_key=key,
        p0_material_assessment_hash="1" * 64,
        p0_disposition="PLAUSIBLE" if disposition == "ELIGIBLE" else "INDETERMINATE",
        p1_entry_disposition=disposition,
        p1_execution_authorized=disposition == "ELIGIBLE",
        reason="test",
    )


def test_execution_plan_includes_only_eligible_material_units():
    units = (
        SimpleNamespace(
            material_key="a", component_label="direct", representation_mode="DIRECT",
            content_hash="2" * 64, unit_structure_hash="3" * 64,
            source_path="data/benchmarks/known_material/structures/a.cif",
        ),
        SimpleNamespace(
            material_key="b", component_label="member-00", representation_mode="ENSEMBLE",
            content_hash="4" * 64, unit_structure_hash="5" * 64,
            source_path="data/benchmarks/known_material/structures/b.cif",
        ),
    )
    structure_plan = SimpleNamespace(content_hash="6" * 64, units=units)
    config = {
        "primary_checkpoint": "medium-mpa-0",
        "checkpoint_url": "https://example.invalid/model",
        "checkpoint_sha256": "7" * 64,
        "force_tol_ev_A": 0.01,
        "max_relax_steps": 200,
        "precision": "float64",
    }
    plan = build_b5_p1_execution_plan(
        structure_plan,
        (
            decision("a", P1EntryDisposition.ELIGIBLE.value),
            decision("b", P1EntryDisposition.HELD_P0_INDETERMINATE.value),
        ),
        mlip_config=config,
    )
    assert plan.plan_version == B5_P1_EXECUTION_PLAN_VERSION
    assert len(plan.units) == 1
    assert plan.units[0].material_key == "a"
    assert plan.units[0].checkpoint_id == "medium-mpa-0"
    assert plan.planning_only is True
    assert plan.p1_tasks_created is False
