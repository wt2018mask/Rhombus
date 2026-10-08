"""Conservative, opt-in, no-compute AI structure/model-domain preflights."""
import hashlib
import json
import math
from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from rhombus.domain import structure_candidate_fingerprint_sha256
from rhombus.tools.preflight import ReadOnlyPreflightTools


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/benchmarks/known_material/model_domains/medium-mpa-0-domain-v1.json"
INDEX = ROOT / "data/benchmarks/known_material/model_domain_snapshot_index_v1.json"


def gateway(snapshot=SNAPSHOT, sha=None):
    expected = json.loads(INDEX.read_text())["entries"][0]["snapshot_file_sha256"]
    assert hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest() == expected
    return ReadOnlyPreflightTools(
        model_domain_snapshot=snapshot, model_domain_snapshot_sha256=sha or expected
    )


def structure_args():
    return {
        "candidate_id": "candidate-1",
        "atomic_numbers": [11, 17],
        "cell_lengths_angstrom": [4.0, 4.0, 4.0],
        "cell_angles_degrees": [90.0, 90.0, 90.0],
        "fractional_coordinates": [[0, 0, 0], [0.5, 0.5, 0.5]],
    }


def domain_args(numbers=None):
    return {
        "candidate_id": "candidate-1",
        "atomic_numbers": [3, 8] if numbers is None else numbers,
        "claim_kind": "finite_temperature_stability",
    }


def test_element_supported_does_not_authorize_in_domain():
    result = gateway().call_tool("get_domain_assessment", domain_args())
    assert result["model_id"] == "medium-mpa-0"
    assert result["domain_status"] == "UNQUALIFIED"
    assert result["unsupported_atomic_numbers"] == []
    assert result["scientific_verdict"] == "UNKNOWN"
    assert result["claim_authorized"] is False
    assert result["input_binding"] == "MODEL_SUPPLIED_NOT_SOURCE_VERIFIED"
    assert result["evidence_ids"] == []
    assert result["assessment_level"] == "ELEMENT_COVERAGE_PREFLIGHT"


def test_unsupported_atomic_number_far_ood_but_not_candidate_verdict():
    result = gateway().call_tool("get_domain_assessment", domain_args([3, 84]))
    assert result["unsupported_atomic_numbers"] == [84]
    assert result["domain_status"] == "FAR_OOD"
    assert result["scientific_verdict"] == "UNKNOWN"
    assert result["claim_authorized"] is False


def test_structure_preflight_reuses_frozen_coarse_fingerprint():
    args = structure_args()
    result = gateway().call_tool("validate_candidate_structure", args)
    known = Structure(Lattice.cubic(4.0), [11, 17], [[0, 0, 0], [0.5, 0.5, 0.5]])
    assert result["candidate_fingerprint_sha256"] == structure_candidate_fingerprint_sha256(known)
    assert result["site_count"] == 2
    assert result["representation_status"] == "WELL_FORMED_PERIODIC_STRUCTURE"
    assert result["scientific_verdict"] == "UNKNOWN"
    assert result["domain_status"] == "UNQUALIFIED"
    assert result["claim_authorized"] is False
    assert "COARSE_FINGERPRINT_NOT_EXACT_STRUCTURE_MEMBERSHIP" in result["limitations"]


@pytest.mark.parametrize("damage", [
    "atom_count", "bool_number", "negative_atomic_number", "nan_angle",
    "degenerate_cell", "colliding_sites", "extra_path", "huge_position",
])
def test_malformed_or_untrusted_structures_fail_closed(damage):
    args = structure_args()
    if damage == "atom_count":
        args["fractional_coordinates"].pop()
    elif damage == "bool_number":
        args["atomic_numbers"][0] = True
    elif damage == "negative_atomic_number":
        args["atomic_numbers"][0] = -1
    elif damage == "nan_angle":
        args["cell_angles_degrees"][1] = math.nan
    elif damage == "degenerate_cell":
        args["cell_angles_degrees"] = [90, 90, 179.99999999]
    elif damage == "colliding_sites":
        args["fractional_coordinates"][1] = [0, 0, 0]
    elif damage == "extra_path":
        args["evidence_jsonl"] = "/etc/passwd"
    elif damage == "huge_position":
        args["fractional_coordinates"][1][0] = 1e10
    with pytest.raises((ValueError, TypeError)):
        gateway().call_tool("validate_candidate_structure", args)


def test_frozen_snapshot_bytes_must_match_host_pin(tmp_path):
    target = tmp_path / "model.json"
    original = SNAPSHOT.read_bytes()
    target.write_bytes(original.replace(b"medium-mpa-0", b"other-model", 1))
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        gateway(target).call_tool("get_domain_assessment", domain_args())
    with pytest.raises(ValueError, match="missing or oversized"):
        gateway(tmp_path / "missing.json").call_tool("get_domain_assessment", domain_args())
    with pytest.raises(ValueError):
        ReadOnlyPreflightTools(model_domain_snapshot=target, model_domain_snapshot_sha256="not-a-sha")


def test_domain_args_reject_new_paths_and_fake_candidate_ids():
    for change in (
        {"source_path": "s3://some-private-file"},
        {"candidate_id": "  "},
        {"atomic_numbers": [True]},
        {"atomic_numbers": [119]},
        {"claim_kind": ""},
        {"atomic_numbers": [8] * 257},
    ):
        args = domain_args()
        args.update(change)
        with pytest.raises((ValueError, TypeError)):
            gateway().call_tool("get_domain_assessment", args)
    with pytest.raises(ValueError, match="not registered"):
        gateway().call_tool("run_kaggle", domain_args())
