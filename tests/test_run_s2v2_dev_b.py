"""Focused tests for S2 v2 DEV-B preflight (tmp fixtures only).

No real DEV-A root access, no DEV-B execution, no HELD_OUT access. Valid
fixture packages are generated with the committed Stage-B freeze builder
using crafted scores whose 90th order statistic equals the frozen q_hat.
"""
import inspect
import json
from pathlib import Path

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science import calibration_s2v2_populations as pop
from rudeus.science import run_s2v2_dev_b as preflight
from rudeus.science.calibration_s2v2_stageb import (
    build_complete_pre_heldout_identity,
    build_s2v2_score_record,
    freeze_s2v2_calibration_package,
)
from rudeus.science.contracts import digest

TRUTH = 1.0e-9
Q_HAT = preflight.S2V2_FROZEN_Q_HAT
REVISION = "devb-preflight-fixture-revision"
PACKAGE = "a" * 64


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _dev_a_ids():
    return sorted(pop.S2V2_DEV_A_SEEDS)


def _fixture_scores():
    # 89 scores below Q_HAT, Q_HAT itself, 9 above: sorted[89] == Q_HAT.
    # One shared truth hash: a single truth record serves the whole cell.
    targets = [Q_HAT * (i + 1) / 100 for i in range(89)] + [Q_HAT] + \
        [Q_HAT * (1 + i / 10) for i in range(1, 10)]
    records = []
    for position, replicate_id in enumerate(_dev_a_ids()):
        suffix = "%x" % (position % 16)
        records.append(build_s2v2_score_record(
            replicate_id=replicate_id,
            estimate_D=TRUTH + targets[position], truth_D=TRUTH,
            replicate_manifest_hash="c" * 63 + suffix,
            estimator_result_hash="d" * 63 + suffix,
            truth_record_hash="e" * 64,
            code_revision=REVISION))
    return records


def _fixture_package():
    return freeze_s2v2_calibration_package(
        score_records=_fixture_scores(), code_revision=REVISION)


def _fixture_identity(package_hash):
    return build_complete_pre_heldout_identity(
        calibration_package_hash=package_hash, code_revision=REVISION)


def _write_package(root, package):
    identity = digest(package)
    _write(root / "calibration_packages" / f"{identity}.json", package)
    return identity


def _write_identity(root, identity):
    identity_hash = digest(identity)
    _write(root / "pre_heldout_identities" / f"{identity_hash}.json", identity)
    return identity_hash


def _mutated(package, **overrides):
    altered = dict(package)
    altered.update(overrides)
    return altered, digest(altered)


def test_valid_frozen_package_accepted(tmp_path):
    package = _fixture_package()
    assert package["q_hat"] == Q_HAT
    package_hash = _write_package(tmp_path / "deva", package)
    resolved = preflight.resolve_s2v2_calibration_package(
        dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)
    assert digest(resolved) == package_hash


def test_missing_package_rejected(tmp_path):
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash="f" * 64)


def test_malformed_package_rejected(tmp_path):
    _write(tmp_path / "deva" / "calibration_packages" / ("f" * 64 + ".json"),
           "{not json")
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash="f" * 64)


def test_digest_mismatch_rejected(tmp_path):
    package = _fixture_package()
    _write(tmp_path / "deva" / "calibration_packages" / ("f" * 64 + ".json"),
           package)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash="f" * 64)


def test_wrong_method_rejected(tmp_path):
    package, package_hash = _mutated(_fixture_package(), method_hash="0" * 64)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_wrong_criterion_rejected(tmp_path):
    package, package_hash = _mutated(
        _fixture_package(), criterion_hash="0" * 64)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_wrong_population_rejected(tmp_path):
    package, package_hash = _mutated(
        _fixture_package(), dev_a_population_hash="0" * 64)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_wrong_q_hat_rejected(tmp_path):
    package, package_hash = _mutated(_fixture_package(), q_hat=Q_HAT * 2)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_wrong_n_rejected(tmp_path):
    package, package_hash = _mutated(_fixture_package(), n=98)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_wrong_k_rejected(tmp_path):
    package, package_hash = _mutated(_fixture_package(), k=91)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_wrong_target_coverage_rejected(tmp_path):
    package, package_hash = _mutated(
        _fixture_package(), target_coverage=0.95)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_valid_identity_accepted(tmp_path):
    package_hash = _write_package(tmp_path / "deva", _fixture_package())
    identity = _fixture_identity(package_hash)
    identity_hash = _write_identity(tmp_path / "deva", identity)
    resolved = preflight.resolve_s2v2_pre_heldout_identity(
        dev_a_artifact_root=tmp_path / "deva", identity_hash=identity_hash)
    assert digest(resolved) == identity_hash


def test_missing_identity_rejected(tmp_path):
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_pre_heldout_identity(
            dev_a_artifact_root=tmp_path / "deva", identity_hash="f" * 64)


def test_identity_digest_mismatch_rejected(tmp_path):
    identity = _fixture_identity(PACKAGE)
    _write(tmp_path / "deva" / "pre_heldout_identities" / ("f" * 64 + ".json"),
           identity)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_pre_heldout_identity(
            dev_a_artifact_root=tmp_path / "deva", identity_hash="f" * 64)


def test_identity_wrong_package_binding_rejected(tmp_path):
    package_hash = _write_package(tmp_path / "deva", _fixture_package())
    identity = _fixture_identity("f" * 64)
    identity_hash = _write_identity(tmp_path / "deva", identity)
    resolved = preflight.resolve_s2v2_pre_heldout_identity(
        dev_a_artifact_root=tmp_path / "deva", identity_hash=identity_hash)
    assert resolved["calibration_package_hash"] == "f" * 64
    with pytest.raises(ExecutionError):
        preflight.verify_s2v2_devb_inputs(
            _read_package(tmp_path / "deva", package_hash), resolved)


def _read_package(root, package_hash):
    return json.loads(
        (root / "calibration_packages" / f"{package_hash}.json").read_text())


def test_identity_wrong_populations_rejected(tmp_path):
    package_hash = _write_package(tmp_path / "deva", _fixture_package())
    for key in ("dev_b_population_hash", "heldout_population_hash"):
        identity = dict(_fixture_identity(package_hash))
        identity[key] = "0" * 64
        identity_hash = digest(identity)
        _write(tmp_path / "deva" / "pre_heldout_identities"
               / f"{identity_hash}.json", identity)
        with pytest.raises(ExecutionError):
            preflight.resolve_s2v2_pre_heldout_identity(
                dev_a_artifact_root=tmp_path / "deva",
                identity_hash=identity_hash)


def test_identity_wrong_phase_rejected(tmp_path):
    package_hash = _write_package(tmp_path / "deva", _fixture_package())
    for phase in ({"calibration": "open", "dev_b": "not-evaluated",
                   "heldout": "unopened"},
                  {"calibration": "frozen", "dev_b": "evaluated",
                   "heldout": "unopened"},
                  {"calibration": "frozen", "dev_b": "not-evaluated",
                   "heldout": "opened"}):
        identity = dict(_fixture_identity(package_hash))
        identity["phase"] = phase
        identity_hash = digest(identity)
        _write(tmp_path / "deva" / "pre_heldout_identities"
               / f"{identity_hash}.json", identity)
        with pytest.raises(ExecutionError):
            preflight.resolve_s2v2_pre_heldout_identity(
                dev_a_artifact_root=tmp_path / "deva",
                identity_hash=identity_hash)


def test_cross_binding_mismatch_rejected(tmp_path):
    _write_package(tmp_path / "deva", _fixture_package())
    package = _fixture_package()
    identity = _fixture_identity("f" * 64)
    with pytest.raises(ExecutionError):
        preflight.verify_s2v2_devb_inputs(package, identity)


def test_cross_binding_accepts(tmp_path):
    package = _fixture_package()
    identity = _fixture_identity(digest(package))
    verified = preflight.verify_s2v2_devb_inputs(package, identity)
    assert verified["package_hash"] == digest(package)
    assert verified["identity_hash"] == digest(identity)
    assert verified["q_hat"] == Q_HAT
    assert verified["dev_b_population_hash"] == pop.S2V2_DEV_B_HASH
    assert verified["preflight"] == "INPUTS-VERIFIED"


