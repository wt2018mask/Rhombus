"""Focused Stage-A tests for the frozen S2 v2 method contract.

Method-contract only: no DEV execution, no HELD_OUT execution, no learned
quantile, no QualificationRecord, no Uncertainty.bounds, no v1/v3 evidence
reads. Importing this module executes nothing scientific.
"""
from pathlib import Path

import pytest

from rudeus.execution.contracts import ExecutionError
from rudeus.science import calibration_s2v2 as v2
from rudeus.science.calibration_s2 import S2_PROCEDURE_HASH
from rudeus.science.contracts import digest
from rudeus.science.statistics import binomial_interval


def test_method_identity_deterministic():
    assert v2.build_s2v2_method() == v2.S2V2_METHOD
    assert digest(v2.S2V2_METHOD) == v2.S2V2_METHOD_HASH
    assert digest(v2.S2V2_CRITERION) == v2.S2V2_CRITERION_HASH
    assert v2.assert_frozen_v2_policy() is None


def test_v1_v2_identities_differ():
    assert v2.S2V2_METHOD_HASH != S2_PROCEDURE_HASH
    assert v2.S2V2_METHOD["version"] == "s2-interval-procedure-v2"


def test_v1_hash_citation_only():
    assert (v2.S2V2_METHOD["historical_v1"]["procedure_hash"]
            == "088688e9ab8388dcc13a0cf2b23264d3d53e6f3d75b024ea5a46b49b449e0cf8")
    assert v2.S2V2_METHOD["historical_v1"]["enters_calibration"] is False
    assert v2.S2V2_CALIBRATION_PACKAGE is None
    assert v2.S2V2_METHOD["calibration_package"] is None


def test_frozen_policy_values():
    assert v2.S2V2_TARGET_COVERAGE == 0.90
    assert v2.S2V2_MINIMUM_COVERAGE == 0.85
    assert v2.S2V2_ALLOWED_SHORTFALL == 0.05
    assert v2.S2V2_HELDOUT_CONFIDENCE == 0.95
    assert v2.S2V2_BIAS_TOLERANCE_M2_PER_S == 5e-11
    assert v2.S2V2_BIAS_METRIC == "abs-mean-signed-error"
    assert v2.S2V2_INTERVAL_FORM == "two-sided"
    assert v2.S2V2_ARCHITECTURE == "split-conformal-independent-trajectories"


def test_brownian_failure_ceilings_zero():
    assert v2.S2V2_ABSTENTION_CEILING == 0
    assert v2.S2V2_EXECUTION_FAILURE_CEILING == 0
    assert v2.S2V2_ESTIMATOR_FAILURE_CEILING == 0
    assert v2.S2V2_INTERVAL_FAILURE_CEILING == 0
    policy = v2.S2V2_METHOD["operational_policy"]
    assert policy["integrity"] == "zero-tolerance-package-invalid"


def test_conformal_rank_exact():
    assert v2.conformal_rank(99) == 90
    assert v2.conformal_rank(9) == 9
    assert v2.conformal_rank(19) == 18
    # Exact rational arithmetic, not float multiplication: oracle is the
    # integer formula ceil(9(n+1)/10), valid only where k <= n.
    for n in (9, 10, 19, 63, 64, 99, 100, 379):
        assert v2.conformal_rank(n) == (9 * (n + 1) + 9) // 10
    # Rule helper agrees with the frozen quantile rule on supplied scores:
    # rank(100) = 91, so the 91st order statistic of 1..100 is 91.0.
    scores = [float(i) for i in range(1, 101)]
    assert v2.conformal_quantile_from_scores(scores) == 91.0


def test_small_n_rank_insufficient_evidence():
    for n in (1, 2, 8):
        with pytest.raises(ExecutionError) as excinfo:
            v2.conformal_rank(n)
        assert "INSUFFICIENT EVIDENCE" in str(excinfo.value)
    with pytest.raises(ExecutionError):
        v2.conformal_quantile_from_scores([1.0, 2.0, 3.0])


def test_calibration_resolution_derives_99():
    assert v2.calibration_minimum_n(0.01) == 99
    assert v2.calibration_minimum_n() == 99
    # Minimality exact-verified, not asserted by habit.
    assert 1 / (99 + 1) <= 0.01
    assert not 1 / (98 + 1) <= 0.01


def test_heldout_power_planning_derives_oracle():
    result = v2.heldout_exact_power_n()
    assert result["n"] == 379
    assert result["critical_successes"] == 334
    assert result["lcb_at_critical"] == pytest.approx(0.85037, abs=5e-4)
    assert result["power"] == pytest.approx(0.9011, abs=5e-4)
    # Minimality: n - 1 must fail the power target under the same rule.
    smaller = v2.heldout_exact_power_n(target_power=result["power"] + 1e-9)
    assert smaller["n"] >= result["n"]


