import copy

import pytest

from rudeus.science.contracts import digest
from rudeus.science.x_mattersim_scientific import (
    MatterSimXExecutionSpec,
    admit_mattersim_x,
)


def payloads():
    traj = digest("trajectory")
    p2 = {
        "batch_id": "batch",
        "result": {
            "candidate_material_id": "candidate",
            "p2_verdict": "PASS",
            "dynamic_state": "PASS",
            "temperature_K": 550.0,
            "p2_config_hash": "cfg",
            "p2_protocol_version": "p2-v1",
            "seed": 7,
            "trajectory_artifact": {
                "sha256": traj,
                "format_version": "p2-traj-v1",
            },
        },
    }
    p25 = {
        "batch_id": "batch",
        "result": {
            "candidate_material_id": "candidate",
            "batch_id": "batch",
            "p2_verdict": "PASS",
            "p2_dynamic_state": "PASS",
            "temperature_K": 550.0,
            "target_species": "Li",
            "transport_state": "DIFFUSIVE",
            "p25_verdict": "DIFFUSIVE",
            "provenance": {
                "trajectory_artifact_sha256": traj,
                "p2_config_hash": "cfg",
                "p2_protocol_version": "p2-v1",
                "p2_seed": 7,
                "artifact_format_version": "p2-traj-v1",
            },
        },
    }
    return p2, p25


def test_mattersim_x_admission_accepts_only_bound_diffusive_entrant():
    p2, p25 = payloads()
    spec = admit_mattersim_x(p2, p25, p3_protocol_hash=digest("p3-protocol"))

    assert spec.candidate_id == "candidate"
    assert spec.batch_id == "batch"
    assert spec.target_species == "Li"
    assert spec.temperature_K == 550.0
    assert spec.purpose == "independent_transport_crosscheck"
    assert len(spec.checkpoint_sha256) == 64
    assert MatterSimXExecutionSpec.from_dict(spec.to_dict()) == spec


@pytest.mark.parametrize(
    "field,value",
    [
        ("transport_state", "NONDIFFUSIVE"),
        ("transport_state", "INDETERMINATE"),
        ("p25_verdict", "NONDIFFUSIVE"),
    ],
)
def test_mattersim_x_admission_rejects_non_diffusive_or_indeterminate(field, value):
    p2, p25 = payloads()
    p25["result"][field] = value

    with pytest.raises(ValueError, match="requires P2.5 DIFFUSIVE"):
        admit_mattersim_x(p2, p25, p3_protocol_hash=digest("p3-protocol"))


def test_mattersim_x_admission_rejects_p2_failure():
    p2, p25 = payloads()
    p2["result"]["p2_verdict"] = "FAIL"

    with pytest.raises(ValueError, match="requires P2 PASS"):
        admit_mattersim_x(p2, p25, p3_protocol_hash=digest("p3-protocol"))


@pytest.mark.parametrize(
    "damage",
    [
        "candidate",
        "batch",
        "temperature",
        "trajectory",
        "p2_config",
        "p2_protocol",
        "p2_seed",
        "artifact_format",
    ],
)
def test_mattersim_x_admission_rejects_cross_document_rebinding(damage):
    p2, p25 = payloads()
    if damage == "candidate":
        p25["result"]["candidate_material_id"] = "other"
    elif damage == "batch":
        p25["result"]["batch_id"] = "other"
    elif damage == "temperature":
        p25["result"]["temperature_K"] = 600.0
    elif damage == "trajectory":
        p25["result"]["provenance"]["trajectory_artifact_sha256"] = digest("other")
    elif damage == "p2_config":
        p25["result"]["provenance"]["p2_config_hash"] = "other"
    elif damage == "p2_protocol":
        p25["result"]["provenance"]["p2_protocol_version"] = "other"
    elif damage == "p2_seed":
        p25["result"]["provenance"]["p2_seed"] = 999
    elif damage == "artifact_format":
        p25["result"]["provenance"]["artifact_format_version"] = "other"

    with pytest.raises(ValueError, match="provenance mismatch"):
        admit_mattersim_x(p2, p25, p3_protocol_hash=digest("p3-protocol"))


def test_mattersim_x_admission_does_not_mutate_upstream_payloads():
    p2, p25 = payloads()
    before = copy.deepcopy((p2, p25))

    admit_mattersim_x(p2, p25, p3_protocol_hash=digest("p3-protocol"))

    assert (p2, p25) == before