def test_preflight_pins_frozen_hashes():
    source = inspect.getsource(preflight.preflight_s2v2_dev_b)
    assert "S2V2_FROZEN_PACKAGE_HASH" in source
    assert "S2V2_FROZEN_IDENTITY_HASH" in source


def test_absent_target_root_passes(tmp_path):
    store_root = tmp_path / "store"
    artifact_root = tmp_path / "artifacts"
    assert preflight.check_devb_target_root_empty(
        store_root=store_root, artifact_root=artifact_root) is None
    assert not store_root.exists()
    assert not artifact_root.exists()


def test_empty_target_directories_pass(tmp_path):
    store_root = tmp_path / "store"
    artifact_root = tmp_path / "artifacts"
    (store_root / "calibration_replicates").mkdir(parents=True)
    (artifact_root / "estimator_results").mkdir(parents=True)
    assert preflight.check_devb_target_root_empty(
        store_root=store_root, artifact_root=artifact_root) is None
    assert list(store_root.rglob("*")) == [store_root / "calibration_replicates"]
    assert list(artifact_root.rglob("*")) == [artifact_root / "estimator_results"]


def test_devb_manifest_refuses(tmp_path):
    _write(tmp_path / "store" / "calibration_replicates" / "m.json",
           {"replicate_id": "s2v2-dev-b-001", "seed": 364})
    with pytest.raises(ExecutionError):
        preflight.check_devb_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")


def test_devb_evaluation_refuses(tmp_path):
    _write(tmp_path / "artifacts" / preflight.DEV_B_EVALUATION_DIR / "e.json",
           {"replicate_id": "s2v2-dev-b-001"})
    with pytest.raises(ExecutionError):
        preflight.check_devb_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")


def test_devb_summary_refuses(tmp_path):
    _write(tmp_path / "artifacts" / preflight.DEV_B_SUMMARY_DIR / "s.json",
           {"n_covered": 100})
    with pytest.raises(ExecutionError):
        preflight.check_devb_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")


def test_unrelated_file_refuses(tmp_path):
    _write(tmp_path / "store" / "calibration_replicates" / "other.json",
           {"note": "unrelated file in a scanned namespace"})
    with pytest.raises(ExecutionError):
        preflight.check_devb_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")


def test_failed_preflight_adds_no_files(tmp_path):
    # Populate then fail: file set after failure equals file set before it.
    _write(tmp_path / "store" / "calibration_replicates" / "m.json",
           {"replicate_id": "s2v2-dev-b-001", "seed": 364})
    before = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    with pytest.raises(ExecutionError):
        preflight.check_devb_target_root_empty(
            store_root=tmp_path / "store", artifact_root=tmp_path / "artifacts")
    after = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*"))
    assert after == before


def test_cli_options_exact():
    actions = set()
    original = __import__("argparse").ArgumentParser.add_argument

    def spy(self, *names, **kwargs):
        actions.update(names)
        return original(self, *names, **kwargs)

    import argparse
    argparse.ArgumentParser.add_argument = spy
    try:
        preflight.main(["--help"])
    except SystemExit:
        pass
    finally:
        argparse.ArgumentParser.add_argument = original
    assert actions == {"--dev-a-artifact-root", "--store-root",
                       "--artifact-root", "--code-revision",
                       "--preflight-only", "--materialize-only",
                       "--estimate-only", "--evaluate-only", "-h", "--help"}


def test_cli_refuses_non_preflight(tmp_path):
    with pytest.raises(SystemExit):
        preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                        "--store-root", str(tmp_path / "store"),
                        "--artifact-root", str(tmp_path / "artifacts"),
                        "--code-revision", "rev"])


def test_no_execution_imports():
    text = Path(preflight.__file__).read_text()
    for marker in ("build_s2v2_devb_summary",
                   "binomial_interval", "QualificationRecord", "Uncertainty("):
        assert marker not in text, marker
    assert "estimate_calibration_replicate" in text
    assert "build_s2v2_devb_evaluation" in text


def _mutated_package(tmp_path, **overrides):
    package = _fixture_package()
    package = dict(package)
    package.update(overrides)
    package_hash = digest(package)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    return package_hash


def test_package_status_mutation_rejected(tmp_path):
    package_hash = _mutated_package(tmp_path, package_status="TAMPERED")
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_package_estimator_mutation_rejected(tmp_path):
    estimator = dict(_fixture_package()["estimator"])
    estimator["config_hash"] = "0" * 64
    package_hash = _mutated_package(tmp_path, estimator=estimator)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_package_truth_mutation_rejected(tmp_path):
    truth = dict(_fixture_package()["truth"])
    truth["value"] = {"D_m2_per_s": 2e-9}
    package_hash = _mutated_package(tmp_path, truth=truth)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_package_scope_mutation_rejected(tmp_path):
    scope = dict(_fixture_package()["scope"])
    scope["parameter_cell"] = "cell-b"
    package_hash = _mutated_package(tmp_path, scope=scope)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_package_generator_mutation_rejected(tmp_path):
    protocol = dict(_fixture_package()["generator_protocol"])
    protocol["version"] = "synthetic-v9"
    package_hash = _mutated_package(
        tmp_path, generator_protocol=protocol)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_package_revision_malformed_rejected(tmp_path):
    package = dict(_fixture_package())
    del package["code_revision"]
    package_hash = digest(package)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_calibration_package(
            dev_a_artifact_root=tmp_path / "deva", package_hash=package_hash)


def test_combined_population_mutation_rejected(tmp_path):
    package_hash = _write_package(tmp_path / "deva", _fixture_package())
    identity = dict(_fixture_identity(package_hash))
    identity["populations_hash"] = "0" * 64
    identity_hash = digest(identity)
    _write(tmp_path / "deva" / "pre_heldout_identities"
           / f"{identity_hash}.json", identity)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_pre_heldout_identity(
            dev_a_artifact_root=tmp_path / "deva",
            identity_hash=identity_hash)


def test_identity_revision_malformed_rejected(tmp_path):
    package_hash = _write_package(tmp_path / "deva", _fixture_package())
    identity = dict(_fixture_identity(package_hash))
    del identity["code_revision"]
    identity_hash = digest(identity)
    _write(tmp_path / "deva" / "pre_heldout_identities"
           / f"{identity_hash}.json", identity)
    with pytest.raises(ExecutionError):
        preflight.resolve_s2v2_pre_heldout_identity(
            dev_a_artifact_root=tmp_path / "deva",
            identity_hash=identity_hash)


def test_cross_revision_mismatch_rejected(tmp_path):
    package = _fixture_package()
    other = _fixture_identity(digest(package))
    other = dict(other)
    other["code_revision"] = "other-historical-revision"
    with pytest.raises(ExecutionError):
        preflight.verify_s2v2_devb_inputs(package, other)


def test_future_cli_revision_independent(tmp_path):
    package = _fixture_package()
    identity = _fixture_identity(digest(package))
    verified = preflight.verify_s2v2_devb_inputs(package, identity)
    assert verified["frozen_dev_a_code_revision"] == REVISION
    import inspect
    parameters = inspect.signature(
        preflight.verify_s2v2_devb_inputs).parameters
    assert "code_revision" not in parameters
    assert "frozen_dev_a_code_revision" in inspect.getsource(
        preflight.verify_s2v2_devb_inputs)
    assert '"code_revision": code_revision' in inspect.getsource(
        preflight.preflight_s2v2_dev_b)


def _s1_family(tmp_path):
    from rudeus.science.calibration_s1 import build_s1_plan_family
    from rudeus.science.calibration_store import CalibrationStore
    store = CalibrationStore(tmp_path / "store")
    return store, build_s1_plan_family(store)


