"""Frozen-source adapter and authorization tests, with no model inference."""
from pathlib import Path
import hashlib
import json
import shutil

import pytest

from scripts.science import digital_pilot_0200 as pilot


def test_oxidation_annotated_cif_uses_element_formula_without_changing_structure():
    protocol = pilot.load_protocol()
    _, structure = pilot.load_candidate(protocol["candidates"][0])
    before = structure.as_dict()
    assert pilot.canonical_formula(structure) == "LiAlO2"
    assert "+" in str(structure.composition)
    assert structure.as_dict() == before
    from rudeus.filters.p0 import evaluate_p0
    p0 = evaluate_p0(pilot.canonical_formula(structure), structure)
    assert p0.passed and p0.neutrality_ok and p0.geometry_ok


def test_frozen_second_family_source_keeps_exact_identity():
    p = pilot.load_protocol()
    spec = p["candidates"][1]
    receipt, structure = pilot.load_candidate(spec)
    assert spec["family_id"] == "S_ONLY"
    assert pilot.canonical_formula(structure) == "Li2S" and len(structure) == 12
    assert receipt["artifact_sha256"] == spec["cif_sha256"]


def test_proposal_or_missing_authorization_never_starts_model(tmp_path):
    with pytest.raises(PermissionError):
        pilot.run(tmp_path / "no-model", tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_wrong_weights_rejected_before_loading_mace(tmp_path):
    model = tmp_path / "fake.model"; model.write_bytes(b"not-a-model")
    with pytest.raises(ValueError, match="weights digest"):
        pilot.run(model, tmp_path / "out", authorized=True)
    assert not (tmp_path / "out").exists()


def test_existing_observation_is_preserved(tmp_path):
    output = tmp_path / "out"; output.mkdir();(output / "report.json").write_text("preserve")
    with pytest.raises(FileExistsError):
        pilot.run(tmp_path / "absent-model", output, authorized=True)
    assert (output / "report.json").read_text() == "preserve"


def test_source_receipt_tampering_fails_before_geometry_parse(tmp_path, monkeypatch):
    spec = dict(pilot.load_protocol()["candidates"][0])
    receipt = tmp_path / spec["receipt"];receipt.parent.mkdir(parents=True)
    receipt.write_text("{}")
    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="receipt changed"):pilot.load_candidate(spec)


def test_frozen_protocol_drift_is_not_accepted(tmp_path, monkeypatch):
    path = tmp_path / pilot.PROTOCOL_PATH;path.parent.mkdir(parents=True);path.write_text("{}")
    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="protocol changed"):pilot.load_protocol()


def retained():
    s = json.loads((pilot.ROOT / "data/development/0200.json").read_text())
    return s, pilot.ROOT / s["retained_final_directory"]


def test_real_retained_calculation_has_two_sources_eight_bound_trajectories():
    from rhombus.qualification.pilot_artifacts import verify_pilot_artifacts
    s, path = retained()
    result = verify_pilot_artifacts(path, expected_report_sha256=s["final_report_sha256"])
    assert result == dict(file_count=20, trajectory_count=8, evidence_count=2, qualified_survivors=[])
    report = json.loads((path / "report.json").read_text())
    assert report["protocol_sha256"] == pilot.PROTOCOL_SHA256
    assert len(report["candidates"]) == 2
    for c in report["candidates"]:
        assert c["status"] == "SUCCEEDED" and not c["errors"]
        assert c["P0"]["passed"] and c["P1"]["converged"]
        assert c["repeat_max_position_difference_A"] <= 1e-8
        assert len(c["runs"]) == 4
        assert c["digital_qualification"]["claim_vector"]["verdict"] == "UNKNOWN"
    for relative, expected in report["code_sha256"].items():
        # 0201 adds opt-in thermal instrumentation. Verify the exact executed
        # historical P2 source snapshot rather than claiming today's code ran.
        source = (pilot.ROOT / "data/development/digital0201/legacy_p2_0200.source.txt"
                  if relative == "rudeus/mlip/p2.py" else pilot.ROOT / relative)
        assert pilot.sha(source) == expected


def test_initial_adapter_failure_and_valid_measurements_are_preserved():
    s, _ = retained()
    first = pilot.ROOT / s["attempts"][0]["directory"]
    assert pilot.sha(first / "report.json") == s["attempts"][0]["report_sha256"]
    r = json.loads((first / "report.json").read_text())
    assert pilot.sha(first / "runner.source.txt") == r["code_sha256"]["scripts/science/digital_pilot_0200.py"]
    assert r["candidates"][0]["status"] == "ERROR"
    assert r["candidates"][0]["P0"]["existence_state"] == "UNKNOWN"
    assert r["candidates"][1]["status"] == "SUCCEEDED"
    for name, expected in r["artifact_files_sha256"].items():
        assert pilot.sha(first / name) == expected


@pytest.fixture
def archive_copy(tmp_path):
    s, source = retained()
    target = tmp_path / "copy"
    shutil.copytree(source, target)
    return s, target


def test_modified_trajectory_bytes_cannot_be_replayed(archive_copy):
    from rhombus.qualification.pilot_artifacts import verify_pilot_artifacts
    s, path = archive_copy
    artifact = next(path.rglob("*.npz"));artifact.write_bytes(artifact.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="byte digest"):
        verify_pilot_artifacts(path, expected_report_sha256=s["final_report_sha256"])


def test_report_and_mcp_snapshot_must_agree(archive_copy):
    from rhombus.qualification.pilot_artifacts import verify_pilot_artifacts
    s, path = archive_copy
    (path / "evidence.jsonl").write_text("")
    with pytest.raises(ValueError, match="snapshot"):
        verify_pilot_artifacts(path, expected_report_sha256=s["final_report_sha256"])


@pytest.mark.parametrize("field,value", [("qualified_survivors", ["false-positive"]),
                                         ("production_enabled", True), ("TEST121_accessed", True)])
def test_even_rehashed_receipt_cannot_promote_pilot_to_qualification(archive_copy, field, value):
    from rhombus.qualification.pilot_artifacts import verify_pilot_artifacts
    _, path = archive_copy
    r = json.loads((path / "report.json").read_text());r[field] = value
    (path / "report.json").write_text(json.dumps(r))
    with pytest.raises(ValueError, match="cannot confer"):
        verify_pilot_artifacts(path, expected_report_sha256=pilot.sha(path / "report.json"))


def test_rehashed_report_cannot_relabel_retained_candidate(archive_copy):
    from rhombus.qualification.pilot_artifacts import verify_pilot_artifacts
    _, path = archive_copy
    r = json.loads((path / "report.json").read_text())
    r["candidates"][0]["digital_qualification"]["qualified_survivor"] = True
    (path / "report.json").write_text(json.dumps(r))
    with pytest.raises(ValueError, match="candidate disagree"):
        verify_pilot_artifacts(path, expected_report_sha256=pilot.sha(path / "report.json"))
