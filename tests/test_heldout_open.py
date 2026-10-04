"""Fixture-only adversarial tests for the S2 v2 HELDOUT open marker."""
import json
import sys
from pathlib import Path

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science import heldout_open
from rudeus.science import run_s2v2_heldout as runner
from rudeus.science.contracts import canonical_bytes, digest

REVISION = "heldout-fixture-execution-revision"


def _ack_fixture(tmp_path, monkeypatch, *, persist=True, corrupt=False):
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from test_run_s2v2_heldout import _ack_fixture as make_ack
    finally:
        sys.path.pop(0)
    return make_ack(tmp_path, monkeypatch, persist=persist, corrupt=corrupt)


def _target(tmp_path):
    return tmp_path / "heldout-store", tmp_path / "heldout-artifacts"


def _open(tmp_path, monkeypatch, *, persist=True, corrupt=False,
          revision=REVISION):
    deva, ack, _ = _ack_fixture(
        tmp_path, monkeypatch, persist=persist, corrupt=corrupt)
    store, artifacts = _target(tmp_path)
    record = runner.open_s2v2_heldout(
        dev_a_artifact_root=deva, pre_heldout_artifact_root=ack,
        store_root=store, artifact_root=artifacts, code_revision=revision)
    return deva, ack, store, artifacts, record


def _verify(deva, ack, store, artifacts, revision=REVISION):
    return runner.verify_heldout_open_authorization(
        dev_a_artifact_root=deva, pre_heldout_artifact_root=ack,
        store_root=store, artifact_root=artifacts, code_revision=revision)


def _rewrite_marker(artifacts, mutation):
    directory = artifacts / heldout_open.OPEN_DIR
    path = next(directory.glob("*.json"))
    original = json.loads(path.read_bytes())
    path.unlink()
    changed = dict(original, **mutation)
    changed_hash = digest(changed)
    (directory / f"{changed_hash}.json").write_bytes(canonical_bytes(changed))


def test_open_marker_is_deterministic_content_addressed_and_re_read(monkeypatch,
                                                                    tmp_path):
    deva, ack, store, artifacts, result = _open(tmp_path, monkeypatch)
    record = result["marker"]
    marker_path = artifacts / heldout_open.OPEN_DIR / f"{result['marker_hash']}.json"
    assert marker_path.read_bytes() == canonical_bytes(record)
    assert digest(json.loads(marker_path.read_bytes())) == result["marker_hash"]
    assert record["format"] == "s2v2-heldout-open-v1"
    assert record["transition"] == "OPEN"
    assert record["previous_status"] == "UNOPENED"
    assert record["heldout_status"] == "OPENED"
    identity = record["execution_root_identity"]
    context = runner.verify_pre_heldout_gate(
        dev_a_artifact_root=deva, pre_heldout_artifact_root=ack)
    again = heldout_open.build_heldout_open_marker(
        context=context, code_revision=REVISION, root_identity=identity)
    assert canonical_bytes(again) == marker_path.read_bytes()
    assert digest(again) == result["marker_hash"]
    assert heldout_open.execution_root_identity(
        store_root=store, artifact_root=artifacts) == identity
    assert heldout_open.execution_root_identity(
        store_root=store.with_name("other-store"),
        artifact_root=artifacts) != identity
    assert not store.exists()
    assert sorted(p.name for p in artifacts.iterdir()) == [heldout_open.OPEN_DIR]
    with pytest.raises(ExecutionError, match="already exists or conflicts"):
        runner.open_s2v2_heldout(
            dev_a_artifact_root=deva, pre_heldout_artifact_root=ack,
            store_root=store, artifact_root=artifacts, code_revision=REVISION)


@pytest.mark.parametrize("persist,corrupt", [(False, False), (True, True)])
def test_missing_or_wrong_ack_refuses_marker_creation(
        persist, corrupt, monkeypatch, tmp_path):
    deva, ack, _ = _ack_fixture(
        tmp_path, monkeypatch, persist=persist, corrupt=corrupt)
    store, artifacts = _target(tmp_path)
    with pytest.raises(ExecutionError):
        runner.open_s2v2_heldout(
            dev_a_artifact_root=deva, pre_heldout_artifact_root=ack,
            store_root=store, artifact_root=artifacts, code_revision=REVISION)
    assert not store.exists()
    assert not artifacts.exists()


@pytest.mark.parametrize("mutation", [
    {"pre_heldout_acknowledgment_hash": "0" * 64},
    {"method_hash": "1" * 64},
    {"criterion_hash": "2" * 64},
    {"heldout_population_hash": "3" * 64},
    {"populations_hash": "4" * 64},
    {"calibration_package_hash": "5" * 64},
    {"q_hat": 123.0},
    {"dev_b_summary_hash": "6" * 64},
    {"dev_b_summary_code_revision": "7" * 64},
    {"heldout_execution_code_revision": "other-revision"},
    {"execution_root_identity": "8" * 64},
    {"transition": "CLOSE"},
    {"previous_status": "OPENED"},
    {"heldout_status": "UNOPENED"},
])
def test_digest_valid_marker_mutations_are_rejected(mutation, monkeypatch,
                                                     tmp_path):
    deva, ack, store, artifacts, _ = _open(tmp_path, monkeypatch)
    _rewrite_marker(artifacts, mutation)
    with pytest.raises(ExecutionError):
        _verify(deva, ack, store, artifacts)