def _write_fixture_evidence(store_root, artifact_root, revision, truth_hash,
                            skip=(), mutate=None):
    import hashlib

    from rudeus.science.contracts import canonical_bytes, digest
    store_root, artifact_root = Path(store_root), Path(artifact_root)
    for replicate_id in sorted(pop.S2V2_DEV_B_SEEDS):
        if replicate_id in skip:
            continue
        seed = pop.S2V2_DEV_B_SEEDS[replicate_id]
        payload = {"trajectory": replicate_id, "seed": seed}
        blob = canonical_bytes(payload)
        logical = digest(payload)
        (artifact_root / "blobs").mkdir(parents=True, exist_ok=True)
        (artifact_root / "blobs" / logical).write_bytes(blob)
        manifest = {"logical_hash": logical,
                    "raw_hash": hashlib.sha256(blob).hexdigest(),
                    "size_bytes": len(blob)}
        (artifact_root / "trajectory_manifests").mkdir(
            parents=True, exist_ok=True)
        _write(artifact_root / "trajectory_manifests" / (logical[:16] + ".json"),
               manifest)
        attempt = {"status": "COMPLETED", "exit_status": 0,
                   "environment": {"code_revision": revision}}
        record = {"replicate_id": replicate_id, "seed": seed,
                  "dataset_id": preflight.S2V2_DEV_B_DATASET_ID,
                  "split_assignment": "DEV",
                  "trajectory_artifact_hash": logical,
                  "truth_record_hash": truth_hash,
                  "conditions": {"code_revision": revision},
                  "execution_attempt_hash": None}
        if mutate is not None:
            mutate(replicate_id, record, attempt)
        attempt_hash = digest(attempt)
        (artifact_root / "attempts").mkdir(parents=True, exist_ok=True)
        _write(artifact_root / "attempts" / f"{attempt_hash}.json", attempt)
        record["execution_attempt_hash"] = attempt_hash
        (store_root / "calibration_replicates").mkdir(
            parents=True, exist_ok=True)
        _write(store_root / "calibration_replicates" / f"{replicate_id}.json",
               record)


def _completeness_kwargs(tmp_path, revision="mat-revision"):
    store, family = _s1_family(tmp_path)
    return {"store_root": tmp_path / "store",
            "artifact_root": tmp_path / "artifacts",
            "dataset_id": preflight.S2V2_DEV_B_DATASET_ID,
            "truth_hash": family["truth"],
            "code_revision": revision,
            "family_truth": family["truth"]}


def test_devb_plan_dataset_frozen(tmp_path):
    from rudeus.science.calibration import CalibrationPlan
    store, family = _s1_family(tmp_path)
    dataset_hash = preflight.build_s2v2_devb_dataset(store, family)
    plan = store.retrieve(
        CalibrationPlan,
        store.retrieve(
            __import__("rudeus.science.calibration", fromlist=[
                "CalibrationDatasetManifest"]).CalibrationDatasetManifest,
            dataset_hash).plan_hash)
    assert tuple(plan.dev_replicate_ids) == tuple(pop.S2V2_DEV_B_SEEDS)
    assert tuple(plan.heldout_replicate_ids) == ()
    from rudeus.science.calibration_s1 import S1_CODE_REVISION
    assert plan.code_revision == S1_CODE_REVISION
    dataset = store.retrieve(
        __import__("rudeus.science.calibration", fromlist=[
            "CalibrationDatasetManifest"]).CalibrationDatasetManifest,
        dataset_hash)
    assert dataset.dataset_id == preflight.S2V2_DEV_B_DATASET_ID
    assert tuple(dataset.attempted_replicate_ids) == tuple(pop.S2V2_DEV_B_SEEDS)
    assert tuple(dataset.trajectory_ids) == tuple(
        f"traj-{rep}" for rep in pop.S2V2_DEV_B_SEEDS)
    assert tuple(dataset.truth_record_hashes) == (family["truth"],)
    assert len(pop.S2V2_DEV_B_SEEDS) == 114
    assert pop.S2V2_DEV_B_SEEDS["s2v2-dev-b-001"] == 364
    assert pop.S2V2_DEV_B_SEEDS["s2v2-dev-b-114"] == 477


def test_devb_builders_hard_bound():
    text = Path(preflight.__file__).read_text()
    assert text.count("S2V2_DEV_B_SEEDS") >= 3
    assert "S2V2_DEV_A_SEEDS" not in text
    assert "HELDOUT_SEEDS" not in text


def test_completeness_accepts_114(tmp_path):
    kwargs = _completeness_kwargs(tmp_path)
    _write_fixture_evidence(kwargs["store_root"], kwargs["artifact_root"],
                            kwargs["code_revision"], kwargs["family_truth"])
    result = preflight.verify_devb_materialization_complete(
        store_root=kwargs["store_root"], artifact_root=kwargs["artifact_root"],
        dataset_id=kwargs["dataset_id"], truth_hash=kwargs["family_truth"],
        code_revision=kwargs["code_revision"])
    assert result["materialized"] == 114
    assert result["replicates"] == sorted(pop.S2V2_DEV_B_SEEDS)


def test_completeness_rejects_113(tmp_path):
    kwargs = _completeness_kwargs(tmp_path)
    _write_fixture_evidence(kwargs["store_root"], kwargs["artifact_root"],
                            kwargs["code_revision"], kwargs["family_truth"],
                            skip={"s2v2-dev-b-114"})
    with pytest.raises(ExecutionError):
        preflight.verify_devb_materialization_complete(
            store_root=kwargs["store_root"],
            artifact_root=kwargs["artifact_root"],
            dataset_id=kwargs["dataset_id"],
            truth_hash=kwargs["family_truth"],
            code_revision=kwargs["code_revision"])


def test_completeness_rejects_duplicate(tmp_path):
    kwargs = _completeness_kwargs(tmp_path)
    _write_fixture_evidence(kwargs["store_root"], kwargs["artifact_root"],
                            kwargs["code_revision"], kwargs["family_truth"])
    first = sorted(pop.S2V2_DEV_B_SEEDS)[0]
    _write(tmp_path / "store" / "calibration_replicates" / "dup.json",
           {"replicate_id": first, "seed": pop.S2V2_DEV_B_SEEDS[first]})
    with pytest.raises(ExecutionError):
        preflight.verify_devb_materialization_complete(
            store_root=kwargs["store_root"],
            artifact_root=kwargs["artifact_root"],
            dataset_id=kwargs["dataset_id"],
            truth_hash=kwargs["family_truth"],
            code_revision=kwargs["code_revision"])


def test_completeness_rejects_unexpected_id(tmp_path):
    kwargs = _completeness_kwargs(tmp_path)
    _write_fixture_evidence(kwargs["store_root"], kwargs["artifact_root"],
                            kwargs["code_revision"], kwargs["family_truth"])
    _write(tmp_path / "store" / "calibration_replicates" / "foreign.json",
           {"replicate_id": "s2v2-dev-a-001", "seed": 265})
    with pytest.raises(ExecutionError):
        preflight.verify_devb_materialization_complete(
            store_root=kwargs["store_root"],
            artifact_root=kwargs["artifact_root"],
            dataset_id=kwargs["dataset_id"],
            truth_hash=kwargs["family_truth"],
            code_revision=kwargs["code_revision"])


def test_completeness_rejects_wrong_seed(tmp_path):
    kwargs = _completeness_kwargs(tmp_path)

    def mutate(replicate_id, record, attempt):
        if replicate_id == "s2v2-dev-b-001":
            record["seed"] = 9999

    _write_fixture_evidence(kwargs["store_root"], kwargs["artifact_root"],
                            kwargs["code_revision"], kwargs["family_truth"],
                            mutate=mutate)
    with pytest.raises(ExecutionError):
        preflight.verify_devb_materialization_complete(
            store_root=kwargs["store_root"],
            artifact_root=kwargs["artifact_root"],
            dataset_id=kwargs["dataset_id"],
            truth_hash=kwargs["family_truth"],
            code_revision=kwargs["code_revision"])


def test_completeness_rejects_wrong_revision(tmp_path):
    kwargs = _completeness_kwargs(tmp_path)

    def mutate(replicate_id, record, attempt):
        if replicate_id == "s2v2-dev-b-001":
            attempt["environment"] = {"code_revision": "other-revision"}

    _write_fixture_evidence(kwargs["store_root"], kwargs["artifact_root"],
                            kwargs["code_revision"], kwargs["family_truth"],
                            mutate=mutate)
    with pytest.raises(ExecutionError):
        preflight.verify_devb_materialization_complete(
            store_root=kwargs["store_root"],
            artifact_root=kwargs["artifact_root"],
            dataset_id=kwargs["dataset_id"],
            truth_hash=kwargs["family_truth"],
            code_revision=kwargs["code_revision"])


