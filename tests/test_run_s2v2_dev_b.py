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
                       "--preflight-only", "-h", "--help"}


def test_cli_refuses_non_preflight(tmp_path):
    with pytest.raises(SystemExit):
        preflight.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                        "--store-root", str(tmp_path / "store"),
                        "--artifact-root", str(tmp_path / "artifacts"),
                        "--code-revision", "rev"])


def test_no_execution_imports():
    text = Path(preflight.__file__).read_text()
    for marker in ("materialize_calibration_dataset",
                   "estimate_calibration_replicate",
                   "build_s2v2_devb_evaluation", "build_s2v2_devb_summary",
                   "binomial_interval", "QualificationRecord", "Uncertainty(",
                   "CalibrationStore"):
        assert marker not in text, marker


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
