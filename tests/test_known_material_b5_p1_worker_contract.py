from rudeus.mlip.sharding import structure_dict_sha256
from rudeus.science.known_material_b5_p1_batch_materialization import (
    B5P1PendingBatch,
    B5_P1_BATCH_MATERIALIZATION_VERSION,
)
from rudeus.science.known_material_b5_p1_worker_contract import (
    validate_synthetic_worker_handoff,
)


def batch(index: int):
    structure = {
        "lattice": {"matrix": [[2 + index, 0, 0], [0, 2, 0], [0, 0, 2]]},
        "sites": [{"species": [{"element": "Li", "occu": 1}], "abc": [0, 0, 0]}],
    }
    sha = structure_dict_sha256(structure)
    batch_id = f"{index + 1:016x}"
    return B5P1PendingBatch(
        materialization_version=B5_P1_BATCH_MATERIALIZATION_VERSION,
        batch_id_scheme="v2-structure-sha256",
        batch_id=batch_id,
        child_index=index,
        seed=0,
        parent_id=f"p{index}",
        child_material_id=f"c{index}",
        generation_config_hash="1" * 64,
        checkpoint_id="medium-mpa-0",
        structure_sha256=sha,
        structure_dict=structure,
        material_key=f"m{index}",
        component_label="direct",
        representation_mode="DIRECT",
        source_execution_plan_hash="2" * 64,
        source_execution_unit_hash="3" * 64,
        source_b5_structure_unit_hash="4" * 64,
        input_structure_hash="5" * 64,
        source_path=f"data/benchmarks/known_material/structures/m{index}.cif",
        mlip_protocol={
            "checkpoint_id": "medium-mpa-0",
            "checkpoint_sha256": "6" * 64,
            "checkpoint_url": "https://example.invalid/model",
            "force_tol_ev_A": 0.01,
            "max_relax_steps": 200,
            "precision": "float64",
        },
        p0_state="PLAUSIBLE",
        split="DEV",
    )


def test_stateless_p1_worker_contract_preserves_identity_resume_and_error_isolation():
    result = validate_synthetic_worker_handoff(tuple(batch(i) for i in range(3)))
    assert result["batch_count"] == 3
    assert result["normal_processed"] == 3
    assert result["resume_skipped_done"] == 3
    assert result["isolated_error_count"] == 1
    assert result["isolated_success_count"] == 2
    assert result["scientific_verdict_authorized"] is False
