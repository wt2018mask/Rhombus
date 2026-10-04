"""Focused tests for the S2 v2 pre-HELDOUT no-change gate (tmp only).

No real DEV-A/DEV-B root access, no DEV-B execution, no HELDOUT access or
execution. Fixture packages use the committed Stage-B freeze builder;
fixture DEV-B summaries use the committed pure DEV-B builders.
"""
import json
import os
from pathlib import Path
import subprocess

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science import calibration_s2v2_populations as pop
from rudeus.science import pre_heldout_no_change as gate
from rudeus.science import run_s2v2_dev_b as devb
from rudeus.science.calibration_s2v2 import S2V2_CRITERION_HASH, S2V2_METHOD_HASH
from rudeus.science.calibration_s2v2_devb import (
    build_s2v2_devb_evaluation,
    build_s2v2_devb_summary,
)
from rudeus.science.calibration_s2v2_stageb import (
    build_complete_pre_heldout_identity,
    build_s2v2_score_record,
    freeze_s2v2_calibration_package,
)
from rudeus.science.contracts import canonical_bytes, digest

TRUTH = 1.0e-9
Q_HAT = devb.S2V2_FROZEN_Q_HAT
REVISION = "no-change-fixture-revision"
SUMMARY_REVISION = "no-change-summary-fixture-revision"


@pytest.fixture(autouse=True)
def restore_frozen_test_pins():
    names = ("S2V2_FROZEN_PACKAGE_HASH", "S2V2_FROZEN_IDENTITY_HASH",
             "S2V2_FROZEN_DEV_B_SUMMARY_HASH",
             "S2V2_FROZEN_DEV_B_CODE_REVISION")
    original = {name: getattr(gate, name) for name in names}
    yield
    for name, value in original.items():
        setattr(gate, name, value)


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _dev_a_ids():
    return sorted(pop.S2V2_DEV_A_SEEDS)


def _fixture_package():
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
    package = freeze_s2v2_calibration_package(
        score_records=records, code_revision=REVISION)
    assert package["q_hat"] == Q_HAT
    return package


def _setup(tmp_path):
    """Write fixture package/identity/summary; return explicit hashes."""
    package = _fixture_package()
    package_hash = digest(package)
    _write(tmp_path / "deva" / "calibration_packages" / f"{package_hash}.json",
           package)
    identity = build_complete_pre_heldout_identity(
        calibration_package_hash=package_hash, code_revision=REVISION)
    identity_hash = digest(identity)
    _write(tmp_path / "deva" / "pre_heldout_identities" / f"{identity_hash}.json",
           identity)
    evaluations = []
    for position, replicate_id in enumerate(sorted(pop.S2V2_DEV_B_SEEDS)):
        suffix = "%x" % (position % 16)
        offset = (position - 57) * 1e-12
        evaluations.append(build_s2v2_devb_evaluation(
            replicate_id=replicate_id,
            replicate_manifest_hash="1" * 63 + suffix,
            estimator_result_hash="2" * 63 + suffix,
            truth_record_hash="3" * 64,
            estimate_D=TRUTH + offset, truth_D=TRUTH,
            calibration_package_hash=package_hash, q_hat=Q_HAT,
            code_revision=SUMMARY_REVISION))
    assert len(evaluations) == 114
    summary = build_s2v2_devb_summary(
        evaluation_records=evaluations,
        pre_heldout_identity_hash=identity_hash,
        calibration_package_hash=package_hash, q_hat=Q_HAT,
        code_revision=SUMMARY_REVISION)
    summary_hash = digest(summary)
    _write(tmp_path / "artifacts" / devb.DEV_B_SUMMARY_DIR / f"{summary_hash}.json",
           summary)
    # Gate constants are pinned to the production evidence. Substitute the
    # generated tmp-only fixture identities for each test, then restore them.
    gate.S2V2_FROZEN_PACKAGE_HASH = package_hash
    gate.S2V2_FROZEN_IDENTITY_HASH = identity_hash
    gate.S2V2_FROZEN_DEV_B_SUMMARY_HASH = summary_hash
    gate.S2V2_FROZEN_DEV_B_CODE_REVISION = SUMMARY_REVISION
    return {"package_hash": package_hash, "identity_hash": identity_hash,
            "summary_hash": summary_hash, "summary": summary}