def test_wrong_root_or_revision_marker_is_rejected(monkeypatch, tmp_path):
    deva, ack, store, artifacts, _ = _open(tmp_path, monkeypatch)
    with pytest.raises(ExecutionError):
        _verify(deva, ack, store.with_name("different-store"), artifacts)
    with pytest.raises(ExecutionError):
        _verify(deva, ack, store, artifacts, "different-code-revision")


def test_duplicate_or_conflicting_marker_is_rejected(monkeypatch, tmp_path):
    deva, ack, store, artifacts, result = _open(tmp_path, monkeypatch)
    directory = artifacts / heldout_open.OPEN_DIR
    conflict = dict(result["marker"], q_hat=result["marker"]["q_hat"] + 1)
    conflict_hash = digest(conflict)
    (directory / f"{conflict_hash}.json").write_bytes(canonical_bytes(conflict))
    with pytest.raises(ExecutionError, match="duplicate, or conflicting"):
        _verify(deva, ack, store, artifacts)


def test_missing_or_wrong_marker_blocks_all_direct_write_gates(
        monkeypatch, tmp_path):
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from test_run_s2v2_heldout import _RecordingStore
    finally:
        sys.path.pop(0)

    deva, ack, _ = _ack_fixture(tmp_path, monkeypatch)
    store_root, artifacts = _target(tmp_path)
    store = _RecordingStore()
    family = {"scope": "e" * 64, "truth": "d" * 64, "generator": "f" * 64}
    with pytest.raises(ExecutionError, match="marker is missing"):
        runner.build_s2v2_heldout_plan(
            store, family, REVISION, dev_a_artifact_root=deva,
            pre_heldout_artifact_root=ack, store_root=store_root,
            artifact_root=artifacts)
    with pytest.raises(ExecutionError, match="marker is missing"):
        runner.build_s2v2_heldout_dataset(
            store, family, REVISION, dev_a_artifact_root=deva,
            pre_heldout_artifact_root=ack, store_root=store_root,
            artifact_root=artifacts)
    with pytest.raises(ExecutionError, match="marker is missing"):
        runner.run_s2v2_heldout_materialize(
            dev_a_artifact_root=deva, pre_heldout_artifact_root=ack,
            store_root=store_root, artifact_root=artifacts,
            code_revision=REVISION)
    for entrypoint in (runner.run_s2v2_heldout_estimate,
                       runner.run_s2v2_heldout_evaluate):
        with pytest.raises(ExecutionError, match="marker is missing"):
            entrypoint(dev_a_artifact_root=deva,
                       pre_heldout_artifact_root=ack,
                       store_root=store_root, artifact_root=artifacts,
                       code_revision=REVISION)
    with pytest.raises(ExecutionError, match="marker is missing"):
        runner.persist_heldout_evaluations(
            store_root=store_root, artifact_root=artifacts,
            estimator_hashes={}, truth_hash="d" * 64,
            code_revision=REVISION, dev_a_artifact_root=deva,
            pre_heldout_artifact_root=ack)
    assert store.records == []
    assert not store_root.exists()
    assert not artifacts.exists()

    _, _, other_store, other_artifacts, _ = _open(
        tmp_path / "different", monkeypatch)
    with pytest.raises(ExecutionError):
        runner.build_s2v2_heldout_dataset(
            store, family, REVISION, dev_a_artifact_root=deva,
            pre_heldout_artifact_root=ack, store_root=store_root,
            artifact_root=other_artifacts)
    assert store.records == []
    assert other_store.exists() is False


def test_wrong_marker_stops_materialization_before_first_output(
        monkeypatch, tmp_path):
    deva, ack, store, artifacts, _ = _open(
        tmp_path, monkeypatch, revision="different-code-revision")
    with pytest.raises(ExecutionError, match="does not match"):
        runner.run_s2v2_heldout_materialize(
            dev_a_artifact_root=deva, pre_heldout_artifact_root=ack,
            store_root=store, artifact_root=artifacts,
            code_revision=REVISION)
    assert not (store / "calibration_plans").exists()
    assert not (store / "calibration_datasets").exists()
    assert not (artifacts / "trajectory_manifests").exists()
    assert not (artifacts / "attempts").exists()
    assert sorted(p.name for p in artifacts.iterdir()) == [heldout_open.OPEN_DIR]


def test_valid_marker_allows_next_preflight_without_execution(monkeypatch,
                                                              tmp_path):
    deva, ack, store, artifacts, _ = _open(tmp_path, monkeypatch)
    result = runner.preflight_s2v2_heldout(
        dev_a_artifact_root=deva, pre_heldout_artifact_root=ack,
        store_root=store, artifact_root=artifacts, code_revision=REVISION)
    assert result["preflight"] == "VERIFIED"
    assert result["open_marker_hash"]
    assert not store.exists()
    assert [p.name for p in artifacts.iterdir()] == [heldout_open.OPEN_DIR]


def test_cli_open_action_stops_after_marker(monkeypatch, tmp_path):
    deva, ack, _ = _ack_fixture(tmp_path, monkeypatch)
    store, artifacts = _target(tmp_path)
    runner.main([
        "--dev-a-artifact-root", str(deva),
        "--pre-heldout-artifact-root", str(ack),
        "--store-root", str(store), "--artifact-root", str(artifacts),
        "--code-revision", REVISION, "--open-heldout",
    ])
    assert list((artifacts / heldout_open.OPEN_DIR).glob("*.json"))
    assert not store.exists()
    assert sorted(p.name for p in artifacts.iterdir()) == [heldout_open.OPEN_DIR]