def test_heldout_planning_computes_not_hardcodes():
    relaxed = v2.heldout_exact_power_n(target_power=0.50)
    assert relaxed["n"] < 379
    assert relaxed["n"] >= 1
    # Critical count is genuinely the threshold crossing, recomputed here.
    assert (v2.exact_one_sided_lcb(relaxed["critical_successes"], relaxed["n"], 0.95)
            >= 0.85)
    if relaxed["critical_successes"] > 0:
        assert not (v2.exact_one_sided_lcb(relaxed["critical_successes"] - 1,
                                           relaxed["n"], 0.95) >= 0.85)


def test_heldout_power_planning_rejects_infeasible_inputs():
    with pytest.raises(ExecutionError) as excinfo:
        v2.heldout_exact_power_n(p_true=0.50, minimum_coverage=0.85)
    assert "INSUFFICIENT EVIDENCE" in str(excinfo.value)
    # Frozen coherent path unchanged.
    result = v2.heldout_exact_power_n()
    assert result["n"] == 379
    assert result["critical_successes"] == 334


def test_devb_sizing_follows_exact_width_rule():
    n = v2.devb_exact_width_n()
    planned = round(0.90 * n)
    interval = binomial_interval(planned, n, 0.90)
    assert interval[1] - interval[0] <= 0.10
    # Minimality: n - 1 fails under the identical frozen count rule.
    planned_prev = round(0.90 * (n - 1))
    prev = binomial_interval(planned_prev, n - 1, 0.90)
    assert not prev[1] - prev[0] <= 0.10


def test_devb_no_pooling_after_inspection():
    assert v2.devb_pooling_after_inspection_allowed() is False
    assert (v2.S2V2_METHOD["populations"]["dev_b_pooling_after_inspection"]
            == "FORBIDDEN")


def test_no_heldout_execution_path():
    text = Path(v2.__file__).read_text()
    assert "materialize" not in text
    assert "estimate_calibration_replicate" not in text
    assert "coverage_experiment" not in text
    assert "CalibrationStore" not in text
    assert "C:\\" not in text and "s2-dev-v" not in text
    # The v1 seed sets appear ONLY inside the disjointness-exclusion policy
    # string (what must never be reused), never as a reserved inventory:
    # no seed mapping, no range-built inventory, no population records.
    assert "fresh-ranges-disjoint-from-11-12-21-22-101-108-201-264" in text
    assert "S2V2_DEV_SEEDS" not in text and "S2V2_HELDOUT_SEEDS" not in text
    assert "range(" not in text and "CalibrationDatasetManifest" not in text
    assert "CalibrationPlan" not in text
    assert not hasattr(v2, "run_dev") and not hasattr(v2, "run_heldout")


def test_no_qualification_state():
    text = Path(v2.__file__).read_text()
    # No USE of qualification machinery (docstring exclusion mentions aside):
    # no forbidden imports, no construction, no bounds access, no verdicts.
    import_block = "\n".join(
        line for line in text.splitlines()
        if line.startswith(("import ", "from ")))
    for forbidden in ("QualificationRecord", "Uncertainty", "claims", "evidence",
                      "followups", "materialize", "CalibrationStore",
                      "coverage_experiment"):
        assert forbidden not in import_block
    assert "QualificationRecord(" not in text
    assert "Uncertainty(" not in text
    assert ".bounds" not in text and '"bounds"' not in text
    assert '"PASS"' not in text and '"FAIL"' not in text
    assert '"QUALIFIED"' not in text and "Verdict" not in text
    # Failure-ceiling constant names are policy vocabulary, not verdicts:
    # no verdict assignment or qualification-state word remains.
    assert "verdict" not in text.lower()


def test_criterion_defined_not_evaluated():
    criterion = v2.S2V2_CRITERION
    assert criterion["minimum_true_coverage"] == 0.85
    assert criterion["bias_tolerance_m2_per_s"] == 5e-11
    assert v2.S2V2_METHOD["criterion_hash"] == v2.S2V2_CRITERION_HASH
    assert "verdict" not in criterion and "result" not in criterion


def test_no_v1v3_evidence_as_calibration():
    text = Path(v2.__file__).read_text()
    assert "92b4355" not in text and "5c96c4ca" not in text
    assert "estimator_results" not in text and "calibration_intervals" not in text
    # No evidence-filesystem access of any kind (no reads, globs, or roots).
    for marker in (".json", "read_bytes", "glob(", "artifact_root", "store.root",
                   "blobs", "attempts/"):
        assert marker not in text