def _kwargs(tmp_path, hashes):
    return {"dev_a_artifact_root": tmp_path / "deva",
            "artifact_root": tmp_path / "artifacts",
            "package_hash": hashes["package_hash"],
            "identity_hash": hashes["identity_hash"],
            "dev_b_summary_hash": hashes["summary_hash"]}


def _build_acknowledgment(hashes):
    return gate.build_pre_heldout_no_change(
        method_hash=S2V2_METHOD_HASH, criterion_hash=S2V2_CRITERION_HASH,
        dev_a_population_hash=pop.S2V2_DEV_A_HASH,
        dev_b_population_hash=pop.S2V2_DEV_B_HASH,
        heldout_population_hash=pop.S2V2_HELDOUT_HASH,
        populations_hash=pop.S2V2_POPULATIONS_HASH,
        calibration_package_hash=hashes["package_hash"],
        pre_heldout_identity_hash=hashes["identity_hash"], q_hat=Q_HAT,
        dev_b_summary_hash=hashes["summary_hash"],
        dev_b_summary_code_revision=SUMMARY_REVISION)


def _ack_files(tmp_path):
    directory = tmp_path / "artifacts" / gate.NO_CHANGE_DIR
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"))


def _read_ack(path):
    return json.loads(Path(path).read_text())


# --- creation / persistence / determinism -------------------------------

def test_valid_acknowledgment_creation(tmp_path):
    hashes = _setup(tmp_path)
    result = gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert result["acknowledged"] == 1
    assert len(result["acknowledgment_hash"]) == 64
    assert result["dev_b_summary_hash"] == hashes["summary_hash"]
    assert result["failures"] == []


def test_exact_digest_filename(tmp_path):
    hashes = _setup(tmp_path)
    result = gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    files = _ack_files(tmp_path)
    assert len(files) == 1
    assert files[0].stem == result["acknowledgment_hash"]
    assert digest(_read_ack(files[0])) == files[0].stem


def test_exact_reread_equals_builder_output(tmp_path):
    hashes = _setup(tmp_path)
    gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    persisted = _read_ack(_ack_files(tmp_path)[0])
    expected = _build_acknowledgment(hashes)
    assert persisted == expected
    assert persisted["decision"] == "NO-CHANGE"
    assert persisted["heldout_status"] == "UNOPENED"
    assert persisted["post_dev_b_tuning"] == "FORBIDDEN"
    assert persisted["dev_b_role"] == "DESCRIPTIVE-NON-QUALIFICATION"
    assert "verdict" not in persisted
    reverified = gate.verify_pre_heldout_no_change_complete(
        **_kwargs(tmp_path, hashes))
    assert reverified["acknowledgment_hash"] == digest(expected)


def test_deterministic_identity(tmp_path):
    hashes = _setup(tmp_path)
    first = gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    record_a = _build_acknowledgment(hashes)
    record_b = _build_acknowledgment(hashes)
    assert canonical_bytes(record_a) == canonical_bytes(record_b)
    assert digest(record_a) == digest(record_b) == first["acknowledgment_hash"]
    # A second persistence attempt is a duplicate and must refuse.
    record = _read_ack(_ack_files(tmp_path)[0])
    with pytest.raises(ExecutionError):
        gate.persist_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert first["acknowledgment_hash"] == digest(record)
    assert len(_ack_files(tmp_path)) == 1


def test_conflicting_acknowledgment_refused(tmp_path):
    hashes = _setup(tmp_path)
    record = _build_acknowledgment(hashes)
    conflicting = dict(record, decision="NO-CHANGE-OTHER")
    path = (tmp_path / "artifacts" / gate.NO_CHANGE_DIR
            / f"{digest(conflicting)}.json")
    _write(path, conflicting)
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert len(_ack_files(tmp_path)) == 1