def test_completeness_rejects_missing_trajectory(tmp_path):
    kwargs = _completeness_kwargs(tmp_path)
    _write_fixture_evidence(kwargs["store_root"], kwargs["artifact_root"],
                            kwargs["code_revision"], kwargs["family_truth"])
    first_blob = next((tmp_path / "artifacts" / "blobs").iterdir())
    first_blob.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_materialization_complete(
            store_root=kwargs["store_root"],
            artifact_root=kwargs["artifact_root"],
            dataset_id=kwargs["dataset_id"],
            truth_hash=kwargs["family_truth"],
            code_revision=kwargs["code_revision"])


def test_completeness_rejects_failed_attempt(tmp_path):
    kwargs = _completeness_kwargs(tmp_path)

    def mutate(replicate_id, record, attempt):
        if replicate_id == "s2v2-dev-b-001":
            attempt["status"] = "FAILED"
            attempt["exit_status"] = 1

    _write_fixture_evidence(kwargs["store_root"], kwargs["artifact_root"],
                            kwargs["code_revision"], kwargs["family_truth"],
                            mutate=mutate)
    with pytest.raises(ExecutionError):
        preflight.verify_devb_materialization_complete(
            store_root=kwargs["store_root"],
            artifact_root=kwargs["artifact_root"],
            dataset_id=kwargs["dataset_id"],
            truth_hash=kwargs["family_truth"],
            code_revision=kwargs["code_revision"])


def test_materialize_orchestration_order(tmp_path, monkeypatch):
    calls = []
    store, family = _s1_family(tmp_path)

    def fake_preflight(**kwargs):
        calls.append("preflight")
        assert kwargs["code_revision"] == "orch-revision"
        return {"package_hash": "p" * 64}

    def fake_materialize(**kwargs):
        calls.append("materialize")
        assert calls[0] == "preflight"
        assert kwargs["code_revision"] == "orch-revision"
        assert kwargs["seeds"] == dict(pop.S2V2_DEV_B_SEEDS)
        assert len(kwargs["seeds"]) == 114
        _write_fixture_evidence(tmp_path / "store", tmp_path / "artifacts",
                                "orch-revision", family["truth"])
        return {"failed": [], "succeeded": sorted(pop.S2V2_DEV_B_SEEDS)}

    monkeypatch.setattr(preflight, "preflight_s2v2_dev_b", fake_preflight)
    monkeypatch.setattr(
        preflight, "materialize_calibration_dataset", fake_materialize)
    summary = preflight.run_s2v2_dev_b_materialize(
        dev_a_artifact_root=tmp_path / "deva",
        store_root=tmp_path / "store", artifact_root=tmp_path / "artifacts",
        code_revision="orch-revision")
    assert calls[0] == "preflight"
    assert calls.count("materialize") == 1
    assert summary["requested"] == 114
    assert summary["materialized"] == 114
    assert summary["package_hash"] == "p" * 64
    assert summary["failures"] == []


def test_materialize_only_cli_dispatch(tmp_path, monkeypatch):
    calls = []
    original = preflight.run_s2v2_dev_b_materialize

    def fake(**kwargs):
        calls.append(kwargs)
        return {"materialized": 114}

    monkeypatch.setattr(
        preflight, "run_s2v2_dev_b_materialize", fake)
    preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                    "--store-root", str(tmp_path / "store"),
                    "--artifact-root", str(tmp_path / "artifacts"),
                    "--code-revision", "cli-rev", "--materialize-only"])
    assert len(calls) == 1
    assert calls[0]["code_revision"] == "cli-rev"
    assert calls[0]["store_root"] == str(tmp_path / "store")
    assert calls[0]["artifact_root"] == str(tmp_path / "artifacts")
    assert calls[0]["dev_a_artifact_root"] == str(tmp_path / "deva")
    monkeypatch.setattr(
        preflight, "run_s2v2_dev_b_materialize", original)


def test_full_run_without_mode_refuses(tmp_path):
    with pytest.raises(SystemExit):
        preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                        "--store-root", str(tmp_path / "store"),
                        "--artifact-root", str(tmp_path / "artifacts"),
                        "--code-revision", "rev"])


def test_exclusive_modes_refuse(tmp_path):
    with pytest.raises(SystemExit):
        preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                        "--store-root", str(tmp_path / "store"),
                        "--artifact-root", str(tmp_path / "artifacts"),
                        "--code-revision", "rev", "--preflight-only",
                        "--materialize-only"])


def test_no_evaluation_execution_path():
    text = Path(preflight.__file__).read_text()
    for marker in ("build_s2v2_devb_summary",
                   "binomial_interval", "evaluate_heldout", "HeldoutEvaluation",
                   "QualificationRecord"):
        assert marker not in text, marker
    assert "estimate_calibration_replicate" in text
    assert "build_s2v2_devb_evaluation" in text


def _estimator_payload(replicate_id, manifest_hash, revision, estimate=1.05e-9):
    return {"replicate_id": replicate_id,
            "replicate_manifest_hash": manifest_hash,
            "truth_record_hash": "t" * 64,
            "estimator": "analyze_trajectory",
            "estimator_module": "rudeus.science.transport",
            "estimator_config": {"lag_steps": [1, 2],
                                 "fit_window_ps": [0.5, 2.5],
                                 "selected_species": ["Li"],
                                 "volume_A3": 1000.0, "temperature_K": 550.0,
                                 "reference_frame": "simulation_cell",
                                 "charge_numbers": None},
            "code_revision": revision,
            "result": {"self_diffusion_by_species": {
                "Li": {"D_m2_per_s": estimate}}}}


def _write_estimator(root, payload):
    from rudeus.science.contracts import digest as content_digest
    estimator_hash = content_digest(payload)
    _write(root / "estimator_results" / f"{estimator_hash}.json", payload)
    return estimator_hash


def test_resolve_by_returned_hash(tmp_path):
    root = tmp_path / "artifacts"
    payload = _estimator_payload("s2v2-dev-b-010", "m" * 64, "rev-hash")
    estimator_hash = _write_estimator(root, payload)
    assert estimator_hash != "m" * 64
    resolved = preflight.resolve_devb_estimator_result(root, estimator_hash)
    assert resolved == payload
    text = Path(preflight.__file__).read_text()
    assert "find_estimator" not in text
    assert "by_manifest" not in text


def test_resolve_missing_file_rejected(tmp_path):
    with pytest.raises(ExecutionError):
        preflight.resolve_devb_estimator_result(
            tmp_path / "artifacts", "e" * 64)


def test_resolve_malformed_file_rejected(tmp_path):
    _write(tmp_path / "artifacts" / "estimator_results" / ("e" * 64 + ".json"),
           "{not json")
    with pytest.raises(ExecutionError):
        preflight.resolve_devb_estimator_result(
            tmp_path / "artifacts", "e" * 64)


def test_resolve_digest_mismatch_rejected(tmp_path):
    payload = _estimator_payload("s2v2-dev-b-010", "m" * 64, "rev-digest")
    _write(tmp_path / "artifacts" / "estimator_results" / ("f" * 64 + ".json"),
           payload)
    with pytest.raises(ExecutionError):
        preflight.resolve_devb_estimator_result(
            tmp_path / "artifacts", "f" * 64)


def test_estimator_semantics_accept(tmp_path):
    store, truth_hash = _s1_truth(tmp_path)
    payload = _estimator_payload("s2v2-dev-b-010", "m" * 64, "rev-sem")
    payload["truth_record_hash"] = truth_hash
    estimate = preflight.verify_devb_estimator_result(
        payload, replicate_id="s2v2-dev-b-010", manifest_hash="m" * 64,
        truth_hash=truth_hash,
        expected_config=dict(preflight.S2V2_EXPECTED_ESTIMATOR_CONFIG),
        code_revision="rev-sem")
    assert estimate == 1.05e-9


def _s1_truth(tmp_path):
    store, family = _s1_family(tmp_path)
    return store, family["truth"]


def test_estimator_wrong_manifest_rejected():
    payload = _estimator_payload("s2v2-dev-b-010", "m" * 64, "rev-man")
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_result(
            payload, replicate_id="s2v2-dev-b-010", manifest_hash="0" * 64,
            truth_hash="t" * 64,
            expected_config=dict(preflight.S2V2_EXPECTED_ESTIMATOR_CONFIG),
            code_revision="rev-man")


def test_estimator_wrong_name_rejected():
    payload = dict(_estimator_payload("s2v2-dev-b-010", "m" * 64, "rev-name"))
    payload["estimator"] = "other_estimator"
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_result(
            payload, replicate_id="s2v2-dev-b-010", manifest_hash="m" * 64,
            truth_hash="t" * 64,
            expected_config=dict(preflight.S2V2_EXPECTED_ESTIMATOR_CONFIG),
            code_revision="rev-name")


