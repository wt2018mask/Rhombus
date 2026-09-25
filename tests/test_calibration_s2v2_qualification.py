"""Fixture-only S2 v2 HELDOUT qualification tests."""
import json
import sys
from pathlib import Path
import pytest
from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s2v2 import (S2V2_CRITERION, S2V2_CRITERION_HASH,
    S2V2_HELDOUT_CONFIDENCE, exact_one_sided_lcb)
from rudeus.science.calibration_s2v2_populations import S2V2_HELDOUT_HASH, S2V2_HELDOUT_SEEDS
from rudeus.science.calibration_s2v2_qualification import *
from rudeus.science.contracts import canonical_bytes, digest

H = {k: chr(97+i)*64 for i,k in enumerate(("ack","open","package"))}
KW = dict(pre_heldout_acknowledgment_hash=H["ack"], heldout_open_marker_hash=H["open"], calibration_package_hash=H["package"], q_hat=1.0, execution_code_revision="fixture-revision")

def records(covered=379, error=0.0):
    return [{"format":"s2v2-heldout-evaluation-v2", "replicate_id":rid,
      "method_hash":__import__("rudeus.science.calibration_s2v2",fromlist=["S2V2_METHOD_HASH"]).S2V2_METHOD_HASH,
      "population_hash":S2V2_HELDOUT_HASH, "pre_heldout_acknowledgment_hash":H["ack"],
      "calibration_package_hash":H["package"], "q_hat":1.0, "code_revision":"fixture-revision",
      "covered": i<covered, "signed_error":error, "absolute_error":abs(error)} for i,rid in enumerate(sorted(S2V2_HELDOUT_SEEDS))]

def test_one_sided_lcb_is_not_devb_two_sided_90():
    assert exact_one_sided_lcb(350,379,0.95) == __import__("rudeus.science.statistics",fromlist=["binomial_interval"]).binomial_interval(350,379,0.90)[0]
    assert exact_one_sided_lcb(350,379,0.95) != __import__("rudeus.science.statistics",fromlist=["binomial_interval"]).binomial_interval(350,379,0.90)[1]
    record = build_qualification_record(evaluation_records=records(), **KW)
    assert S2V2_HELDOUT_CONFIDENCE == 0.95
    assert S2V2_CRITERION["coverage_rule"] == "exact-one-sided-CP-LCB"
    assert S2V2_CRITERION["one_sided_confidence"] == 0.95
    assert record["criterion_hash"] == S2V2_CRITERION_HASH
    assert "coverage_lcb_95" in record
    assert not any("upper" in key.lower() and "coverage" in key.lower()
                   for key in record)

@pytest.mark.parametrize("lcb,bias,expected", [(.85,5e-11,"QUALIFIED"),(.849999999,0,"NOT-QUALIFIED"),(.85,5.000000001e-11,"NOT-QUALIFIED")])
def test_exact_boundaries(lcb,bias,expected): assert classify_qualification(lcb,bias)[2] == expected

def test_combined_states():
    assert [classify_qualification(.85,x)[2] for x in (5e-11,5e-10)] == ["QUALIFIED","NOT-QUALIFIED"]
    assert classify_qualification(.84,5e-10)[2] == "NOT-QUALIFIED"

@pytest.mark.parametrize("change", [{"coverage":.1},{"coverage_lcb_95":.1},{"mean_signed_error":1},{"abs_mean_signed_error":1},{"mean_absolute_error":1},{"n_covered":1},{"n_missed":1},{"criterion_hash":"f"*64},{"heldout_population_hash":"f"*64},{"pre_heldout_acknowledgment_hash":"f"*64},{"heldout_open_marker_hash":"f"*64},{"q_hat":2},{"heldout_execution_code_revision":"other"},{"coverage_criterion_result":"FAIL"},{"bias_criterion_result":"FAIL"},{"final_qualification_state":"NOT-QUALIFIED"}])
def test_rehashed_mutation_refused(tmp_path,change):
    rs=records(); record=build_qualification_record(evaluation_records=rs,**KW); persist_qualification_record(artifact_root=tmp_path,record=record)
    mutated=dict(record,**change); d=tmp_path/QUALIFICATION_DIR/f"{digest(mutated)}.json"; old=next((tmp_path/QUALIFICATION_DIR).glob("*.json")); old.unlink(); d.write_bytes(canonical_bytes(mutated))
    with pytest.raises(ExecutionError): verify_qualification_record(artifact_root=tmp_path,evaluation_records=rs,**KW)

