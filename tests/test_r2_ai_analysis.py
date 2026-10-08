"""Bounds, pinned provenance, and fail-closed structure/domain AI preflights."""
import json
from pathlib import Path

import pytest

from rhombus.tools.read_only_analysis import (
    DOMAIN_SHA256, ReadOnlyAnalysisTools, list_analysis_tool_specs,
)

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "data/benchmarks/known_material/model_domains/medium-mpa-0-domain-v1.json"


def request(model_id="medium-mpa-0", atoms=None):
    return {
        "candidate_id": "candidate-a",
        "model_id": model_id,
        "claim_kind": "finite_temperature_stability",
        "atomic_numbers": atoms if atoms is not None else [3, 8, 8],
    }


def structure():
    return {
        "lattice_vectors_angstrom": [[4.0, 0, 0], [0, 4.0, 0], [0, 0, 4.0]],
        "atomic_numbers": [3, 8],
        "fractional_coords": [[0, 0, 0], [0.5, 0.5, 0.5]],
    }


def test_analysis_catalog_has_strict_schemas_and_no_paths():
    specs = list_analysis_tool_specs()
    assert [x["function"]["name"] for x in specs] == [
        "get_domain_assessment", "validate_candidate_structure"
    ]
    for spec in specs:
        params = spec["function"]["parameters"]
        assert params["additionalProperties"] is False
        assert "evidence_jsonl" not in params["properties"]
        assert "model_domain_snapshot" not in params["properties"]
        assert "kaggle_token" not in params["properties"]
    assert specs[1]["function"]["parameters"]["properties"]["structure"]["additionalProperties"] is False
    specs[0]["function"]["name"] = "tampered"
    assert list_analysis_tool_specs()[0]["function"]["name"] == "get_domain_assessment"


def test_domain_snapshot_is_exactly_pinned_and_not_in_domain():
    import hashlib
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == DOMAIN_SHA256
    gateway = ReadOnlyAnalysisTools(FROZEN)
    before = FROZEN.read_bytes()
    answer = gateway.call_tool("get_domain_assessment", request())
    assert answer["operational_status"] == "SUCCEEDED"
    assert answer["scientific_verdict"] == "UNKNOWN"
    assert answer["claim_authorized"] is False
    assert answer["domain_status"] == "UNQUALIFIED"
    assert answer["model_checkpoint_sha256"].startswith("75428a")
    assert answer["unsupported_atomic_numbers"] == []
    assert "NOT_TRAINING_EXPOSURE_AUDIT" in answer["limitations"]
    assert FROZEN.read_bytes() == before


def test_unsupported_element_is_far_ood_not_scientific_pass():
    gateway = ReadOnlyAnalysisTools(FROZEN)
    answer = gateway.call_tool("get_domain_assessment", request(atoms=[3, 84]))
    assert answer["domain_status"] == "FAR_OOD"
    assert answer["unsupported_atomic_numbers"] == [84]
    assert answer["scientific_verdict"] == "UNKNOWN"
    assert answer["claim_authorized"] is False


def test_missing_or_changed_host_snapshot_fails_closed(tmp_path):
    args = request()
    with pytest.raises(ValueError, match="not configured"):
        ReadOnlyAnalysisTools().call_tool("get_domain_assessment", args)
    corrupt = tmp_path / "untrusted.json"
    corrupt.write_text(FROZEN.read_text(encoding="utf-8").replace(
        '"model_id": "medium-mpa-0"', '"model_id": "forged"'
    ), encoding="utf-8")
    with pytest.raises(ValueError, match="identity mismatch"):
        ReadOnlyAnalysisTools(corrupt).call_tool("get_domain_assessment", args)


@pytest.mark.parametrize("args", [
    request(model_id="untrusted-model"),
    request(atoms=[True, 8]),
    request(atoms=[]),
    {**request(), "path": "/etc/passwd"},
    {**request(), "claim_kind": "unseen_generalization"},
    {**request(), "candidate_id": "  "},
])
def test_domain_rejects_invalid_authority_or_args(args):
    with pytest.raises(ValueError):
        ReadOnlyAnalysisTools(FROZEN).call_tool("get_domain_assessment", args)


def test_structure_valid_representation_is_not_a_scientific_pass():
    gateway = ReadOnlyAnalysisTools()
    args = {"candidate_id": "candidate-a", "structure": structure()}
    result = gateway.call_tool("validate_candidate_structure", args)
    assert result["representation_status"] == "VALID_REPRESENTATION"
    assert result["scientific_verdict"] == "UNKNOWN"
    assert result["domain_status"] == "UNQUALIFIED"
    assert result["claim_authorized"] is False
    assert result["site_count"] == 2
    assert result["cell_volume_angstrom3"] == 64.0
    assert len(result["input_structure_sha256"]) == 64
    assert "NO_SCIENTIFIC_CLAIM_AUTHORIZATION" in result["limitations"]
    assert gateway.call_tool("validate_candidate_structure", args) == result


def test_structure_periodic_collision_is_not_misrepresented_as_pass():
    s = structure()
    s["fractional_coords"][1] = [1, 0, 0]
    result = ReadOnlyAnalysisTools().call_tool(
        "validate_candidate_structure", {"candidate_id": "x", "structure": s}
    )
    assert result["representation_status"] == "INVALID_COINCIDENT_PERIODIC_SITES"
    assert result["scientific_verdict"] == "UNKNOWN"
    assert result["claim_authorized"] is False


@pytest.mark.parametrize("mutator", [
    lambda s: s.update(lattice_vectors_angstrom=[[1, 0, 0], [2, 0, 0], [0, 0, 1]]),
    lambda s: s.update(atomic_numbers=[3, True]),
    lambda s: s.update(fractional_coords=[[0, 0, 0]]),
    lambda s: s.update(fractional_coords=[[float("nan"), 0, 0], [0, 0, 0]]),
    lambda s: s.update(fractional_coords=[[0, 0, 0], [0, 0, "bad"]]),
    lambda s: s.update(atomic_numbers=[3] * 129, fractional_coords=[[0, 0, 0]] * 129),
    lambda s: s.update(file_path="../../kaggle.json"),
])
def test_structure_bad_inputs_fail_closed(mutator):
    s = structure()
    mutator(s)
    with pytest.raises(ValueError):
        ReadOnlyAnalysisTools().call_tool(
            "validate_candidate_structure", {"candidate_id": "x", "structure": s}
        )


def test_structure_rejects_model_injected_execution_request():
    for extra in ("command", "secrets", "kaggle_kernel", "model_domain_snapshot"):
        with pytest.raises(ValueError):
            ReadOnlyAnalysisTools(FROZEN).call_tool(
                "validate_candidate_structure",
                {"candidate_id": "x", "structure": structure(), extra: "anything"},
            )


def test_no_simulation_or_shell_tool_is_registered():
    gateway = ReadOnlyAnalysisTools(FROZEN)
    for name in ("relax_structure", "run_command", "kaggle_submit", "resolve_claims"):
        with pytest.raises(ValueError):
            gateway.call_tool(name, {"candidate_id": "x"})