def test_estimator_result_wrong_module_rejected():
    payload = dict(_estimator_payload("s2v2-dev-b-010", "m" * 64, "rev-mod"))
    payload["estimator_module"] = "other.implementation"
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_result(
            payload, replicate_id="s2v2-dev-b-010", manifest_hash="m" * 64,
            truth_hash="t" * 64,
            expected_config=dict(preflight.S2V2_EXPECTED_ESTIMATOR_CONFIG),
            code_revision="rev-mod")


def test_estimator_wrong_config_rejected():
    payload = dict(_estimator_payload("s2v2-dev-b-010", "m" * 64, "rev-cfg"))
    config = dict(payload["estimator_config"])
    config["lag_steps"] = [1, 3]
    payload["estimator_config"] = config
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_result(
            payload, replicate_id="s2v2-dev-b-010", manifest_hash="m" * 64,
            truth_hash="t" * 64,
            expected_config=dict(preflight.S2V2_EXPECTED_ESTIMATOR_CONFIG),
            code_revision="rev-cfg")


def test_estimator_wrong_revision_rejected():
    payload = _estimator_payload("s2v2-dev-b-010", "m" * 64, "rev-old")
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_result(
            payload, replicate_id="s2v2-dev-b-010", manifest_hash="m" * 64,
            truth_hash="t" * 64,
            expected_config=dict(preflight.S2V2_EXPECTED_ESTIMATOR_CONFIG),
            code_revision="rev-new")


def test_estimator_nonfinite_rejected():
    for bad in (float("nan"), float("inf"), "1e-9", True, None):
        payload = dict(_estimator_payload("s2v2-dev-b-010", "m" * 64, "rev-f"))
        payload["result"] = {"self_diffusion_by_species": {
            "Li": {"D_m2_per_s": bad}}}
        with pytest.raises(ExecutionError):
            preflight.verify_devb_estimator_result(
                payload, replicate_id="s2v2-dev-b-010",
                manifest_hash="m" * 64, truth_hash="t" * 64,
                expected_config=dict(preflight.S2V2_EXPECTED_ESTIMATOR_CONFIG),
                code_revision="rev-f")


def test_truth_mapping_shape_accepted(tmp_path):
    store, truth_hash = _s1_truth(tmp_path)
    assert preflight.verify_devb_truth_value(
        store, truth_hash, truth_hash) == 1e-9


def test_truth_wrong_hash_rejected(tmp_path):
    store, family = _s1_family(tmp_path)
    with pytest.raises(ExecutionError):
        preflight.verify_devb_truth_value(store, "0" * 64, family["truth"])


def test_truth_wrong_value_rejected(tmp_path):
    from rudeus.science.calibration import TruthRecord, TruthType
    from rudeus.science.calibration_store import CalibrationStore
    store = CalibrationStore(tmp_path / "store")
    alternate = TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.ANALYTICAL,
        value={"D_m2_per_s": 2e-9}, statistical_interpretation="ensemble",
        window_interpretation="long_time", cell_interpretation="bulk",
        code_revision="f" * 40)
    alternate_hash = store.store(alternate)
    with pytest.raises(ExecutionError):
        preflight.verify_devb_truth_value(
            store, alternate_hash, alternate_hash)


def test_truth_unknown_rejected(tmp_path):
    from rudeus.science.calibration import TruthRecord, TruthType
    from rudeus.science.calibration_store import CalibrationStore
    store = CalibrationStore(tmp_path / "store")
    empty = TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.UNKNOWN,
        value=None, unavailable_reason="no-truth-declared",
        code_revision="f" * 40)
    empty_hash = store.store(empty)
    with pytest.raises(ExecutionError):
        preflight.verify_devb_truth_value(store, empty_hash, empty_hash)


def _write_estimator_complete_evidence(store_root, artifact_root, revision,
                                       truth_hash):
    from rudeus.science.contracts import digest as content_digest
    hashes = {}
    for position, replicate_id in enumerate(sorted(pop.S2V2_DEV_B_SEEDS)):
        manifest = {"replicate_id": replicate_id,
                    "seed": pop.S2V2_DEV_B_SEEDS[replicate_id],
                    "dataset_id": preflight.S2V2_DEV_B_DATASET_ID,
                    "split_assignment": "DEV",
                    "trajectory_artifact_hash": "t" * 64,
                    "truth_record_hash": truth_hash,
                    "conditions": {"code_revision": revision},
                    "execution_attempt_hash": "e" * 64}
        manifest_hash = content_digest(manifest)
        _write(store_root / "calibration_replicates" / f"{manifest_hash}.json",
               manifest)
        payload = _estimator_payload(
            replicate_id, manifest_hash, revision,
            estimate=1e-9 + position * 1e-12)
        payload["truth_record_hash"] = truth_hash
        estimator_hash = content_digest(payload)
        _write(artifact_root / "estimator_results" / f"{estimator_hash}.json",
               payload)
        hashes[replicate_id] = (manifest_hash, estimator_hash)
    return hashes


def _estimator_hashes_only(artifact_root):
    hashes = {}
    for path in sorted((artifact_root / "estimator_results").glob("*.json")):
        record = json.loads(path.read_text())
        if record.get("replicate_id") in pop.S2V2_DEV_B_SEEDS:
            hashes[record["replicate_id"]] = path.stem
    return hashes


def test_estimator_complete_114(tmp_path):
    store, truth_hash = _s1_truth(tmp_path)
    mapping = _write_estimator_complete_evidence(
        tmp_path / "store", tmp_path / "artifacts", "rev114", truth_hash)
    hashes = {rep: est for rep, (man, est) in mapping.items()}
    result = preflight.verify_devb_estimator_complete(
        store_root=tmp_path / "store", artifact_root=tmp_path / "artifacts",
        estimator_hashes=hashes,
        dataset_id=preflight.S2V2_DEV_B_DATASET_ID,
        truth_hash=truth_hash, code_revision="rev114")
    assert result["estimated"] == 114
    assert result["replicates"] == sorted(pop.S2V2_DEV_B_SEEDS)


def test_estimator_complete_113_rejected(tmp_path):
    store, truth_hash = _s1_truth(tmp_path)
    mapping = _write_estimator_complete_evidence(
        tmp_path / "store", tmp_path / "artifacts", "rev113", truth_hash)
    first = sorted(pop.S2V2_DEV_B_SEEDS)[0]
    for path in (tmp_path / "artifacts" / "estimator_results").glob("*.json"):
        record = json.loads(path.read_text())
        if record.get("replicate_id") == first:
            path.unlink()
    hashes = {}
    for replicate_id in sorted(pop.S2V2_DEV_B_SEEDS)[1:]:
        for path in sorted(
                (tmp_path / "artifacts" / "estimator_results").glob("*.json")):
            record = json.loads(path.read_text())
            if record.get("replicate_id") == replicate_id:
                hashes[replicate_id] = path.stem
                break
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_complete(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts",
            estimator_hashes=hashes,
            dataset_id=preflight.S2V2_DEV_B_DATASET_ID,
            truth_hash=truth_hash, code_revision="rev113")


def test_estimator_complete_duplicate_rejected(tmp_path):
    store, truth_hash = _s1_truth_hash(tmp_path)
    _write_estimator_complete_evidence(
        tmp_path / "store", tmp_path / "artifacts", "revdup", truth_hash)
    payload = _estimator_payload("s2v2-dev-b-001", "z" * 64, "revdup")
    payload["truth_record_hash"] = truth_hash
    from rudeus.science.contracts import digest as content_digest
    _write(tmp_path / "artifacts" / "estimator_results"
           / f"{content_digest(payload)}.json", payload)
    hashes = {}
    for replicate_id in sorted(pop.S2V2_DEV_B_SEEDS):
        for path in sorted(
                (tmp_path / "artifacts" / "estimator_results").glob("*.json")):
            record = json.loads(path.read_text())
            if record.get("replicate_id") == replicate_id:
                hashes[replicate_id] = path.stem
                break
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_complete(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts",
            estimator_hashes=hashes,
            dataset_id=preflight.S2V2_DEV_B_DATASET_ID,
            truth_hash=truth_hash, code_revision="revdup")


