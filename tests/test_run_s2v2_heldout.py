"""Fixture-only tests for the S2 v2 HELDOUT execution runner.

All artifacts live under pytest temporary directories. No real HELDOUT root or
outcomes are accessed and no 379-replicate simulation is run.
"""
import hashlib
import json
from pathlib import Path

import pytest

from rudeus.execution.contracts import ArtifactManifest, ExecutionError
from rudeus.science import run_s2v2_heldout as heldout
from rudeus.science.calibration import CalibrationReplicateManifest
from rudeus.science.calibration_estimator import ESTIMATOR_MODULE, ESTIMATOR_NAME
from rudeus.science.calibration_s2v2_heldout import (
    build_s2v2_heldout_evaluation,
)
from rudeus.science.calibration_s2v2_populations import (
    S2V2_DEV_A_SEEDS, S2V2_DEV_B_SEEDS, S2V2_HELDOUT_HASH,
    S2V2_HELDOUT_SEEDS,
)
from rudeus.science.calibration_store import CalibrationStore
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science import pre_heldout_no_change as no_change

REVISION = "heldout-fixture-execution-revision"
PACKAGE_HASH = "a" * 64
MANIFEST_HASH = "b" * 64
RESULT_HASH = "c" * 64
TRUTH_HASH = "d" * 64


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(payload))


