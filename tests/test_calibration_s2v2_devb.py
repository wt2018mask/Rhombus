"""Focused DEV-B builder tests (fixture/in-memory inputs only).

No execution, no trajectories, no estimator calls, no filesystem evidence,
no learned content from real data. The frozen q_hat value below is the
committed DEV-A calibration output reused as a fixture constant.
"""
import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science import calibration_s2v2_devb as devb
from rudeus.science import calibration_s2v2_populations as pop
from rudeus.science.contracts import digest
from rudeus.science.statistics import binomial_interval

TRUTH = 1.0e-9
Q_HAT = 7.195845360795594e-10
REVISION = "devb-fixture-revision"
PACKAGE = "a" * 64
IDENTITY = "b" * 64


def _hashes(suffix):
    return {
        "replicate_manifest_hash": "c" * 63 + suffix,
        "estimator_result_hash": "d" * 63 + suffix,
        "truth_record_hash": "e" * 63 + suffix,
    }


def _dev_b_ids():
    return sorted(pop.S2V2_DEV_B_SEEDS)


def _evaluation(replicate_id, estimate, suffix="0"):
    return devb.build_s2v2_devb_evaluation(
        replicate_id=replicate_id, estimate_D=estimate, truth_D=TRUTH,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION, **_hashes(suffix))


def _fixture_evaluations(count=114):
    records = []
    for position, replicate_id in enumerate(_dev_b_ids()[:count]):
        suffix = "%x" % (position % 16)
        records.append(_evaluation(
            replicate_id, TRUTH + (position - 57) * 1.0e-11, suffix))
    return records


def test_covered_replicate_exact():
    estimate = TRUTH + 1.0e-10
    record = _evaluation("s2v2-dev-b-001", estimate, "1")
    assert record["signed_error"] == estimate - TRUTH
    assert record["absolute_error"] == abs(estimate - TRUTH)
    assert record["interval_lower"] == estimate - Q_HAT
    assert record["interval_upper"] == estimate + Q_HAT
    assert record["covered"] is True


def test_missed_replicate():
    estimate = TRUTH + 10 * Q_HAT
    record = _evaluation("s2v2-dev-b-001", estimate, "2")
    assert record["covered"] is False
    assert record["absolute_error"] == abs(estimate - TRUTH)


def test_closed_lower_bound_equality():
    record = _evaluation("s2v2-dev-b-001", TRUTH + Q_HAT, "3")
    assert record["interval_lower"] == TRUTH
    assert record["covered"] is True


def test_closed_upper_bound_equality():
    record = _evaluation("s2v2-dev-b-001", TRUTH - Q_HAT, "4")
    assert record["interval_upper"] == TRUTH
    assert record["covered"] is True


def test_negative_lower_bound_unclipped():
    record = _evaluation("s2v2-dev-b-001", Q_HAT / 2, "5")
    assert record["interval_lower"] == Q_HAT / 2 - Q_HAT
    assert record["interval_lower"] < 0


def test_invalid_q_hat_rejected():
    for bad in (-1.0e-10, float("nan"), float("inf"), "x", True, None):
        with pytest.raises(ExecutionError):
            devb.build_s2v2_devb_evaluation(
                replicate_id="s2v2-dev-b-001", estimate_D=TRUTH,
                truth_D=TRUTH, calibration_package_hash=PACKAGE,
                q_hat=bad, code_revision=REVISION, **_hashes("6"))


def test_invalid_estimate_truth_rejected():
    for bad in (float("nan"), float("inf"), "1e-9", True, None):
        with pytest.raises(ExecutionError):
            devb.build_s2v2_devb_evaluation(
                replicate_id="s2v2-dev-b-001", estimate_D=bad, truth_D=TRUTH,
                calibration_package_hash=PACKAGE, q_hat=Q_HAT,
                code_revision=REVISION, **_hashes("7"))
        with pytest.raises(ExecutionError):
            devb.build_s2v2_devb_evaluation(
                replicate_id="s2v2-dev-b-001", estimate_D=TRUTH, truth_D=bad,
                calibration_package_hash=PACKAGE, q_hat=Q_HAT,
                code_revision=REVISION, **_hashes("7"))