def _s1_truth_hash(tmp_path):
    store, family = _s1_family(tmp_path)
    return store, family["truth"]


def test_estimator_complete_foreign_rejected(tmp_path):
    store, truth_hash = _s1_truth(tmp_path)
    _write_estimator_complete_evidence(
        tmp_path / "store", tmp_path / "artifacts", "revfor", truth_hash)
    payload = _estimator_payload("s2v2-dev-a-001", "m" * 64, "revfor")
    payload["truth_record_hash"] = truth_hash
    from rudeus.science.contracts import digest as content_digest
    _write(tmp_path / "artifacts" / "estimator_results"
           / f"{content_digest(payload)}.json", payload)
    hashes = {}
    for replicate_id in sorted(pop.S2V2_DEV_B_SEEDS):
        for path in sorted(
                (tmp_path / "artifacts" / "estimator_results").glob("*.json")):
            record = json.loads(path.read_text())
            if record.get("replicate_id") == replicate_id:
                hashes[replicate_id] = path.stem
                break
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_complete(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts",
            estimator_hashes=hashes,
            dataset_id=preflight.S2V2_DEV_B_DATASET_ID,
            truth_hash=truth_hash, code_revision="revfor")


def test_estimator_complete_wrong_manifest_rejected(tmp_path):
    store, truth_hash = _s1_truth(tmp_path)
    _write_estimator_complete_evidence(
        tmp_path / "store", tmp_path / "artifacts", "revman", truth_hash)
    from rudeus.science.contracts import digest as content_digest
    payload = _estimator_payload("s2v2-dev-b-001", "0" * 64, "revman")
    payload["truth_record_hash"] = truth_hash
    other_hash = content_digest(payload)
    _write(tmp_path / "artifacts" / "estimator_results" / f"{other_hash}.json",
           payload)
    hashes = {}
    for replicate_id in sorted(pop.S2V2_DEV_B_SEEDS):
        if replicate_id == "s2v2-dev-b-001":
            hashes[replicate_id] = other_hash
            continue
        for path in sorted(
                (tmp_path / "artifacts" / "estimator_results").glob("*.json")):
            record = json.loads(path.read_text())
            if record.get("replicate_id") == replicate_id:
                hashes[replicate_id] = path.stem
                break
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_complete(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts",
            estimator_hashes=hashes,
            dataset_id=preflight.S2V2_DEV_B_DATASET_ID,
            truth_hash=truth_hash, code_revision="revman")


def _rewrite_estimator(tmp_path, replicate_id, transform):
    from rudeus.science.contracts import digest as content_digest
    for path in sorted(
            (tmp_path / "artifacts" / "estimator_results").glob("*.json")):
        record = json.loads(path.read_text())
        if record.get("replicate_id") == replicate_id:
            transform(record)
            new_hash = content_digest(record)
            _write(tmp_path / "artifacts" / "estimator_results"
                   / f"{new_hash}.json", record)
            path.unlink()
            return new_hash
    raise AssertionError("fixture estimator missing")


def _hashes_by_id(tmp_path):
    hashes = {}
    for path in sorted(
            (tmp_path / "artifacts" / "estimator_results").glob("*.json")):
        record = json.loads(path.read_text())
        if record.get("replicate_id") in pop.S2V2_DEV_B_SEEDS:
            hashes[record["replicate_id"]] = path.stem
    return hashes


def test_estimator_complete_wrong_config_rejected(tmp_path):
    store, truth_hash = _s1_truth(tmp_path)
    _write_estimator_complete_evidence(
        tmp_path / "store", tmp_path / "artifacts", "revcfg", truth_hash)

    def break_config(record):
        record["estimator_config"] = dict(
            record["estimator_config"], lag_steps=[1, 3])

    target = sorted(pop.S2V2_DEV_B_SEEDS)[0]
    new_hash = _rewrite_estimator(tmp_path, target, break_config)
    hashes = _hashes_by_id(tmp_path)
    assert hashes[target] == new_hash
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_complete(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts",
            estimator_hashes=hashes,
            dataset_id=preflight.S2V2_DEV_B_DATASET_ID,
            truth_hash=truth_hash, code_revision="revcfg")


def test_estimator_complete_wrong_revision_rejected(tmp_path):
    store, truth_hash = _s1_truth(tmp_path)
    _write_estimator_complete_evidence(
        tmp_path / "store", tmp_path / "artifacts", "revok", truth_hash)
    hashes = _hashes_by_id(tmp_path)
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_complete(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts",
            estimator_hashes=hashes,
            dataset_id=preflight.S2V2_DEV_B_DATASET_ID,
            truth_hash=truth_hash, code_revision="revother")


def test_estimator_complete_nonfinite_rejected(tmp_path):
    store, truth_hash = _s1_truth(tmp_path)
    _write_estimator_complete_evidence(
        tmp_path / "store", tmp_path / "artifacts", "revfin", truth_hash)

    def break_estimate(record):
        record["result"]["self_diffusion_by_species"]["Li"][
            "D_m2_per_s"] = float("inf")

    target = sorted(pop.S2V2_DEV_B_SEEDS)[0]
    for path in sorted(
            (tmp_path / "artifacts" / "estimator_results").glob("*.json")):
        record = json.loads(path.read_text())
        if record.get("replicate_id") == target:
            break_estimate(record)
            raw_path = (tmp_path / "artifacts" / "estimator_results"
                        / "nonfinite.json")
            raw_path.write_text(json.dumps(record, allow_nan=True))
            path.unlink()
    hashes = _hashes_by_id(tmp_path)
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_complete(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts",
            estimator_hashes=hashes,
            dataset_id=preflight.S2V2_DEV_B_DATASET_ID,
            truth_hash=truth_hash, code_revision="revfin")


def test_estimate_orchestration_order(tmp_path, monkeypatch):
    calls = []
    store, family = _s1_family(tmp_path)

    def fake_preflight(**kwargs):
        calls.append("preflight")
        return {"package_hash": "p" * 64}

    def fake_materialize(**kwargs):
        calls.append("materialize")
        assert calls[0] == "preflight"
        assert kwargs["code_revision"] == "orch-revision"
        assert kwargs["seeds"] == dict(pop.S2V2_DEV_B_SEEDS)
        return {"failed": [], "succeeded": sorted(pop.S2V2_DEV_B_SEEDS)}

    def fake_estimate(**kwargs):
        calls.append("estimate")
        assert "materialize" in calls
        manifest_hash = kwargs["replicate_manifest_hash"]
        replicate_id = None
        for manifest_path in sorted(
                (tmp_path / "store" / "calibration_replicates").glob("*.json")):
            record = json.loads(manifest_path.read_text())
            if manifest_path.stem == manifest_hash \
                    or digest(record) == manifest_hash:
                replicate_id = record["replicate_id"]
                break
        assert replicate_id in pop.S2V2_DEV_B_SEEDS
        payload = _estimator_payload(
            replicate_id, manifest_hash, "orch-revision")
        payload["truth_record_hash"] = family["truth"]
        from rudeus.science.contracts import digest as content_digest
        estimator_hash = content_digest(payload)
        _write(tmp_path / "artifacts" / "estimator_results"
               / f"{estimator_hash}.json", payload)
        return {"estimator_result_hash": estimator_hash,
                "replicate_manifest_hash": manifest_hash,
                "trajectory_artifact_hash": "t" * 64}

    monkeypatch.setattr(preflight, "preflight_s2v2_dev_b", fake_preflight)
    monkeypatch.setattr(
        preflight, "materialize_calibration_dataset", fake_materialize)
    monkeypatch.setattr(
        preflight, "estimate_calibration_replicate", fake_estimate)
    monkeypatch.setattr(
        preflight, "build_s1_plan_family", lambda store: family)
    _write_fixture_evidence(tmp_path / "store", tmp_path / "artifacts",
                            "orch-revision", family["truth"])
    summary = preflight.run_s2v2_dev_b_estimate(
        dev_a_artifact_root=tmp_path / "deva",
        store_root=tmp_path / "store", artifact_root=tmp_path / "artifacts",
        code_revision="orch-revision")
    assert calls[0] == "preflight"
    assert calls.count("materialize") == 1
    assert calls.count("estimate") == 114
    assert summary["requested"] == 114
    assert summary["estimated"] == 114
    assert summary["failures"] == []


