"""Focused Stage-B builder tests (fixture/in-memory inputs only).

No execution, no trajectories, no estimator calls, no filesystem evidence,
no learned content from real data. All score records are synthetic fixtures
built by the frozen builder itself.
"""
from pathlib import Path

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science import calibration_s2v2 as method
from rudeus.science import calibration_s2v2_populations as pop
from rudeus.science import calibration_s2v2_stageb as stageb
from rudeus.science.contracts import digest

TRUTH = 1.0e-9
REVISION = "stageb-fixture-revision"


def _hex(char, length=64):
    return (char * length)[:length]


def _hashes(suffix):
    return {
        "replicate_manifest_hash": _hex("a", 63) + suffix,
        "estimator_result_hash": _hex("b", 63) + suffix,
        "truth_record_hash": _hex("c", 63) + suffix,
    }


def _estimate(index):
    return TRUTH + index * 1.0e-11


def _dev_a_ids():
    return sorted(pop.S2V2_DEV_A_SEEDS)


def _fixture_records(count=99):
    records = []
    for position, replicate_id in enumerate(_dev_a_ids()[:count]):
        suffix = "%x" % (position % 16)
        record = stageb.build_s2v2_score_record(
            replicate_id=replicate_id, estimate_D=_estimate(position),
            truth_D=TRUTH, code_revision=REVISION, **_hashes(suffix))
        # One frozen truth record serves the whole calibration cell.
        record["truth_record_hash"] = "c" * 64
        records.append(record)
    return records


def test_score_equals_abs_error():
    record = stageb.build_s2v2_score_record(
        replicate_id="s2v2-dev-a-001", estimate_D=1.25e-9, truth_D=TRUTH,
        code_revision=REVISION, **_hashes("0"))
    assert record["score_value"] == abs(1.25e-9 - TRUTH)


def test_score_rejects_nonfinite_estimate():
    for bad in (float("nan"), float("inf"), float("-inf"), "1e-9", True, None):
        with pytest.raises(ExecutionError):
            stageb.build_s2v2_score_record(
                replicate_id="s2v2-dev-a-001", estimate_D=bad, truth_D=TRUTH,
                code_revision=REVISION, **_hashes("1"))


def test_score_rejects_wrong_method_hash():
    with pytest.raises(ExecutionError):
        stageb.build_s2v2_score_record(
            replicate_id="s2v2-dev-a-001", estimate_D=1e-9, truth_D=TRUTH,
            method_hash="0" * 64, code_revision=REVISION, **_hashes("2"))


def test_score_rejects_wrong_population_hash():
    with pytest.raises(ExecutionError):
        stageb.build_s2v2_score_record(
            replicate_id="s2v2-dev-a-001", estimate_D=1e-9, truth_D=TRUTH,
            population_hash=pop.S2V2_DEV_B_HASH, code_revision=REVISION,
            **_hashes("3"))


def test_score_rejects_foreign_dev_b_id():
    with pytest.raises(ExecutionError):
        stageb.build_s2v2_score_record(
            replicate_id="s2v2-dev-b-001", estimate_D=1e-9, truth_D=TRUTH,
            code_revision=REVISION, **_hashes("4"))


def test_score_rejects_foreign_heldout_id():
    with pytest.raises(ExecutionError):
        stageb.build_s2v2_score_record(
            replicate_id="s2v2-heldout-001", estimate_D=1e-9, truth_D=TRUTH,
            code_revision=REVISION, **_hashes("5"))


def test_score_digest_deterministic():
    kwargs = dict(replicate_id="s2v2-dev-a-007", estimate_D=1.1e-9,
                  truth_D=TRUTH, code_revision=REVISION, **_hashes("6"))
    assert (digest(stageb.build_s2v2_score_record(**kwargs))
            == digest(stageb.build_s2v2_score_record(**kwargs)))