def test_existing_empty_acknowledgment_namespace_refused(tmp_path):
    hashes = _setup(tmp_path)
    (tmp_path / "artifacts" / gate.NO_CHANGE_DIR).mkdir()
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert _ack_files(tmp_path) == []


def test_symlinked_acknowledgment_namespace_cannot_escape_root(tmp_path):
    hashes = _setup(tmp_path)
    artifact_root = tmp_path / "artifacts"
    namespace = artifact_root / gate.NO_CHANGE_DIR
    external = tmp_path / "outside-artifact-root"
    external.mkdir()

    try:
        os.symlink(external, namespace, target_is_directory=True)
    except (OSError, NotImplementedError) as symlink_error:
        if os.name != "nt":
            pytest.fail(f"could not create adversarial symlink fixture: {symlink_error}")
        # Directory junctions exercise the same path escape through a Windows
        # reparse point and generally do not require symlink privileges.
        junction = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(namespace), str(external)],
            capture_output=True, text=True, check=False)
        if junction.returncode != 0:
            pytest.fail(
                "could not create symlink or junction fixture; "
                f"symlink error={symlink_error}; junction error={junction.stderr or junction.stdout}"
            )

    assert namespace.is_symlink() or namespace.exists()
    with pytest.raises(ExecutionError, match="escapes root"):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert list(external.iterdir()) == []


def test_duplicate_acknowledgment_refused(tmp_path):
    hashes = _setup(tmp_path)
    gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert len(_ack_files(tmp_path)) == 1


# --- DEV-A input refusals -------------------------------------------------

def test_missing_package_refused(tmp_path):
    hashes = _setup(tmp_path)
    (tmp_path / "deva" / "calibration_packages").rename(
        tmp_path / "deva" / "calibration_packages_gone")
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert _ack_files(tmp_path) == []


def test_wrong_package_digest_refused(tmp_path):
    hashes = _setup(tmp_path)
    package = _fixture_package()
    package["estimator"] = dict(package["estimator"])
    package["estimator"]["name"] = "foreign-estimator"
    foreign_hash = digest(package)
    _write(tmp_path / "deva" / "calibration_packages" / f"{foreign_hash}.json",
           package)
    kwargs = _kwargs(tmp_path, hashes)
    kwargs["package_hash"] = foreign_hash
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**kwargs)
    assert _ack_files(tmp_path) == []


def test_missing_identity_refused(tmp_path):
    hashes = _setup(tmp_path)
    (tmp_path / "deva" / "pre_heldout_identities").rename(
        tmp_path / "deva" / "pre_heldout_identities_gone")
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert _ack_files(tmp_path) == []


def test_wrong_identity_refused(tmp_path):
    hashes = _setup(tmp_path)
    identity = build_complete_pre_heldout_identity(
        calibration_package_hash="0" * 64, code_revision=REVISION)
    foreign_hash = digest(identity)
    _write(tmp_path / "deva" / "pre_heldout_identities" / f"{foreign_hash}.json",
           identity)
    kwargs = _kwargs(tmp_path, hashes)
    kwargs["identity_hash"] = foreign_hash
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**kwargs)
    assert _ack_files(tmp_path) == []


# --- DEV-B summary refusals -------------------------------------------------

def test_missing_summary_refused(tmp_path):
    hashes = _setup(tmp_path)
    (tmp_path / "artifacts" / devb.DEV_B_SUMMARY_DIR).rename(
        tmp_path / "artifacts" / "dev_b_summaries_gone")
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert _ack_files(tmp_path) == []


def test_wrong_summary_digest_refused(tmp_path):
    hashes = _setup(tmp_path)
    target = tmp_path / "artifacts" / devb.DEV_B_SUMMARY_DIR / \
        f"{hashes['summary_hash']}.json"
    record = json.loads(target.read_text())
    record["n_covered"] = record["n_covered"] + 1
    target.write_text(json.dumps(record))
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert _ack_files(tmp_path) == []