def test_estimate_only_cli_dispatch(tmp_path, monkeypatch):
    calls = []
    original = preflight.run_s2v2_dev_b_estimate

    def fake(**kwargs):
        calls.append(kwargs)
        return {"estimated": 114}

    monkeypatch.setattr(preflight, "run_s2v2_dev_b_estimate", fake)
    preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                    "--store-root", str(tmp_path / "store"),
                    "--artifact-root", str(tmp_path / "artifacts"),
                    "--code-revision", "cli-rev", "--estimate-only"])
    assert len(calls) == 1
    assert calls[0]["code_revision"] == "cli-rev"
    assert calls[0]["store_root"] == str(tmp_path / "store")
    assert calls[0]["artifact_root"] == str(tmp_path / "artifacts")
    assert calls[0]["dev_a_artifact_root"] == str(tmp_path / "deva")
    monkeypatch.setattr(preflight, "run_s2v2_dev_b_estimate", original)


def test_three_modes_refuse(tmp_path):
    with pytest.raises(SystemExit):
        preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                        "--store-root", str(tmp_path / "store"),
                        "--artifact-root", str(tmp_path / "artifacts"),
                        "--code-revision", "rev", "--preflight-only",
                        "--materialize-only", "--estimate-only"])


# ---------------------------------------------------------------------------
# S2 v2 DEV-B evaluation persistence slice (fixture/tmp-only).
# ---------------------------------------------------------------------------

EVAL_PACKAGE = "a" * 64
EVAL_Q_HAT = Q_HAT
EVAL_REVISION = "devb-eval-fixture-revision"


def _eval_setup(tmp_path, revision=EVAL_REVISION):
    store, family = _s1_family(tmp_path)
    truth_hash = family["truth"]
    mapping = _write_estimator_complete_evidence(
        tmp_path / "store", tmp_path / "artifacts", revision, truth_hash)
    estimator_hashes = {rep: est for rep, (man, est) in mapping.items()}
    manifest_hashes = {rep: man for rep, (man, est) in mapping.items()}
    return store, family, truth_hash, estimator_hashes, manifest_hashes


def _eval_kwargs(tmp_path, estimator_hashes, truth_hash,
                 revision=EVAL_REVISION, package=EVAL_PACKAGE, q_hat=EVAL_Q_HAT):
    return {"store_root": tmp_path / "store",
            "artifact_root": tmp_path / "artifacts",
            "estimator_hashes": dict(estimator_hashes),
            "dataset_id": preflight.S2V2_DEV_B_DATASET_ID,
            "truth_hash": truth_hash, "code_revision": revision,
            "calibration_package_hash": package, "q_hat": q_hat}


def _eval_files(tmp_path):
    directory = tmp_path / "artifacts" / preflight.DEV_B_EVALUATION_DIR
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"))


def _read_eval(path):
    return json.loads(Path(path).read_text())