def test_wrong_hashes_rejected():
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_evaluation(
            replicate_id="s2v2-dev-a-001", estimate_D=TRUTH, truth_D=TRUTH,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision=REVISION, **_hashes("8"))
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_evaluation(
            replicate_id="s2v2-dev-b-001", estimate_D=TRUTH, truth_D=TRUTH,
            calibration_package_hash="not-a-hash", q_hat=Q_HAT,
            code_revision=REVISION, **_hashes("8"))
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_evaluation(
            replicate_id="s2v2-dev-b-001", estimate_D=TRUTH, truth_D=TRUTH,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision="", **_hashes("8"))


def test_114_records_accepted():
    summary = devb.build_s2v2_devb_summary(
        evaluation_records=_fixture_evaluations(114),
        pre_heldout_identity_hash=IDENTITY,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION)
    assert summary["n_attempted"] == 114
    assert summary["n_valid"] == 114


def test_missing_record_rejected():
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_summary(
            evaluation_records=_fixture_evaluations(113),
            pre_heldout_identity_hash=IDENTITY,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision=REVISION)


def test_duplicate_id_rejected():
    records = _fixture_evaluations(114)
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_summary(
            evaluation_records=records + [records[0]],
            pre_heldout_identity_hash=IDENTITY,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision=REVISION)


def test_unexpected_id_rejected():
    records = _fixture_evaluations(113)
    intruder = dict(records[0])
    intruder["replicate_id"] = "s2v2-dev-a-001"
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_summary(
            evaluation_records=records + [intruder],
            pre_heldout_identity_hash=IDENTITY,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision=REVISION)


def test_wrong_population_hash_rejected():
    records = _fixture_evaluations(114)
    altered = [dict(record) for record in records]
    altered[0]["population_hash"] = pop.S2V2_DEV_A_HASH
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_summary(
            evaluation_records=altered,
            pre_heldout_identity_hash=IDENTITY,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision=REVISION)


def test_wrong_package_hash_rejected():
    records = _fixture_evaluations(114)
    altered = [dict(record) for record in records]
    altered[0]["calibration_package_hash"] = "f" * 64
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_summary(
            evaluation_records=altered,
            pre_heldout_identity_hash=IDENTITY,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision=REVISION)


def test_wrong_method_hash_rejected():
    records = [dict(record) for record in _fixture_evaluations(2)]
    records[0]["method_hash"] = "f" * 64
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_summary(
            evaluation_records=_fixture_evaluations(112) + records,
            pre_heldout_identity_hash=IDENTITY,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision=REVISION)


def test_q_hat_mismatch_rejected():
    records = [dict(record) for record in _fixture_evaluations(114)]
    records[0]["q_hat"] = Q_HAT * 2
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_summary(
            evaluation_records=records,
            pre_heldout_identity_hash=IDENTITY,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision=REVISION)


def test_revision_mismatch_rejected():
    records = [dict(record) for record in _fixture_evaluations(114)]
    records[0]["code_revision"] = "other-revision"
    with pytest.raises(ExecutionError):
        devb.build_s2v2_devb_summary(
            evaluation_records=records,
            pre_heldout_identity_hash=IDENTITY,
            calibration_package_hash=PACKAGE, q_hat=Q_HAT,
            code_revision=REVISION)


def test_deterministic_ordering():
    records = _fixture_evaluations(114)
    forward = devb.build_s2v2_devb_summary(
        evaluation_records=records,
        pre_heldout_identity_hash=IDENTITY,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION)
    backward = devb.build_s2v2_devb_summary(
        evaluation_records=list(reversed(records)),
        pre_heldout_identity_hash=IDENTITY,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION)
    assert digest(forward) == digest(backward)