def test_missing_duplicate_foreign_hold():
    for rs in (records()[:-1], records()+[records()[0]], records()[:-1]+[dict(records()[-1],replicate_id="s2v2-dev-a-001")]):
        with pytest.raises(ExecutionError): build_qualification_record(evaluation_records=rs,**KW)

def test_persistence_exact_reread_and_conflict(tmp_path):
    rs=records(); r=build_qualification_record(evaluation_records=rs,**KW); a=persist_qualification_record(artifact_root=tmp_path,record=r); b=persist_qualification_record(artifact_root=tmp_path,record=r); assert a==b
    assert not (tmp_path/QUALIFICATION_DIR/"latest.json").exists()
    assert verify_qualification_record(artifact_root=tmp_path,evaluation_records=rs,**KW)==r


def test_qualify_only_cli_verifies_and_persists_without_rerunning(tmp_path,
                                                                 monkeypatch):
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from test_run_s2v2_heldout import _ack_fixture, _lineage
    finally:
        sys.path.pop(0)
    from rudeus.science import run_s2v2_heldout as runner

    deva, ack_root, _ = _ack_fixture(tmp_path, monkeypatch)
    store_root, artifact_root = tmp_path / "store", tmp_path / "artifacts"
    runner.open_s2v2_heldout(
        dev_a_artifact_root=deva, pre_heldout_artifact_root=ack_root,
        store_root=store_root, artifact_root=artifact_root,
        code_revision="heldout-fixture-execution-revision")
    store_root, artifact_root, truth_hash, _, estimator_hashes = _lineage(tmp_path)
    runner.persist_heldout_evaluations(
        store_root=store_root, artifact_root=artifact_root,
        estimator_hashes=estimator_hashes, truth_hash=truth_hash,
        code_revision="heldout-fixture-execution-revision",
        dev_a_artifact_root=deva,
        pre_heldout_artifact_root=ack_root)
    evaluation_dir = artifact_root / runner.EVALUATION_DIR
    evaluation_bytes = {p.name: p.read_bytes() for p in evaluation_dir.glob("*.json")}
    args = [
        "--dev-a-artifact-root", str(deva),
        "--pre-heldout-artifact-root", str(ack_root),
        "--store-root", str(store_root), "--artifact-root", str(artifact_root),
        "--code-revision", "heldout-fixture-execution-revision",
        "--estimator-hashes", json.dumps(estimator_hashes, sort_keys=True),
        "--truth-hash", truth_hash, "--qualify-only",
    ]

    # A malformed evaluation must fail before a QualificationRecord appears.
    damaged_path = next(evaluation_dir.glob("*.json"))
    damaged_bytes = damaged_path.read_bytes()
    damaged_path.write_bytes(b"{")
    with pytest.raises(ExecutionError):
        runner.main(args)
    assert not (artifact_root / QUALIFICATION_DIR).exists()
    damaged_path.write_bytes(damaged_bytes)

    gate_calls, evaluation_calls, replay_calls = [], [], []
    gate = runner.verify_heldout_open_authorization
    verify_evaluations = runner.verify_heldout_evaluation_complete
    replay = runner.verify_qualification_record

    def gate_spy(**kwargs):
        gate_calls.append(kwargs)
        return gate(**kwargs)

    def evaluation_spy(**kwargs):
        evaluation_calls.append(kwargs)
        return verify_evaluations(**kwargs)

    def replay_spy(**kwargs):
        replay_calls.append(kwargs)
        return replay(**kwargs)

    monkeypatch.setattr(runner, "verify_heldout_open_authorization", gate_spy)
    monkeypatch.setattr(runner, "verify_heldout_evaluation_complete", evaluation_spy)
    monkeypatch.setattr(runner, "verify_qualification_record", replay_spy)
    for name in ("run_s2v2_heldout_materialize", "run_s2v2_heldout_estimate",
                 "run_s2v2_heldout_evaluate"):
        monkeypatch.setattr(runner, name,
                            lambda **kwargs: pytest.fail(f"{name} reran HELDOUT"))

    runner.main(args)
    assert len(gate_calls) >= 2  # qualification and evaluation replay gates
    assert len(evaluation_calls) == 1
    assert len(replay_calls) == 1
    assert {p.name: p.read_bytes() for p in evaluation_dir.glob("*.json")} == evaluation_bytes
    qualification_dir = artifact_root / QUALIFICATION_DIR
    qualification_files = list(qualification_dir.glob("*.json"))
    assert len(qualification_files) == 1
    assert qualification_files[0].stem == digest(json.loads(qualification_files[0].read_bytes()))