def test_evaluation_persist_valid_at_digest_filename(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    result = preflight.persist_devb_evaluations(
        **_eval_kwargs(tmp_path, estimator_hashes, truth_hash))
    assert result["evaluated"] == 114
    files = _eval_files(tmp_path)
    assert len(files) == 114
    for path in files:
        assert len(path.stem) == 64
        record = _read_eval(path)
        assert digest(record) == path.stem


def test_evaluation_reread_equals_builder_output(tmp_path):
    from rudeus.science.calibration_s2v2 import S2V2_METHOD_HASH
    from rudeus.science.calibration_s2v2_devb import build_s2v2_devb_evaluation
    _, _, truth_hash, estimator_hashes, manifest_hashes = _eval_setup(tmp_path)
    preflight.persist_devb_evaluations(
        **_eval_kwargs(tmp_path, estimator_hashes, truth_hash))
    for path in _eval_files(tmp_path):
        persisted = _read_eval(path)
        replicate_id = persisted["replicate_id"]
        estimator = json.loads(
            (tmp_path / "artifacts" / "estimator_results"
             / f"{estimator_hashes[replicate_id]}.json").read_text())
        estimate = estimator["result"]["self_diffusion_by_species"]["Li"][
            "D_m2_per_s"]
        expected = build_s2v2_devb_evaluation(
            replicate_id=replicate_id,
            replicate_manifest_hash=manifest_hashes[replicate_id],
            estimator_result_hash=estimator_hashes[replicate_id],
            truth_record_hash=truth_hash,
            estimate_D=estimate, truth_D=1.0e-9,
            calibration_package_hash=EVAL_PACKAGE, q_hat=EVAL_Q_HAT,
            method_hash=S2V2_METHOD_HASH,
            population_hash=pop.S2V2_DEV_B_HASH,
            code_revision=EVAL_REVISION)
        assert persisted == expected


def test_evaluation_missing_file_rejected(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    _eval_files(tmp_path)[0].unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_evaluation_malformed_file_rejected(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    target.write_text("{not json")
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_evaluation_digest_mismatch_rejected(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    record = _read_eval(target)
    record["covered"] = not record["covered"]
    target.write_text(json.dumps(record))
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_evaluation_wrong_filename_rejected(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    files = _eval_files(tmp_path)
    first = files[0]
    record = _read_eval(first)
    wrong = first.parent / ("f" * 64 + ".json")
    wrong.write_text(json.dumps(record))
    first.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def _tamper_binding(tmp_path, field, value):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    record = _read_eval(target)
    record[field] = value
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_binding_manifest_hash_refuses(tmp_path):
    _tamper_binding(tmp_path, "replicate_manifest_hash", "0" * 64)


def test_binding_estimator_hash_refuses(tmp_path):
    _tamper_binding(tmp_path, "estimator_result_hash", "1" * 64)


def test_binding_truth_hash_refuses(tmp_path):
    _tamper_binding(tmp_path, "truth_record_hash", "2" * 64)


def test_binding_package_hash_refuses(tmp_path):
    _tamper_binding(tmp_path, "calibration_package_hash", "3" * 64)


def test_binding_q_hat_refuses(tmp_path):
    _tamper_binding(tmp_path, "q_hat", EVAL_Q_HAT * 2)


def test_binding_method_hash_refuses(tmp_path):
    _tamper_binding(tmp_path, "method_hash", "4" * 64)


def test_binding_population_hash_refuses(tmp_path):
    _tamper_binding(tmp_path, "population_hash", "5" * 64)


def test_binding_revision_refuses(tmp_path):
    _tamper_binding(tmp_path, "code_revision", "other-revision")


def _tamper_derived(tmp_path, field, value):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    record = _read_eval(target)
    record[field] = value
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_replay_interval_lower_refuses(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    record = _read_eval(target)
    record["interval_lower"] = record["interval_lower"] + 1e-12
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_replay_interval_upper_refuses(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    record = _read_eval(target)
    record["interval_upper"] = record["interval_upper"] + 1e-12
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_replay_covered_refuses(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    record = _read_eval(target)
    record["covered"] = not record["covered"]
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_replay_signed_error_refuses(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    record = _read_eval(target)
    record["signed_error"] = record["signed_error"] + 1e-12
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_replay_absolute_error_refuses(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    record = _read_eval(target)
    record["absolute_error"] = record["absolute_error"] + 1e-12
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_population_114_accepted(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    result = preflight.verify_devb_evaluation_complete(**kwargs)
    assert result["evaluated"] == 114
    assert result["replicates"] == sorted(pop.S2V2_DEV_B_SEEDS)


def test_population_113_rejected(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    _eval_files(tmp_path)[0].unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_population_duplicate_rejected(tmp_path):
    from rudeus.science.contracts import digest as content_digest
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    record = _read_eval(_eval_files(tmp_path)[0])
    record["estimator_result_hash"] = "6" * 64
    record["replicate_manifest_hash"] = "7" * 64
    record["truth_record_hash"] = "8" * 64
    record["calibration_package_hash"] = "9" * 64
    duplicate = _eval_files(tmp_path)[0].parent / (
        content_digest(record) + ".json")
    duplicate.write_text(json.dumps(record))
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_population_foreign_deva_rejected(tmp_path):
    from rudeus.science.contracts import digest as content_digest
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    intruder = _read_eval(_eval_files(tmp_path)[0])
    intruder["replicate_id"] = "s2v2-dev-a-001"
    foreign = _eval_files(tmp_path)[0].parent / (
        content_digest(intruder) + ".json")
    foreign.write_text(json.dumps(intruder))
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_population_foreign_heldout_rejected(tmp_path):
    from rudeus.science.contracts import digest as content_digest
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    heldout_id = sorted(pop.S2V2_HELDOUT_SEEDS)[0]
    assert heldout_id not in pop.S2V2_DEV_B_SEEDS
    intruder = _read_eval(_eval_files(tmp_path)[0])
    intruder["replicate_id"] = heldout_id
    foreign = _eval_files(tmp_path)[0].parent / (
        content_digest(intruder) + ".json")
    foreign.write_text(json.dumps(intruder))
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_population_arbitrary_id_rejected(tmp_path):
    from rudeus.science.contracts import digest as content_digest
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    intruder = _read_eval(_eval_files(tmp_path)[0])
    intruder["replicate_id"] = "arbitrary-id-001"
    foreign = _eval_files(tmp_path)[0].parent / (
        content_digest(intruder) + ".json")
    foreign.write_text(json.dumps(intruder))
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_q_hat_matches_package_value(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    for path in _eval_files(tmp_path):
        assert _read_eval(path)["q_hat"] == EVAL_Q_HAT
    result = preflight.verify_devb_evaluation_complete(**kwargs)
    assert result["evaluated"] == 114


def test_q_hat_mismatch_refuses(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    preflight.persist_devb_evaluations(**kwargs)
    target = _eval_files(tmp_path)[0]
    record = _read_eval(target)
    record["q_hat"] = EVAL_Q_HAT * 3
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    with pytest.raises(ExecutionError):
        preflight.verify_devb_evaluation_complete(**kwargs)


def test_runner_uses_no_qhat_learning(tmp_path):
    text = Path(preflight.__file__).read_text()
    assert "build_s2v2_devb_evaluation" in text
    for marker in ("order_statistic", "np.quantile",
                   "statistics.quantiles"):
        assert marker not in text, marker
    assert "q_hat" in text


def test_runner_reimplements_no_formulas():
    text = Path(preflight.__file__).read_text()
    for marker in ("signed_error", "absolute_error", "interval_lower",
                   "interval_upper"):
        assert marker not in text, marker


def test_no_summary_path():
    text = Path(preflight.__file__).read_text()
    for marker in ("build_s2v2_devb_summary", "binomial_interval",
                   "QualificationRecord", "mean_signed_error",
                   "mean_absolute_error", "coverage_ci"):
        assert marker not in text, marker


def test_evaluation_blocks_rerun_preflight(tmp_path):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    preflight.persist_devb_evaluations(
        **_eval_kwargs(tmp_path, estimator_hashes, truth_hash))
    with pytest.raises(ExecutionError):
        preflight.check_devb_target_root_empty(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts")


def test_failed_estimator_completeness_writes_zero(tmp_path, monkeypatch):
    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    kwargs = _eval_kwargs(tmp_path, estimator_hashes, truth_hash)
    original = preflight.verify_devb_estimator_complete

    def failing(**call_kwargs):
        raise preflight.ExecutionError("forced estimator failure", "INTEGRITY")

    monkeypatch.setattr(
        preflight, "verify_devb_estimator_complete", failing)
    before = _eval_files(tmp_path)
    assert before == []
    with pytest.raises(ExecutionError):
        preflight.verify_devb_estimator_complete(
            store_root=tmp_path / "store",
            artifact_root=tmp_path / "artifacts",
            estimator_hashes=estimator_hashes,
            dataset_id=preflight.S2V2_DEV_B_DATASET_ID,
            truth_hash=truth_hash, code_revision=EVAL_REVISION)
    assert _eval_files(tmp_path) == []
    monkeypatch.setattr(
        preflight, "verify_devb_estimator_complete", original)


def test_builder_called_114_times(tmp_path, monkeypatch):
    import rudeus.science.run_s2v2_dev_b as runner
    calls = []
    original = runner.build_s2v2_devb_evaluation

    def counting(**kwargs):
        calls.append(kwargs["replicate_id"])
        return original(**kwargs)

    _, _, truth_hash, estimator_hashes, _ = _eval_setup(tmp_path)
    monkeypatch.setattr(runner, "build_s2v2_devb_evaluation", counting)
    preflight.persist_devb_evaluations(
        **_eval_kwargs(tmp_path, estimator_hashes, truth_hash))
    assert len(calls) == 114
    assert sorted(calls) == sorted(pop.S2V2_DEV_B_SEEDS)


def test_evaluate_ordering_estimator_before_write(tmp_path, monkeypatch):
    import rudeus.science.run_s2v2_dev_b as runner
    order = []
    original_verify = runner.verify_devb_estimator_complete
    original_persist = runner.persist_devb_evaluations

    def verify_spy(**kwargs):
        order.append("estimator-complete")
        return original_verify(**kwargs)

    def persist_spy(**kwargs):
        assert "estimator-complete" in order
        order.append("first-write")
        return original_persist(**kwargs)

    monkeypatch.setattr(runner, "verify_devb_estimator_complete", verify_spy)
    monkeypatch.setattr(runner, "persist_devb_evaluations", persist_spy)
    package = _fixture_package()
    package_hash = _write_package(tmp_path / "deva", package)
    identity = _fixture_identity(package_hash)
    _write_identity(tmp_path / "deva", identity)
    monkeypatch.setattr(runner, "S2V2_FROZEN_PACKAGE_HASH", package_hash)
    monkeypatch.setattr(
        runner, "S2V2_FROZEN_IDENTITY_HASH", digest(identity))
    summary = runner.run_s2v2_dev_b_evaluate(
        dev_a_artifact_root=tmp_path / "deva",
        store_root=tmp_path / "store", artifact_root=tmp_path / "artifacts",
        code_revision="order-rev")
    assert order[0] == "estimator-complete"
    assert order[1] == "first-write"
    assert summary["evaluated"] == 114


def test_evaluate_only_cli_dispatch(tmp_path, monkeypatch):
    calls = []
    original = preflight.run_s2v2_dev_b_evaluate

    def fake(**kwargs):
        calls.append(kwargs)
        return {"evaluated": 114}

    monkeypatch.setattr(preflight, "run_s2v2_dev_b_evaluate", fake)
    preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                    "--store-root", str(tmp_path / "store"),
                    "--artifact-root", str(tmp_path / "artifacts"),
                    "--code-revision", "cli-rev", "--evaluate-only"])
    assert len(calls) == 1
    assert calls[0]["code_revision"] == "cli-rev"
    assert calls[0]["store_root"] == str(tmp_path / "store")
    assert calls[0]["artifact_root"] == str(tmp_path / "artifacts")
    assert calls[0]["dev_a_artifact_root"] == str(tmp_path / "deva")
    monkeypatch.setattr(preflight, "run_s2v2_dev_b_evaluate", original)


def test_four_modes_exclusive_refuse(tmp_path):
    with pytest.raises(SystemExit):
        preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                        "--store-root", str(tmp_path / "store"),
                        "--artifact-root", str(tmp_path / "artifacts"),
                        "--code-revision", "rev", "--estimate-only",
                        "--evaluate-only"])
    with pytest.raises(SystemExit):
        preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                        "--store-root", str(tmp_path / "store"),
                        "--artifact-root", str(tmp_path / "artifacts"),
                        "--code-revision", "rev"])


def test_evaluate_produces_no_summary(tmp_path, monkeypatch):
    import rudeus.science.run_s2v2_dev_b as runner
    package = _fixture_package()
    package_hash = _write_package(tmp_path / "deva", package)
    identity = _fixture_identity(package_hash)
    _write_identity(tmp_path / "deva", identity)
    monkeypatch.setattr(runner, "S2V2_FROZEN_PACKAGE_HASH", package_hash)
    monkeypatch.setattr(
        runner, "S2V2_FROZEN_IDENTITY_HASH", digest(identity))
    summary = runner.run_s2v2_dev_b_evaluate(
        dev_a_artifact_root=tmp_path / "deva",
        store_root=tmp_path / "store", artifact_root=tmp_path / "artifacts",
        code_revision="nosum-rev")
    assert summary["evaluated"] == 114
    assert not (tmp_path / "artifacts" / preflight.DEV_B_SUMMARY_DIR).exists()
    assert "summary" not in {key.lower() for key in summary}