def _tamper_summary(tmp_path, field, value):
    hashes = _setup(tmp_path)
    target = tmp_path / "artifacts" / devb.DEV_B_SUMMARY_DIR / \
        f"{hashes['summary_hash']}.json"
    record = json.loads(target.read_text())
    record[field] = value
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    kwargs = _kwargs(tmp_path, hashes)
    kwargs["dev_b_summary_hash"] = replacement.stem
    # Exercise each semantic check with a digest-valid alternate summary.
    gate.S2V2_FROZEN_DEV_B_SUMMARY_HASH = replacement.stem
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**kwargs)
    assert _ack_files(tmp_path) == []


def test_wrong_summary_status_refused(tmp_path):
    _tamper_summary(tmp_path, "status", "SUPPORTED")


def test_wrong_summary_revision_refused(tmp_path):
    _tamper_summary(tmp_path, "code_revision", "foreign-producer-revision")


def test_wrong_summary_format_refused(tmp_path):
    _tamper_summary(tmp_path, "format", "foreign-devb-summary-v1")


def test_wrong_summary_q_hat_refused(tmp_path):
    _tamper_summary(tmp_path, "q_hat", Q_HAT * 2)


def test_wrong_summary_method_refused(tmp_path):
    _tamper_summary(tmp_path, "method_hash", "4" * 64)


def test_wrong_summary_criterion_refused(tmp_path):
    _tamper_summary(tmp_path, "criterion_hash", "5" * 64)


def test_wrong_summary_population_refused(tmp_path):
    _tamper_summary(tmp_path, "population_hash", "6" * 64)


def test_wrong_summary_package_binding_refused(tmp_path):
    _tamper_summary(tmp_path, "calibration_package_hash", "7" * 64)


def test_wrong_summary_identity_binding_refused(tmp_path):
    _tamper_summary(tmp_path, "pre_heldout_identity_hash", "8" * 64)


def test_wrong_summary_count_refused(tmp_path):
    _tamper_summary(tmp_path, "n_valid", 113)


# --- acknowledgment mutation resistance ------------------------------------

def _tamper_ack(tmp_path, field, value):
    hashes = _setup(tmp_path)
    gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    target = _ack_files(tmp_path)[0]
    record = _read_ack(target)
    record[field] = value
    replacement = target.parent / (digest(record) + ".json")
    replacement.write_text(json.dumps(record))
    target.unlink()
    with pytest.raises(ExecutionError):
        gate.verify_pre_heldout_no_change_complete(**_kwargs(tmp_path, hashes))


def test_ack_method_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "method_hash", "1" * 64)


def test_ack_criterion_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "criterion_hash", "2" * 64)


def test_ack_dev_a_population_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "dev_a_population_hash", "3" * 64)


def test_ack_dev_b_population_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "dev_b_population_hash", "4" * 64)


def test_ack_heldout_population_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "heldout_population_hash", "5" * 64)


def test_ack_combined_population_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "populations_hash", "6" * 64)


def test_ack_package_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "calibration_package_hash", "7" * 64)


def test_ack_identity_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "pre_heldout_identity_hash", "8" * 64)


def test_ack_q_hat_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "q_hat", Q_HAT * 3)


def test_ack_summary_hash_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "dev_b_summary_hash", "9" * 64)


def test_ack_summary_revision_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "dev_b_summary_code_revision", "other-revision")


def test_ack_decision_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "decision", "APPROVED")


def test_ack_heldout_status_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "heldout_status", "OPENED")


def test_ack_tuning_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "post_dev_b_tuning", "ALLOWED")


def test_ack_dev_b_role_mutation_refused(tmp_path):
    _tamper_ack(tmp_path, "dev_b_role", "QUALIFICATION")


# --- HELDOUT + scientific firewalls ------------------------------------------

@pytest.mark.parametrize("dirname", list(gate.HELDOUT_EVIDENCE_DIRS))
def test_heldout_evidence_refused(tmp_path, dirname):
    hashes = _setup(tmp_path)
    _write(tmp_path / "artifacts" / dirname / ("f" * 64 + ".json"),
           {"format": "heldout-evaluation-v1"})
    with pytest.raises(ExecutionError):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert _ack_files(tmp_path) == []