def test_evaluation_mutation_propagates_to_summary_identity():
    records = _fixture_evaluations(114)
    original = devb.build_s2v2_devb_summary(
        evaluation_records=records,
        pre_heldout_identity_hash=IDENTITY,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION)
    index = next(
        position for position, record in enumerate(records)
        if record["covered"])
    replicate_id = records[index]["replicate_id"]
    mutated_evaluation = devb.build_s2v2_devb_evaluation(
        replicate_id=replicate_id, estimate_D=TRUTH + 10 * Q_HAT,
        truth_D=TRUTH, calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION, **_hashes("%x" % (index % 16)))
    assert mutated_evaluation["covered"] is False
    assert records[index]["covered"] is True
    assert digest(mutated_evaluation) != digest(records[index])
    mutated = list(records)
    mutated[index] = mutated_evaluation
    mutated_summary = devb.build_s2v2_devb_summary(
        evaluation_records=mutated,
        pre_heldout_identity_hash=IDENTITY,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION)
    assert (mutated_summary["ordered_evaluation_hashes"]
            != original["ordered_evaluation_hashes"])
    assert mutated_summary["n_covered"] == original["n_covered"] - 1
    assert mutated_summary["n_missed"] == original["n_missed"] + 1
    assert digest(mutated_summary) != digest(original)


def test_coverage_recomputation():
    records = _fixture_evaluations(114)
    summary = devb.build_s2v2_devb_summary(
        evaluation_records=records,
        pre_heldout_identity_hash=IDENTITY,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION)
    covered = sum(1 for record in records if record["covered"])
    assert summary["n_covered"] == covered
    assert summary["n_missed"] == 114 - covered
    assert summary["coverage"] == covered / 114


def test_exact_ci():
    records = _fixture_evaluations(114)
    summary = devb.build_s2v2_devb_summary(
        evaluation_records=records,
        pre_heldout_identity_hash=IDENTITY,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION)
    covered = sum(1 for record in records if record["covered"])
    expected = binomial_interval(covered, 114, 0.90)
    assert summary["coverage_ci"] == [float(expected[0]), float(expected[1])]
    assert summary["coverage_ci_confidence"] == 0.90
    assert summary["coverage_ci_sidedness"] == "two-sided"


def test_bias_recomputation():
    records = _fixture_evaluations(114)
    summary = devb.build_s2v2_devb_summary(
        evaluation_records=records,
        pre_heldout_identity_hash=IDENTITY,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION)
    signed = [record["signed_error"] for record in records]
    absolute = [record["absolute_error"] for record in records]
    mean_signed = sum(signed) / len(signed)
    assert summary["mean_signed_error"] == mean_signed
    assert summary["abs_mean_signed_error"] == abs(mean_signed)
    assert summary["mean_absolute_error"] == sum(absolute) / len(absolute)


def test_no_verdict_semantics():
    evaluation = _evaluation("s2v2-dev-b-001", TRUTH, "9")
    assert set(evaluation.keys()) == {
        "format", "replicate_id", "replicate_manifest_hash",
        "estimator_result_hash", "truth_record_hash",
        "calibration_package_hash", "method_hash", "population_hash",
        "q_hat", "q_hat_units", "interval_lower", "interval_upper",
        "covered", "signed_error", "absolute_error", "units",
        "code_revision"}
    summary = devb.build_s2v2_devb_summary(
        evaluation_records=_fixture_evaluations(114),
        pre_heldout_identity_hash=IDENTITY,
        calibration_package_hash=PACKAGE, q_hat=Q_HAT,
        code_revision=REVISION)
    assert set(summary.keys()) == {
        "format", "population_hash", "calibration_package_hash",
        "pre_heldout_identity_hash", "method_hash", "criterion_hash",
        "q_hat", "q_hat_units", "n_attempted", "n_valid", "n_covered",
        "n_missed", "coverage", "coverage_ci", "coverage_ci_confidence",
        "coverage_ci_sidedness", "mean_signed_error",
        "abs_mean_signed_error", "mean_absolute_error",
        "ordered_evaluation_hashes", "code_revision", "status"}
    assert summary["status"] == "DESCRIPTIVE-NON-QUALIFICATION"