def test_score_provenance_mutation_moves_digest():
    base = stageb.build_s2v2_score_record(
        replicate_id="s2v2-dev-a-007", estimate_D=1.1e-9, truth_D=TRUTH,
        code_revision=REVISION, **_hashes("7"))
    reference = digest(base)
    for key in ("replicate_manifest_hash", "estimator_result_hash",
                "truth_record_hash", "code_revision"):
        altered = dict(base)
        altered[key] = "f" * 64 if "hash" in key else "altered-revision"
        assert digest(altered) != reference


def test_package_refuses_98_scores():
    with pytest.raises(ExecutionError):
        stageb.freeze_s2v2_calibration_package(
            score_records=_fixture_records(98), code_revision=REVISION)


def test_package_refuses_mixed_code_revisions():
    records = [dict(record) for record in _fixture_records(99)]
    records[0]["code_revision"] = "different-revision"
    with pytest.raises(ExecutionError):
        stageb.freeze_s2v2_calibration_package(
            score_records=records, code_revision=REVISION)
    records[0]["code_revision"] = ""
    with pytest.raises(ExecutionError):
        stageb.freeze_s2v2_calibration_package(
            score_records=records, code_revision=REVISION)


def test_package_refuses_divergent_truth():
    records = [dict(record) for record in _fixture_records(99)]
    records[0]["truth_record_hash"] = "d" * 64
    with pytest.raises(ExecutionError):
        stageb.freeze_s2v2_calibration_package(
            score_records=records, code_revision=REVISION)


def test_package_refuses_missing_id():
    records = [record for record in _fixture_records(99)
               if record["replicate_id"] != "s2v2-dev-a-050"]
    assert len(records) == 98
    with pytest.raises(ExecutionError):
        stageb.freeze_s2v2_calibration_package(
            score_records=records, code_revision=REVISION)


def test_package_refuses_duplicate_id():
    records = _fixture_records(99)
    records = records + [records[0]]
    with pytest.raises(ExecutionError):
        stageb.freeze_s2v2_calibration_package(
            score_records=records, code_revision=REVISION)


def test_package_refuses_unexpected_id():
    records = _fixture_records(98)
    intruder = dict(records[0])
    intruder["replicate_id"] = "s2v2-dev-b-001"
    with pytest.raises(ExecutionError):
        stageb.freeze_s2v2_calibration_package(
            score_records=records + [intruder], code_revision=REVISION)


def test_valid_fixture_freezes():
    package = stageb.freeze_s2v2_calibration_package(
        score_records=_fixture_records(99), code_revision=REVISION)
    assert package["n"] == 99
    assert package["package_status"] == "FROZEN-DESCRIPTIVE-NOT-QUALIFICATION"


def test_conformal_rank_exactly_90():
    assert method.conformal_rank(99) == 90
    package = stageb.freeze_s2v2_calibration_package(
        score_records=_fixture_records(99), code_revision=REVISION)
    assert package["k"] == 90


def test_q_hat_is_90th_sorted_score():
    records = _fixture_records(99)
    package = stageb.freeze_s2v2_calibration_package(
        score_records=records, code_revision=REVISION)
    expected = sorted(record["score_value"] for record in records)[89]
    assert package["q_hat"] == expected


def test_q_hat_is_supplied_value_not_interpolated():
    records = _fixture_records(99)
    package = stageb.freeze_s2v2_calibration_package(
        score_records=records, code_revision=REVISION)
    values = sorted(record["score_value"] for record in records)
    assert package["q_hat"] in values
    midpoint = (values[89] + values[90]) / 2
    assert values[89] != midpoint
    assert package["q_hat"] != midpoint


def test_input_ordering_does_not_change_package():
    forward = stageb.freeze_s2v2_calibration_package(
        score_records=_fixture_records(99), code_revision=REVISION)
    backward = stageb.freeze_s2v2_calibration_package(
        score_records=list(reversed(_fixture_records(99))),
        code_revision=REVISION)
    assert digest(forward) == digest(backward)


def test_score_mutation_moves_package_digest():
    records = _fixture_records(99)
    reference = digest(stageb.freeze_s2v2_calibration_package(
        score_records=records, code_revision=REVISION))
    mutated = [dict(record) for record in records]
    mutated[10]["score_value"] = mutated[10]["score_value"] + 1.0e-12
    assert digest(stageb.freeze_s2v2_calibration_package(
        score_records=mutated, code_revision=REVISION)) != reference


