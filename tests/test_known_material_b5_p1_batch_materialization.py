from rudeus.science.known_material_b5_p1_batch_materialization import (
    materialize_b5_p1_pending_batches,
)
from rudeus.science.known_material_b5_p1_execution_plan import (
    B5P1ExecutionPlan,
    B5P1ExecutionUnit,
    B5_P1_EXECUTION_PLAN_VERSION,
)


def unit(label="direct"):
    return B5P1ExecutionUnit(
        unit_version=B5_P1_EXECUTION_PLAN_VERSION,
        material_key="m",
        component_label=label,
        representation_mode="DIRECT",
        source_b5_structure_unit_hash="1" * 64,
        input_structure_hash="2" * 64,
        source_path="data/benchmarks/known_material/structures/m.cif",
        checkpoint_id="medium-mpa-0",
        checkpoint_sha256="3" * 64,
        checkpoint_url="https://example.invalid/model",
        force_tol_ev_A=0.01,
        max_relax_steps=200,
        precision="float64",
    )


def test_pending_batch_identity_is_deterministic_and_structure_bound():
    item = unit()
    plan = B5P1ExecutionPlan(
        plan_version=B5_P1_EXECUTION_PLAN_VERSION,
        source_structure_unit_plan_hash="4" * 64,
        source_entry_decision_hashes=("5" * 64,),
        units=(item,),
        planning_only=True,
        p1_tasks_created=False,
    )
    structure = {
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "charge": 0,
        "lattice": {"matrix": [[1,0,0],[0,1,0],[0,0,1]], "pbc": [True,True,True], "a":1,"b":1,"c":1,"alpha":90,"beta":90,"gamma":90,"volume":1},
        "properties": {},
        "sites": [],
    }
    first = materialize_b5_p1_pending_batches(
        plan, structures_by_execution_unit_hash={item.content_hash: structure}
    )
    second = materialize_b5_p1_pending_batches(
        plan, structures_by_execution_unit_hash={item.content_hash: structure}
    )
    assert first == second
    assert len(first) == 1
    assert first[0].generation_config_hash == plan.content_hash
    assert first[0].p0_state == "PLAUSIBLE"
    assert first[0].mlip_protocol["checkpoint_id"] == "medium-mpa-0"