def test_heldout_evidence_is_detected_without_reading_outcomes(tmp_path, monkeypatch):
    hashes = _setup(tmp_path)
    outcome = tmp_path / "artifacts" / "heldout_evaluations" / ("a" * 64 + ".json")
    _write(outcome, {"outcome": "sensitive-heldout-result"})
    original = Path.read_bytes

    def guarded_read_bytes(path):
        if path.resolve() == outcome.resolve():
            raise AssertionError("HELDOUT outcome was read")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    with pytest.raises(ExecutionError, match="HELDOUT evidence already exists"):
        gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert _ack_files(tmp_path) == []


def test_frozen_heldout_inventory_metadata_is_allowed(tmp_path):
    hashes = _setup(tmp_path)
    _write(tmp_path / "artifacts" / "heldout_manifests"
           / f"{pop.S2V2_HELDOUT_HASH}.json", pop.S2V2_HELDOUT_RECORD)
    result = gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    assert result["acknowledged"] == 1


def test_acknowledge_creates_no_heldout_evidence(tmp_path):
    hashes = _setup(tmp_path)
    gate.acknowledge_pre_heldout_no_change(**_kwargs(tmp_path, hashes))
    for dirname in gate.HELDOUT_EVIDENCE_DIRS:
        assert not (tmp_path / "artifacts" / dirname).exists()
    record = _read_ack(_ack_files(tmp_path)[0])
    lowered = {key.lower() for key in record}
    for marker in ("verdict", "qualification", "pass", "fail"):
        assert marker not in lowered


def test_no_automatic_creation(tmp_path):
    hashes = _setup(tmp_path)
    assert devb.DEV_B_SUMMARY_DIR in {
        path.name for path in (tmp_path / "artifacts").iterdir()}
    assert not (tmp_path / "artifacts" / gate.NO_CHANGE_DIR).exists()
    text = Path(devb.__file__).read_text()
    assert "pre_heldout_no_change" not in text
    assert "acknowledge_pre_heldout_no_change" not in text


def test_real_devb_summary_hash_and_producer_revision_are_pinned():
    assert gate.S2V2_FROZEN_DEV_B_SUMMARY_HASH == (
        "f5a1b7d008773d3e40f94b0731d58225df0cd8793b45dd793672989e60534d63")
    assert gate.S2V2_FROZEN_DEV_B_CODE_REVISION == (
        "be1285311f81b0c5c54903c19c1b91b35f1d6fd5")


def test_no_scientific_comparison_in_gate():
    text = Path(gate.__file__).read_text()
    for marker in ("0.85", "5e-11", "QUALIFIED", "QualificationRecord",
                   "coverage >=", "coverage_ci", "mean_signed_error",
                   "mean_absolute_error", "binomial_interval",
                   "evaluate_heldout", "HeldoutEvaluation"):
        assert marker not in text, marker
    assert "build_pre_heldout_no_change" in text


def test_cli_requires_explicit_flag(tmp_path, monkeypatch):
    calls = []
    original = gate.acknowledge_pre_heldout_no_change

    def fake(**kwargs):
        calls.append(kwargs)
        return {"acknowledged": 1}

    monkeypatch.setattr(gate, "acknowledge_pre_heldout_no_change", fake)
    hashes = _setup(tmp_path)
    with pytest.raises(SystemExit):
        gate.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
                   "--artifact-root", str(tmp_path / "artifacts"),
                   "--package-hash", hashes["package_hash"],
                   "--identity-hash", hashes["identity_hash"],
                   "--dev-b-summary-hash", hashes["summary_hash"]])
    assert calls == []
    gate.main(["--dev-a-artifact-root", str(tmp_path / "deva"),
               "--artifact-root", str(tmp_path / "artifacts"),
               "--package-hash", hashes["package_hash"],
               "--identity-hash", hashes["identity_hash"],
               "--dev-b-summary-hash", hashes["summary_hash"],
               "--acknowledge-no-change"])
    assert len(calls) == 1
    assert calls[0]["dev_b_summary_hash"] == hashes["summary_hash"]
    monkeypatch.setattr(gate, "acknowledge_pre_heldout_no_change", original)