def test_package_has_no_dev_b_fields():
    package = stageb.freeze_s2v2_calibration_package(
        score_records=_fixture_records(99), code_revision=REVISION)
    blob = str(package)
    assert "dev-b" not in blob and "dev_b" not in blob
    assert pop.S2V2_DEV_B_HASH not in blob


def test_package_has_no_heldout_outcome():
    package = stageb.freeze_s2v2_calibration_package(
        score_records=_fixture_records(99), code_revision=REVISION)
    blob = str(package)
    assert "heldout" not in blob and "HELDOUT" not in blob
    for word in ("coverage_conditional", "coverage_unconditional",
                 "\"coverage\":", "verdict", "\"PASS\"", "\"FAIL\"",
                 "QUALIFIED", "bounds", "dev_b", "dev-b", "outcome"):
        assert word not in blob


def test_package_has_no_qualification_verdict():
    package = stageb.freeze_s2v2_calibration_package(
        score_records=_fixture_records(99), code_revision=REVISION)
    assert package["package_status"] == "FROZEN-DESCRIPTIVE-NOT-QUALIFICATION"
    assert "verdict" not in str(package).lower()


def test_complete_identity_deterministic():
    package = stageb.freeze_s2v2_calibration_package(
        score_records=_fixture_records(99), code_revision=REVISION)
    package_hash = digest(package)
    first = stageb.build_complete_pre_heldout_identity(
        calibration_package_hash=package_hash, code_revision=REVISION)
    second = stageb.build_complete_pre_heldout_identity(
        calibration_package_hash=package_hash, code_revision=REVISION)
    assert digest(first) == digest(second)
    assert first["calibration_package_hash"] == package_hash
    assert first["phase"] == {"calibration": "frozen", "dev_b": "not-evaluated",
                              "heldout": "unopened"}


def test_package_hash_mutation_moves_identity():
    package = stageb.freeze_s2v2_calibration_package(
        score_records=_fixture_records(99), code_revision=REVISION)
    reference = stageb.build_complete_pre_heldout_identity(
        calibration_package_hash=digest(package), code_revision=REVISION)
    altered = stageb.build_complete_pre_heldout_identity(
        calibration_package_hash="e" * 64, code_revision=REVISION)
    assert digest(altered) != digest(reference)


def test_frozen_hash_mutation_moves_identity():
    # The builder itself refuses a non-frozen method hash (fail-fast); hash
    # sensitivity is therefore shown on the built identity mapping: swapping
    # the bound method hash changes the identity digest.
    package = stageb.freeze_s2v2_calibration_package(
        score_records=_fixture_records(99), code_revision=REVISION)
    identity = stageb.build_complete_pre_heldout_identity(
        calibration_package_hash=digest(package), code_revision=REVISION)
    reference = digest(identity)
    with pytest.raises(ExecutionError):
        stageb.build_complete_pre_heldout_identity(
            calibration_package_hash=digest(package), code_revision=REVISION,
            method_hash="d" * 64)
    altered = dict(identity)
    altered["method_hash"] = "d" * 64
    assert digest(altered) != reference


def test_method_hash_unchanged():
    assert method.S2V2_METHOD_HASH == (
        "3b6f1d0a7e8ca64f02c0bd68c6a7a0af88c40e36298eade055459c5e424bd28b")
    assert method.S2V2_CRITERION_HASH == (
        "4eb3c4ac4769d14cfcffe54de070dd90703271efc6694e9f11be9cb35185098b")


def test_no_v1_bootstrap_dependency():
    text = Path(stageb.__file__).read_text()
    for marker in ("estimate_interval_for_replicate",
                   "matched_origin_block_bootstrap", "calibration_intervals",
                   "block_origins", "np.quantile", "quantile(",
                   "bootstrap", "np.", "numpy"):
        assert marker not in text, marker
    assert "abs(" in text  # score uses builtin abs, not numpy
