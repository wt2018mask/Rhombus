"""Fixture-only tests for replay-verified S2 v2 closure records."""
import json

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_s2v2 import (
    S2V2_CRITERION_HASH,
    S2V2_METHOD_HASH,
)
from rudeus.science.calibration_s2v2_populations import (
    S2V2_HELDOUT_HASH,
    S2V2_HELDOUT_SEEDS,
)
from rudeus.science.calibration_s2v2_qualification import (
    NOT_QUALIFIED,
    QUALIFICATION_DIR,
    build_qualification_record,
    persist_qualification_record,
)
from rudeus.science.run_s2v2_heldout import EVALUATION_DIR
from rudeus.science.contracts import canonical_bytes, digest
from rudeus.science.s2v2_closure import (
    CLOSURE_DIR,
    CLOSURE_FORMAT,
    SCIENTIFIC_SCOPE,
    build_s2v2_closure_record,
    create_s2v2_scientific_closure,
    persist_s2v2_closure_record,
    verify_s2v2_scientific_closure,
)

ACK = "a" * 64
PACKAGE = "c" * 64
REVISION = "fixture-heldout-revision"
CLOSURE_REVISION = "fixture-closure-revision"
QUALIFICATION_KW = {
    "pre_heldout_acknowledgment_hash": ACK,
    "calibration_package_hash": PACKAGE,
    "q_hat": 1.0,
    "execution_code_revision": REVISION,
}


def _evaluations(*, all_covered=True, error=0.0):
    return [
        {
            "format": "s2v2-heldout-evaluation-v2",
            "replicate_id": replicate_id,
            "method_hash": S2V2_METHOD_HASH,
            "population_hash": S2V2_HELDOUT_HASH,
            "pre_heldout_acknowledgment_hash": ACK,
            "calibration_package_hash": PACKAGE,
            "q_hat": 1.0,
            "code_revision": REVISION,
            "covered": all_covered,
            "signed_error": error,
            "absolute_error": abs(error),
        }
        for replicate_id in sorted(S2V2_HELDOUT_SEEDS)
    ]


def _qualification_fixture(root, *, all_covered=True, error=0.0):
    evaluations = _evaluations(all_covered=all_covered, error=error)
    evaluation_dir = root / EVALUATION_DIR
    evaluation_dir.mkdir(parents=True)
    for record in evaluations:
        (evaluation_dir / f"{digest(record)}.json").write_bytes(
            canonical_bytes(record))

    marker = {
        "format": "s2v2-heldout-open-v1",
        "transition": "OPEN",
        "previous_status": "UNOPENED",
        "heldout_status": "OPENED",
        "pre_heldout_acknowledgment_hash": ACK,
        "method_hash": evaluations[0]["method_hash"],
        "criterion_hash": S2V2_CRITERION_HASH,
        "heldout_population_hash": S2V2_HELDOUT_HASH,
        "calibration_package_hash": PACKAGE,
        "q_hat": 1.0,
        "heldout_execution_code_revision": REVISION,
    }
    marker_hash = digest(marker)
    marker_dir = root / "heldout_open"
    marker_dir.mkdir()
    (marker_dir / f"{marker_hash}.json").write_bytes(canonical_bytes(marker))

    record = build_qualification_record(
        evaluation_records=evaluations,
        heldout_open_marker_hash=marker_hash,
        **QUALIFICATION_KW)
    persisted = persist_qualification_record(artifact_root=root, record=record)
    return record, persisted["qualification_hash"]


def _create(root):
    _, qualification_hash = _qualification_fixture(root)
    result = create_s2v2_scientific_closure(
        artifact_root=root,
        qualification_hash=qualification_hash,
        closure_code_revision=CLOSURE_REVISION,
    )
    return result, qualification_hash


def test_create_and_verify_replay_qualified_closure(tmp_path):
    result, qualification_hash = _create(tmp_path)
    record = result["closure_record"]
    assert result["replayed"] == "VERIFIED"
    assert result["closure_hash"] == digest(record)
    assert record["format"] == CLOSURE_FORMAT
    assert record["phase"] == "CLOSED"
    assert record["scientific_status"] == "QUALIFIED"
    assert record["scientific_scope"] == SCIENTIFIC_SCOPE
    assert record["qualification_record_hash"] == qualification_hash
    path = tmp_path / CLOSURE_DIR / f"{result['closure_hash']}.json"
    assert path.read_bytes() == canonical_bytes(record)
    assert verify_s2v2_scientific_closure(
        artifact_root=tmp_path, closure_hash=result["closure_hash"]) == record


def test_deterministic_hash_and_append_only_idempotence(tmp_path):
    first, qualification_hash = _create(tmp_path)
    second = create_s2v2_scientific_closure(
        artifact_root=tmp_path,
        qualification_hash=qualification_hash,
        closure_code_revision=CLOSURE_REVISION,
    )
    assert second == first
    paths = list((tmp_path / CLOSURE_DIR).glob("*.json"))
    assert len(paths) == 1
    before = paths[0].read_bytes()
    persist_s2v2_closure_record(
        artifact_root=tmp_path, record=first["closure_record"])
    assert paths[0].read_bytes() == before