def _ack_fixture(tmp_path, monkeypatch, *, persist=True, corrupt=False):
    """Build and verify the real pre-HELDOUT acknowledgment in tmp roots."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from test_pre_heldout_no_change import _setup, _kwargs
    finally:
        sys.path.pop(0)

    names = (
        "S2V2_FROZEN_PACKAGE_HASH", "S2V2_FROZEN_IDENTITY_HASH",
        "S2V2_FROZEN_DEV_B_SUMMARY_HASH", "S2V2_FROZEN_DEV_B_CODE_REVISION",
    )
    # Register restoration before the fixture helper temporarily changes the
    # no-change verifier's frozen pins.
    for name in names:
        monkeypatch.setattr(no_change, name, getattr(no_change, name))
    ack_root = tmp_path / "ack-fixture"
    hashes = _setup(ack_root)
    monkeypatch.setattr(heldout, "S2V2_FROZEN_PACKAGE_HASH", hashes["package_hash"])
    monkeypatch.setattr(heldout, "S2V2_FROZEN_IDENTITY_HASH", hashes["identity_hash"])
    monkeypatch.setattr(heldout, "S2V2_FROZEN_DEV_B_SUMMARY_HASH", hashes["summary_hash"])
    monkeypatch.setattr(heldout, "S2V2_FROZEN_ACKNOWLEDGMENT_HASH",
                        digest(no_change.build_pre_heldout_no_change(
                            method_hash=heldout.S2V2_METHOD_HASH,
                            criterion_hash=heldout.S2V2_CRITERION_HASH,
                            dev_a_population_hash=heldout.S2V2_DEV_A_HASH,
                            dev_b_population_hash=heldout.S2V2_DEV_B_HASH,
                            heldout_population_hash=heldout.S2V2_HELDOUT_HASH,
                            populations_hash=heldout.S2V2_POPULATIONS_HASH,
                            calibration_package_hash=hashes["package_hash"],
                            pre_heldout_identity_hash=hashes["identity_hash"],
                            q_hat=heldout.S2V2_FROZEN_Q_HAT,
                            dev_b_summary_hash=hashes["summary_hash"],
                            dev_b_summary_code_revision=no_change.S2V2_FROZEN_DEV_B_CODE_REVISION)))
    kwargs = _kwargs(ack_root, hashes)
    if persist:
        no_change.acknowledge_pre_heldout_no_change(**kwargs)
    if corrupt:
        ack_path = next((ack_root / "artifacts" / no_change.NO_CHANGE_DIR).glob("*.json"))
        record = json.loads(ack_path.read_bytes())
        record["decision"] = "APPROVED"
        replacement = ack_path.with_name(f"{digest(record)}.json")
        replacement.write_bytes(canonical_bytes(record))
        ack_path.unlink()
    return ack_root / "deva", ack_root / "artifacts", hashes


def _estimator_payload(replicate_id, manifest_hash, truth_hash,
                       revision=REVISION, **changes):
    result = {
        "format": "calibration-estimator-result-v1",
        "replicate_id": replicate_id,
        "replicate_manifest_hash": manifest_hash,
        "truth_record_hash": truth_hash,
        "estimator": ESTIMATOR_NAME,
        "estimator_module": ESTIMATOR_MODULE,
        "estimator_config": {**heldout.EXPECTED_ESTIMATOR_CONFIG,
                             "charge_numbers": None},
        "code_revision": revision,
        "result": {"self_diffusion_by_species": {"Li": {
            "D_m2_per_s": 1.05e-9}}},
    }
    result.update(changes)
    return result


def _lineage(tmp_path, count=379, *, include_estimators=True):
    """Construct complete synthetic lineage; trajectories are tiny fixtures."""
    from rudeus.science.calibration import TruthRecord, TruthType

    store_root, artifact_root = tmp_path / "store", tmp_path / "artifacts"
    store = CalibrationStore(store_root)
    truth = TruthRecord(
        estimand="self_diffusion", units="m2/s", truth_type=TruthType.ANALYTICAL,
        value={"D_m2_per_s": 1e-9}, code_revision="s1-fixture")
    truth_hash = store.store(truth)
    manifest_hashes, estimator_hashes = {}, {}
    for replicate_id in list(S2V2_HELDOUT_SEEDS)[:count]:
        seed = S2V2_HELDOUT_SEEDS[replicate_id]
        scope_hash, generator_hash = "e" * 64, "f" * 64
        trajectory = {"replicate_id": replicate_id, "seed": seed,
                      "scope_hash": scope_hash,
                      "generator_spec_hash": generator_hash, "frames": []}
        trajectory_data = canonical_bytes(trajectory)
        trajectory_hash = digest(trajectory)
        (artifact_root / "blobs" / trajectory_hash).parent.mkdir(
            parents=True, exist_ok=True)
        (artifact_root / "blobs" / trajectory_hash).write_bytes(trajectory_data)
        attempt_id = digest({"attempt": replicate_id})
        artifact = ArtifactManifest(
            logical_hash=trajectory_hash,
            raw_hash=hashlib.sha256(trajectory_data).hexdigest(),
            canonicalization_version="canonical-json-v1",
            format="json", format_version="calibration-trajectory-v1",
            size_bytes=len(trajectory_data),
            durable_locator=f"blobs/{trajectory_hash}",
            producer_attempt=attempt_id, parent_artifact_hashes=(),
            retrieval_verification={"status": "STORED",
                                     "verifier": "canonical-json-v1"})
        _write(artifact_root / "trajectory_manifests"
               / f"{artifact.content_hash}.json", artifact.to_dict())
        attempt = {"attempt_id": attempt_id, "status": "COMPLETED",
                   "exit_status": 0,
                   "environment": {"code_revision": REVISION},
                   "output_manifest": {"trajectory": artifact.content_hash}}
        attempt_hash = digest(attempt)
        _write(artifact_root / "attempts" / f"{attempt_hash}.json", attempt)
        manifest = CalibrationReplicateManifest(
            replicate_id=replicate_id, dataset_id=heldout.DATASET_ID,
            parameter_cell_id="cell-a", split_assignment="HELD_OUT",
            independence_declaration={}, seed=seed,
            trajectory_artifact_hash=trajectory_hash,
            truth_record_hash=truth_hash,
            conditions={"code_revision": REVISION, "seed": seed,
                        "scope_hash": scope_hash},
            execution_attempt_hash=attempt_hash,
            scientific_outcome="COMPLETED")
        manifest_hash = store.store(manifest)
        manifest_hashes[replicate_id] = manifest_hash
        if include_estimators:
            estimator = _estimator_payload(replicate_id, manifest_hash, truth_hash)
            estimator_hash = digest(estimator)
            _write(artifact_root / "estimator_results" / f"{estimator_hash}.json",
                   estimator)
            estimator_hashes[replicate_id] = estimator_hash
    return store_root, artifact_root, truth_hash, manifest_hashes, estimator_hashes


def test_frozen_population_is_exact():
    assert len(S2V2_HELDOUT_SEEDS) == 379
    assert list(S2V2_HELDOUT_SEEDS.values()) == list(range(478, 857))
    assert not (set(S2V2_HELDOUT_SEEDS) & set(S2V2_DEV_A_SEEDS))
    assert not (set(S2V2_HELDOUT_SEEDS) & set(S2V2_DEV_B_SEEDS))
    assert S2V2_HELDOUT_HASH == "284937cae122b3ddcf258abb9819d965a0fca94379045313be36f77cc199d478"


def test_acknowledgment_replay_is_required_and_exact(monkeypatch, tmp_path):
    deva_root, pre_root, _ = _ack_fixture(tmp_path, monkeypatch)
    calls = []
    original_verify = no_change.verify_pre_heldout_no_change_complete

    def verify(**kwargs):
        calls.append(kwargs)
        return original_verify(**kwargs)

    monkeypatch.setattr(no_change, "verify_pre_heldout_no_change_complete", verify)
    result = heldout.verify_pre_heldout_gate(
        dev_a_artifact_root=deva_root, pre_heldout_artifact_root=pre_root)
    assert calls and result["decision"] == "NO-CHANGE"
    assert result["heldout_status"] == "UNOPENED"
    assert result["post_dev_b_tuning"] == "FORBIDDEN"
    assert result["dev_b_role"] == "DESCRIPTIVE-NON-QUALIFICATION"
    assert result["q_hat"] == heldout.S2V2_FROZEN_Q_HAT

    monkeypatch.setattr(no_change, "verify_pre_heldout_no_change_complete",
                        lambda **kwargs: {"acknowledgment_hash": "0" * 64})
    with pytest.raises(ExecutionError, match="acknowledgment hash"):
        heldout.verify_pre_heldout_gate(
            dev_a_artifact_root=deva_root,
            pre_heldout_artifact_root=pre_root)


def test_exact_ack_read_uses_verified_hash(monkeypatch, tmp_path):
    _, pre_root, _ = _ack_fixture(tmp_path, monkeypatch)
    ack_path = next((pre_root / no_change.NO_CHANGE_DIR).glob("*.json"))
    record = heldout._read_verified_pre_heldout_acknowledgment(
        pre_heldout_artifact_root=pre_root,
        acknowledgment_hash=ack_path.stem)
    assert digest(record) == ack_path.stem
    assert record["calibration_package_hash"] == heldout.S2V2_FROZEN_PACKAGE_HASH
    assert record["q_hat"] == heldout.S2V2_FROZEN_Q_HAT


def test_exact_ack_read_refuses_changed_bytes_at_same_filename(monkeypatch,
                                                                tmp_path):
    _, pre_root, _ = _ack_fixture(tmp_path, monkeypatch)
    ack_path = next((pre_root / no_change.NO_CHANGE_DIR).glob("*.json"))
    ack_hash = ack_path.stem
    ack_path.write_bytes(ack_path.read_bytes() + b" ")
    with pytest.raises(ExecutionError):
        heldout._read_verified_pre_heldout_acknowledgment(
            pre_heldout_artifact_root=pre_root,
            acknowledgment_hash=ack_hash)


def test_exact_ack_read_refuses_wrong_digest(monkeypatch, tmp_path):
    _, pre_root, _ = _ack_fixture(tmp_path, monkeypatch)
    ack_path = next((pre_root / no_change.NO_CHANGE_DIR).glob("*.json"))
    wrong_hash = "f" * 64
    wrong_path = ack_path.with_name(f"{wrong_hash}.json")
    wrong_path.write_bytes(ack_path.read_bytes())
    with pytest.raises(ExecutionError, match="differ from the verified hash"):
        heldout._read_verified_pre_heldout_acknowledgment(
            pre_heldout_artifact_root=pre_root,
            acknowledgment_hash=wrong_hash)


def test_exact_ack_read_does_not_fallback_to_alternate_file(monkeypatch,
                                                             tmp_path):
    _, pre_root, _ = _ack_fixture(tmp_path, monkeypatch)
    ack_path = next((pre_root / no_change.NO_CHANGE_DIR).glob("*.json"))
    ack_hash = ack_path.stem
    alternate = ack_path.with_name("e" * 64 + ".json")
    ack_path.rename(alternate)
    with pytest.raises(ExecutionError, match="verified acknowledgment could not be re-read"):
        heldout._read_verified_pre_heldout_acknowledgment(
            pre_heldout_artifact_root=pre_root,
            acknowledgment_hash=ack_hash)


def test_evaluation_replay_enforces_strict_ack_firewall(monkeypatch, tmp_path):
    deva_root, pre_root, _ = _ack_fixture(tmp_path, monkeypatch)
    # Presence alone is enough for the original gate to refuse; this fixture
    # contains no HELDOUT outcome and the replay never reads this file.
    marker = pre_root / "heldout_evaluations" / "fixture-marker.json"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"")
    with pytest.raises(ExecutionError, match="HELDOUT evidence already exists"):
        heldout.verify_heldout_evaluation_complete(
            store_root=tmp_path / "store", artifact_root=tmp_path / "evaluation-root",
            estimator_hashes={}, truth_hash=TRUTH_HASH, code_revision=REVISION,
            dev_a_artifact_root=deva_root,
            pre_heldout_artifact_root=pre_root)


def test_ack_failure_precedes_any_heldout_write(monkeypatch, tmp_path):
    def refuse(**kwargs):
        raise ExecutionError("bad persisted acknowledgment", "INTEGRITY")

    monkeypatch.setattr(heldout, "verify_pre_heldout_gate", refuse)
    store_root, artifact_root = tmp_path / "store", tmp_path / "artifacts"
    with pytest.raises(ExecutionError):
        heldout.run_s2v2_heldout_materialize(
            dev_a_artifact_root=tmp_path / "deva",
            pre_heldout_artifact_root=tmp_path / "pre", store_root=store_root,
            artifact_root=artifact_root, code_revision=REVISION)
    assert not store_root.exists()
    assert not artifact_root.exists()


class _RecordingStore:
    def __init__(self):
        self.records = []

    def store(self, record):
        self.records.append(record)
        return digest(record.to_dict())


@pytest.mark.parametrize("entrypoint", ["plan", "dataset"])
@pytest.mark.parametrize("ack_state", ["missing", "wrong"])
def test_direct_plan_dataset_calls_refuse_before_first_write(
        entrypoint, ack_state, monkeypatch, tmp_path):
    deva_root, ack_root, _ = _ack_fixture(
        tmp_path, monkeypatch, persist=ack_state == "wrong",
        corrupt=ack_state == "wrong")
    store = _RecordingStore()
    kwargs = {"dev_a_artifact_root": deva_root,
              "pre_heldout_artifact_root": ack_root}
    with pytest.raises(ExecutionError):
        if entrypoint == "plan":
            heldout.build_s2v2_heldout_plan(
                store, {"scope": "e" * 64}, REVISION, **kwargs)
        else:
            heldout.build_s2v2_heldout_dataset(
                store, {"scope": "e" * 64, "truth": "d" * 64,
                        "generator": "f" * 64}, REVISION, **kwargs)
    assert store.records == []


def test_direct_plan_dataset_calls_proceed_after_exact_fixture_ack(
        monkeypatch, tmp_path):
    from types import SimpleNamespace

    deva_root, ack_root, _ = _ack_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(heldout, "validate_plan",
                        lambda *_: SimpleNamespace(status=heldout.VALID))
    monkeypatch.setattr(heldout, "validate_dataset",
                        lambda *_: SimpleNamespace(status=heldout.VALID))
    store = _RecordingStore()
    result = heldout.build_s2v2_heldout_dataset(
        store, {"scope": "e" * 64, "truth": "d" * 64,
                "generator": "f" * 64}, REVISION,
        dev_a_artifact_root=deva_root,
        pre_heldout_artifact_root=ack_root)
    assert len(store.records) == 2
    assert result == digest(store.records[-1].to_dict())


@pytest.mark.parametrize("entrypoint", ["materialize", "estimate", "evaluate"])
@pytest.mark.parametrize("ack_state", ["missing", "wrong"])
def test_direct_runner_write_entrypoints_refuse_before_any_write(
        entrypoint, ack_state, monkeypatch, tmp_path):
    deva_root, ack_root, _ = _ack_fixture(
        tmp_path, monkeypatch, persist=ack_state == "wrong",
        corrupt=ack_state == "wrong")
    store_root, artifact_root = tmp_path / "store", tmp_path / "heldout-artifacts"
    args = {"dev_a_artifact_root": deva_root,
            "pre_heldout_artifact_root": ack_root,
            "store_root": store_root, "artifact_root": artifact_root,
            "code_revision": REVISION}
    with pytest.raises(ExecutionError):
        if entrypoint == "materialize":
            heldout.run_s2v2_heldout_materialize(**args)
        elif entrypoint == "estimate":
            heldout.run_s2v2_heldout_estimate(**args)
        else:
            heldout.run_s2v2_heldout_evaluate(**args)
    assert not store_root.exists()
    assert not artifact_root.exists()


@pytest.mark.parametrize("ack_state", ["missing", "wrong"])
def test_evaluation_persistence_direct_call_refuses_before_write(
        ack_state, monkeypatch, tmp_path):
    deva_root, ack_root, _ = _ack_fixture(
        tmp_path, monkeypatch, persist=ack_state == "wrong",
        corrupt=ack_state == "wrong")
    store_root, artifact_root = tmp_path / "store", tmp_path / "artifacts"
    with pytest.raises(ExecutionError):
        heldout.persist_heldout_evaluations(
            store_root=store_root, artifact_root=artifact_root,
            estimator_hashes={}, truth_hash=TRUTH_HASH,
            code_revision=REVISION,
            dev_a_artifact_root=deva_root,
            pre_heldout_artifact_root=ack_root)
    assert not store_root.exists()
    assert not artifact_root.exists()


def test_evaluation_persistence_with_valid_ack_reaches_estimator_gate(
        monkeypatch, tmp_path):
    deva_root, ack_root, _ = _ack_fixture(tmp_path, monkeypatch)
    with pytest.raises(ExecutionError, match="estimator hash inventory"):
        heldout.persist_heldout_evaluations(
            store_root=tmp_path / "store", artifact_root=tmp_path / "artifacts",
            estimator_hashes={}, truth_hash=TRUTH_HASH,
            code_revision=REVISION,
            dev_a_artifact_root=deva_root,
            pre_heldout_artifact_root=ack_root)
    assert not (tmp_path / "artifacts" / heldout.EVALUATION_DIR).exists()


def test_fresh_root_refuses_existing_namespace(tmp_path):
    root = tmp_path / "artifacts"
    (root / heldout.EVALUATION_DIR).mkdir(parents=True)
    with pytest.raises(ExecutionError, match="not fresh"):
        heldout.check_fresh_heldout_root(
            store_root=tmp_path / "store", artifact_root=root)


def test_379_materializations_and_estimators_verify(tmp_path):
    store_root, root, truth_hash, _, estimator_hashes = _lineage(tmp_path)
    materialized = heldout.verify_heldout_materialization_complete(
        store_root=store_root, artifact_root=root, truth_hash=truth_hash,
        code_revision=REVISION)
    assert materialized["materialized"] == 379
    estimated = heldout.verify_heldout_estimator_complete(
        store_root=store_root, artifact_root=root,
        estimator_hashes=estimator_hashes, truth_hash=truth_hash,
        code_revision=REVISION)
    assert estimated["estimated"] == 379
    first_id = next(iter(S2V2_HELDOUT_SEEDS))
    result_path = root / "estimator_results" / f"{estimator_hashes[first_id]}.json"
    assert heldout.resolve_heldout_estimator_result(
        root, estimator_hashes[first_id]) == json.loads(result_path.read_bytes())
    with pytest.raises(ExecutionError):
        heldout.resolve_heldout_estimator_result(root, MANIFEST_HASH)


def test_378_materializations_rejected(tmp_path):
    store_root, root, truth_hash, _, _ = _lineage(tmp_path, count=378)
    with pytest.raises(ExecutionError, match="exactly the frozen 379"):
        heldout.verify_heldout_materialization_complete(
            store_root=store_root, artifact_root=root, truth_hash=truth_hash,
            code_revision=REVISION)


def test_duplicate_and_foreign_materialization_refused(tmp_path):
    store_root, root, truth_hash, _, _ = _lineage(tmp_path)
    store = CalibrationStore(store_root)
    manifest_hash, manifest = heldout._find_manifest(
        store_root, next(iter(S2V2_HELDOUT_SEEDS)))
    duplicate = CalibrationReplicateManifest.from_dict(manifest)
    duplicate = CalibrationReplicateManifest(
        **{**duplicate.to_dict(), "outcome_notes": {"duplicate": True}})
    store.store(duplicate)
    with pytest.raises(ExecutionError, match="duplicate HELDOUT manifest"):
        heldout.verify_heldout_materialization_complete(
            store_root=store_root, artifact_root=root, truth_hash=truth_hash,
            code_revision=REVISION)
    (store_root / "calibration_replicates" / f"{digest(duplicate.to_dict())}.json").unlink()
    for foreign_id, foreign_seed in (
            (next(iter(S2V2_DEV_A_SEEDS)), 265),
            (next(iter(S2V2_DEV_B_SEEDS)), 364)):
        foreign = CalibrationReplicateManifest(
            replicate_id=foreign_id, dataset_id=heldout.DATASET_ID,
            parameter_cell_id="cell-a", split_assignment="HELD_OUT",
            independence_declaration={}, seed=foreign_seed,
            trajectory_artifact_hash=manifest["trajectory_artifact_hash"],
            truth_record_hash=truth_hash,
            conditions={"code_revision": REVISION, "seed": foreign_seed,
                        "scope_hash": "e" * 64},
            execution_attempt_hash=manifest["execution_attempt_hash"],
            scientific_outcome="COMPLETED")
        foreign_hash = store.store(foreign)
        with pytest.raises(ExecutionError, match="foreign replicate"):
            heldout.verify_heldout_materialization_complete(
                store_root=store_root, artifact_root=root, truth_hash=truth_hash,
                code_revision=REVISION)
        (store_root / "calibration_replicates" / f"{foreign_hash}.json").unlink()
    assert manifest_hash


@pytest.mark.parametrize("field,value", [
    ("estimator_module", "foreign.module"),
    ("code_revision", "older-revision"),
])
def test_wrong_estimator_module_or_revision_refused(field, value):
    payload = _estimator_payload("s2v2-heldout-001", MANIFEST_HASH, TRUTH_HASH,
                                 **{field: value})
    with pytest.raises(ExecutionError):
        heldout.verify_heldout_estimator_result(
            payload, replicate_id="s2v2-heldout-001",
            manifest_hash=MANIFEST_HASH, truth_hash=TRUTH_HASH,
            code_revision=REVISION)


def test_wrong_estimator_config_refused():
    payload = _estimator_payload("s2v2-heldout-001", MANIFEST_HASH, TRUTH_HASH)
    payload["estimator_config"] = dict(payload["estimator_config"], lag_steps=[1, 99])
    with pytest.raises(ExecutionError):
        heldout.verify_heldout_estimator_result(
            payload, replicate_id="s2v2-heldout-001",
            manifest_hash=MANIFEST_HASH, truth_hash=TRUTH_HASH,
            code_revision=REVISION)


def test_estimator_completeness_before_any_evaluation_write(tmp_path, monkeypatch):
    store_root, root, truth_hash, _, estimator_hashes = _lineage(
        tmp_path, count=1, include_estimators=False)
    root.mkdir(parents=True, exist_ok=True)
    deva_root, ack_root, _ = _ack_fixture(tmp_path, monkeypatch)
    with pytest.raises(ExecutionError):
        heldout.persist_heldout_evaluations(
            store_root=store_root, artifact_root=root,
            estimator_hashes={}, truth_hash=truth_hash, code_revision=REVISION,
            dev_a_artifact_root=deva_root,
            pre_heldout_artifact_root=ack_root)
    assert not (root / heldout.EVALUATION_DIR).exists()


def test_exact_379_evaluations_and_replay_tamper_refusal(tmp_path, monkeypatch):
    store_root, root, truth_hash, _, estimator_hashes = _lineage(tmp_path)
    deva_root, ack_root, _ = _ack_fixture(tmp_path, monkeypatch)
    hashes = heldout.persist_heldout_evaluations(
        store_root=store_root, artifact_root=root,
        estimator_hashes=estimator_hashes, truth_hash=truth_hash,
        code_revision=REVISION,
        dev_a_artifact_root=deva_root,
        pre_heldout_artifact_root=ack_root)
    assert len(hashes) == 379
    ack_hash = next((ack_root / no_change.NO_CHANGE_DIR).glob("*.json")).stem
    persisted_record = json.loads(
        (root / heldout.EVALUATION_DIR
         / f"{next(iter(hashes.values()))}.json").read_bytes())
    assert persisted_record["format"] == "s2v2-heldout-evaluation-v2"
    assert persisted_record["pre_heldout_acknowledgment_hash"] == ack_hash
    assert persisted_record["calibration_package_hash"] == heldout.S2V2_FROZEN_PACKAGE_HASH
    assert persisted_record["q_hat"] == heldout.S2V2_FROZEN_Q_HAT
    assert persisted_record["method_hash"] == heldout.S2V2_METHOD_HASH
    assert persisted_record["population_hash"] == S2V2_HELDOUT_HASH
    assert persisted_record["code_revision"] == REVISION
    replay_args = dict(
        store_root=store_root, artifact_root=root,
        estimator_hashes=estimator_hashes, truth_hash=truth_hash,
        code_revision=REVISION, dev_a_artifact_root=deva_root,
        pre_heldout_artifact_root=ack_root)
    verified = heldout.verify_heldout_evaluation_complete(
        **replay_args)
    assert verified["evaluated"] == 379

    # Caller context is checked only against the independently replayed ack.
    for substitution in (
            {"q_hat": heldout.S2V2_FROZEN_Q_HAT * 2},
            {"calibration_package_hash": "f" * 64},
            {"pre_heldout_acknowledgment_hash": "0" * 64}):
        with pytest.raises(ExecutionError, match="caller-supplied"):
            heldout.verify_heldout_evaluation_complete(
                **replay_args, **substitution)

    # Even a digest-valid evaluation whose provenance fields agree with the
    # caller's forged context cannot override the exact persisted ack.
    first_eval_hash = next(iter(hashes.values()))
    first_eval_path = root / heldout.EVALUATION_DIR / f"{first_eval_hash}.json"
    first_eval_bytes = first_eval_path.read_bytes()
    first_eval = json.loads(first_eval_bytes)
    forged_context = dict(
        first_eval, pre_heldout_acknowledgment_hash="0" * 64,
        calibration_package_hash="f" * 64,
        q_hat=first_eval["q_hat"] * 2)
    forged_context_hash = digest(forged_context)
    forged_context_path = first_eval_path.with_name(f"{forged_context_hash}.json")
    forged_context_path.write_bytes(canonical_bytes(forged_context))
    first_eval_path.unlink()
    with pytest.raises(ExecutionError, match="caller-supplied"):
        heldout.verify_heldout_evaluation_complete(
            **replay_args, q_hat=forged_context["q_hat"],
            calibration_package_hash=forged_context["calibration_package_hash"],
            pre_heldout_acknowledgment_hash=(
                forged_context["pre_heldout_acknowledgment_hash"]))
    forged_context_path.unlink()
    first_eval_path.write_bytes(first_eval_bytes)

    # A semantically forged, digest-valid alternate acknowledgment is rejected
    # by the real replay verifier before any evaluation is trusted.
    ack_path = ack_root / no_change.NO_CHANGE_DIR / f"{ack_hash}.json"
    ack_bytes = ack_path.read_bytes()
    forged_ack = json.loads(ack_bytes)
    forged_ack["decision"] = "NO-CHANGE-ALTERNATE"
    alternate_ack_hash = digest(forged_ack)
    alternate_ack_path = ack_path.with_name(f"{alternate_ack_hash}.json")
    alternate_ack_path.write_bytes(canonical_bytes(forged_ack))
    ack_path.unlink()
    with pytest.raises(ExecutionError, match="replay mismatch"):
        heldout.verify_heldout_evaluation_complete(**replay_args)
    alternate_ack_path.unlink()
    ack_path.write_bytes(ack_bytes)

    # Missing, duplicate-logical, and foreign evaluations all fail the exact
    # frozen-inventory/replay check.
    first_hash = next(iter(hashes.values()))
    record_path = root / heldout.EVALUATION_DIR / f"{first_hash}.json"
    original_bytes = record_path.read_bytes()
    record = json.loads(original_bytes)
    record_path.unlink()
    with pytest.raises(ExecutionError, match="exactly one record"):
        heldout.verify_heldout_evaluation_complete(
            **replay_args)
    record_path.write_bytes(original_bytes)
    duplicate = dict(record, interval_lower=record["interval_lower"] - 1.0)
    duplicate_hash = digest(duplicate)
    _write(root / heldout.EVALUATION_DIR / f"{duplicate_hash}.json", duplicate)
    with pytest.raises(ExecutionError, match="exactly one record"):
        heldout.verify_heldout_evaluation_complete(
            **replay_args)
    (root / heldout.EVALUATION_DIR / f"{duplicate_hash}.json").unlink()
    foreign = dict(record, replicate_id=next(iter(S2V2_DEV_A_SEEDS)))
    foreign_hash = digest(foreign)
    _write(root / heldout.EVALUATION_DIR / f"{foreign_hash}.json", foreign)
    with pytest.raises(ExecutionError, match="foreign HELDOUT evaluation"):
        heldout.verify_heldout_evaluation_complete(
            **replay_args)
    (root / heldout.EVALUATION_DIR / f"{foreign_hash}.json").unlink()

    record_path = root / heldout.EVALUATION_DIR / f"{next(iter(hashes.values()))}.json"
    original_record_bytes = record_path.read_bytes()
    record = json.loads(original_record_bytes)
    mutations = {
        "pre_heldout_acknowledgment_hash": "0" * 64,
        "calibration_package_hash": "1" * 64,
        "q_hat": record["q_hat"] * 2,
        "method_hash": "2" * 64,
        "population_hash": "3" * 64,
        "code_revision": "forged-current-revision",
        "replicate_manifest_hash": "4" * 64,
        "estimator_result_hash": "5" * 64,
        "truth_record_hash": "6" * 64,
        "interval_lower": record["interval_lower"] + 1.0,
        "interval_upper": record["interval_upper"] + 1.0,
        "covered": not record["covered"],
        "signed_error": record["signed_error"] + 1.0,
        "absolute_error": record["absolute_error"] + 1.0,
    }
    for field, value in mutations.items():
        forged = dict(record, **{field: value})
        forged_hash = digest(forged)
        forged_path = record_path.with_name(f"{forged_hash}.json")
        forged_path.write_bytes(canonical_bytes(forged))
        record_path.unlink()
        with pytest.raises(ExecutionError, match="replay mismatch"):
            heldout.verify_heldout_evaluation_complete(**replay_args)
        forged_path.unlink()
        record_path.write_bytes(original_record_bytes)


def test_builder_uses_closed_interval_without_zero_clipping():
    result = build_s2v2_heldout_evaluation(
        replicate_id="s2v2-heldout-001",
        replicate_manifest_hash=MANIFEST_HASH,
        estimator_result_hash=RESULT_HASH, truth_record_hash=TRUTH_HASH,
        estimate_D=0.0, truth_D=heldout.S2V2_FROZEN_Q_HAT,
        pre_heldout_acknowledgment_hash=PACKAGE_HASH,
        calibration_package_hash=PACKAGE_HASH,
        q_hat=heldout.S2V2_FROZEN_Q_HAT, code_revision=REVISION)
    assert result["interval_lower"] < 0
    assert result["covered"] is True
    assert "PASS" not in result and "FAIL" not in result


def test_cli_requires_exactly_one_mode():
    args = ["--dev-a-artifact-root", "deva", "--pre-heldout-artifact-root", "pre",
            "--store-root", "store", "--artifact-root", "artifacts",
            "--code-revision", REVISION]
    with pytest.raises(SystemExit):
        heldout.main(args)