@pytest.mark.parametrize(("field", "value"), [
    ("format", "other"), ("phase", "OPEN"),
    ("scientific_status", NOT_QUALIFIED),
    ("scientific_scope", "different scope"),
    ("qualification_record_hash", "d" * 64),
    ("method_hash", "d" * 64), ("criterion_hash", "d" * 64),
    ("heldout_population_hash", "d" * 64),
    ("calibration_package_hash", "d" * 64),
    ("pre_heldout_acknowledgment_hash", "d" * 64),
    ("heldout_open_marker_hash", "d" * 64),
    ("heldout_execution_code_revision", "other revision"),
    ("q_hat", 2.0), ("n_attempted", 1), ("n_valid", 1),
    ("n_covered", 1), ("n_missed", 378), ("coverage", 0.1),
    ("coverage_lcb_95", 0.1),
    ("coverage_criterion_result", "FAIL"),
    ("mean_signed_error", 1.0), ("abs_mean_signed_error", 1.0),
    ("mean_absolute_error", 1.0), ("bias_criterion_result", "FAIL"),
    ("final_qualification_state", NOT_QUALIFIED),
    ("closure_code_revision", "other closure revision"),
])
def test_digest_valid_closure_field_mutation_rejected(tmp_path, field, value):
    result, _ = _create(tmp_path)
    mutated = dict(result["closure_record"], **{field: value})
    mutated_hash = digest(mutated)
    path = tmp_path / CLOSURE_DIR / f"{mutated_hash}.json"
    path.write_bytes(canonical_bytes(mutated))
    with pytest.raises(ExecutionError):
        verify_s2v2_scientific_closure(
            artifact_root=tmp_path, closure_hash=mutated_hash)


def test_digest_valid_underlying_qualification_mutation_rejected(tmp_path):
    record, qualification_hash = _qualification_fixture(tmp_path)
    mutated = dict(record, coverage=0.5)
    mutated_hash = digest(mutated)
    qualification_dir = tmp_path / QUALIFICATION_DIR
    (qualification_dir / f"{qualification_hash}.json").unlink()
    (qualification_dir / f"{mutated_hash}.json").write_bytes(canonical_bytes(mutated))
    with pytest.raises(ExecutionError):
        create_s2v2_scientific_closure(
            artifact_root=tmp_path,
            qualification_hash=mutated_hash,
            closure_code_revision=CLOSURE_REVISION,
        )
    assert not (tmp_path / CLOSURE_DIR).exists()


@pytest.mark.parametrize("invalid_state", [
    "INDETERMINATE / INTEGRITY-HOLD",
    "UNKNOWN",
])
def test_integrity_hold_or_invalid_qualification_refused(tmp_path, invalid_state):
    record, qualification_hash = _qualification_fixture(tmp_path)
    mutated = dict(record, final_qualification_state=invalid_state)
    mutated_hash = digest(mutated)
    qualification_dir = tmp_path / QUALIFICATION_DIR
    (qualification_dir / f"{qualification_hash}.json").unlink()
    (qualification_dir / f"{mutated_hash}.json").write_bytes(canonical_bytes(mutated))
    with pytest.raises(ExecutionError):
        create_s2v2_scientific_closure(
            artifact_root=tmp_path,
            qualification_hash=mutated_hash,
            closure_code_revision=CLOSURE_REVISION,
        )
    assert not (tmp_path / CLOSURE_DIR).exists()


def test_not_qualified_cannot_be_closed(tmp_path):
    _, qualification_hash = _qualification_fixture(tmp_path, all_covered=False)
    with pytest.raises(ExecutionError):
        create_s2v2_scientific_closure(
            artifact_root=tmp_path,
            qualification_hash=qualification_hash,
            closure_code_revision=CLOSURE_REVISION,
        )
    assert not (tmp_path / CLOSURE_DIR).exists()


def test_missing_duplicate_and_wrong_qualification_hash_refused(tmp_path):
    with pytest.raises(ExecutionError):
        create_s2v2_scientific_closure(
            artifact_root=tmp_path, qualification_hash="e" * 64,
            closure_code_revision=CLOSURE_REVISION)

    _, qualification_hash = _qualification_fixture(tmp_path)
    with pytest.raises(ExecutionError):
        create_s2v2_scientific_closure(
            artifact_root=tmp_path, qualification_hash="f" * 64,
            closure_code_revision=CLOSURE_REVISION)
    directory = tmp_path / QUALIFICATION_DIR
    existing = next(directory.glob("*.json"))
    (directory / f"{'e' * 64}.json").write_bytes(existing.read_bytes())
    with pytest.raises(ExecutionError):
        create_s2v2_scientific_closure(
            artifact_root=tmp_path, qualification_hash=qualification_hash,
            closure_code_revision=CLOSURE_REVISION)


def test_conflicting_closures_for_one_qualification_refused(tmp_path):
    result, qualification_hash = _create(tmp_path)
    conflict = dict(result["closure_record"], closure_code_revision="conflict")
    with pytest.raises(ExecutionError):
        persist_s2v2_closure_record(artifact_root=tmp_path, record=conflict)
    assert len(list((tmp_path / CLOSURE_DIR).glob("*.json"))) == 1


def test_builder_does_not_upgrade_not_qualified_record(tmp_path):
    record, _ = _qualification_fixture(tmp_path, all_covered=False)
    with pytest.raises(ExecutionError):
        build_s2v2_closure_record(record, digest(record), CLOSURE_REVISION)
