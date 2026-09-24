"""Frozen S2 interval-procedure v2 method contract (Stage A: method only).

Prospective scientific content for the split-conformal v2 uncertainty
procedure. This module freezes the METHOD -- owner policy, conformal rule,
criterion content, failure semantics, and pure sample-size planning rules.

Explicitly NOT in Stage A (see two-stage identity below):
- fresh DEV-A / DEV-B / HELD_OUT populations (no seeds reserved here)
- the learned conformal quantile ``q_hat`` (Stage-B artifact; absence is
  represented explicitly as ``None``, never placeholder-hashed)
- any qualification result or record, or populated production uncertainty bounds
- any execution path (no materialization, estimation, or evaluation runs)

Two-stage identity boundary (enforced by construction, not by convention):
    PRE-DEV METHOD IDENTITY (this module; S2V2_METHOD_HASH)
        -> fresh DEV-A (later, separate evidence root)
    -> LEARNED CALIBRATION PACKAGE (Stage B, separately hash-bound)
    -> COMPLETE PRE-HELD_OUT IDENTITY (method + package + criterion +
       HELD_OUT inventory)
    -> blind HELD_OUT once (post-HELD_OUT tuning forbidden)

All values below are OWNER POLICY (fixed prospectively, never tuned from
historical v1/v3 outcomes) or exact mathematical derivations from that
policy. Historical v1 procedure hash appears as a provenance citation only.
"""

from __future__ import annotations

import math
from fractions import Fraction

from scipy.stats import beta, binom

from rudeus.execution.contracts import ExecutionError
from rudeus.science.calibration_estimator import ESTIMATOR_MODULE, ESTIMATOR_NAME
from rudeus.science.calibration_s1 import S1_ESTIMATOR_CONFIG, S1_TRUTH_D_M2_PER_S
from rudeus.science.contracts import digest
from rudeus.science.statistics import binomial_interval

# Owner-policy constants (Stage-A frozen; do not derive or change). ---------
S2V2_VERSION = "s2-interval-procedure-v2"
S2V2_INTERVAL_FORM = "two-sided"
S2V2_ARCHITECTURE = "split-conformal-independent-trajectories"
S2V2_SCORE_NAME = "absolute-estimator-error"
S2V2_TARGET_COVERAGE = 0.90
S2V2_ALPHA = 0.10  # 1 - target coverage, exact
S2V2_MINIMUM_COVERAGE = 0.85
S2V2_ALLOWED_SHORTFALL = 0.05
S2V2_HELDOUT_CONFIDENCE = 0.95  # one-sided exact Clopper-Pearson
S2V2_BIAS_METRIC = "abs-mean-signed-error"
S2V2_BIAS_TOLERANCE_M2_PER_S = 5.0e-11
S2V2_ABSTENTION_CEILING = 0
S2V2_EXECUTION_FAILURE_CEILING = 0
S2V2_ESTIMATOR_FAILURE_CEILING = 0
S2V2_INTERVAL_FAILURE_CEILING = 0
S2V2_COVERAGE_RESOLUTION = 0.01  # 1 / (n_A + 1) <= resolution
S2V2_DEVB_CONFIDENCE = 0.90  # two-sided exact binomial CI
S2V2_DEVB_MAX_WIDTH = 0.10  # planned maximum total CI width
S2V2_DEVB_PLANNING_P = 0.90
S2V2_HELDOUT_P_TRUE = 0.90  # planning alternative (nominal target, not boundary)
S2V2_HELDOUT_TARGET_POWER = 0.90
S2V2_V1_PROCEDURE_HASH = (
    "088688e9ab8388dcc13a0cf2b23264d3d53e6f3d75b024ea5a46b49b449e0cf8"
)


def _fail(message):
    raise ExecutionError(message, "INTEGRITY")


def assert_frozen_v2_policy():
    """Verify the frozen Stage-A owner policy before any v2 use."""
    if S2V2_VERSION != "s2-interval-procedure-v2":
        _fail("S2 v2 procedure version is not the frozen value")
    if S2V2_TARGET_COVERAGE != 0.90 or S2V2_ALPHA != 0.10:
        _fail("S2 v2 target coverage is not the frozen owner policy")
    if S2V2_MINIMUM_COVERAGE != 0.85 or S2V2_ALLOWED_SHORTFALL != 0.05:
        _fail("S2 v2 minimum coverage policy is not frozen")
    if S2V2_HELDOUT_CONFIDENCE != 0.95:
        _fail("S2 v2 HELD_OUT confidence is not frozen")
    if S2V2_BIAS_TOLERANCE_M2_PER_S != 5e-11:
        _fail("S2 v2 bias tolerance is not frozen")
    if (S2V2_ABSTENTION_CEILING != 0 or S2V2_EXECUTION_FAILURE_CEILING != 0
            or S2V2_ESTIMATOR_FAILURE_CEILING != 0
            or S2V2_INTERVAL_FAILURE_CEILING != 0):
        _fail("S2 v2 Brownian failure ceilings are not frozen at zero")
    if S2V2_SCORE_NAME != "absolute-estimator-error":
        _fail("S2 v2 conformal score is not frozen")
    if S2V2_COVERAGE_RESOLUTION != 0.01:
        _fail("S2 v2 DEV-A planning resolution is not frozen")
    if digest(S2V2_V1_PROCEDURE_HASH) == digest(S2V2_METHOD):
        _fail("S2 v2 identity collides with the v1 citation")
    if S2V2_METHOD_HASH != digest(S2V2_METHOD):
        _fail("S2 v2 method identity hash mismatch")
    if S2V2_CRITERION_HASH != digest(S2V2_CRITERION):
        _fail("S2 v2 criterion identity hash mismatch")


def conformal_rank(n, *, target_coverage=S2V2_TARGET_COVERAGE):
    """Exact split-conformal rank: k = ceil((n + 1) * target).

    Uses exact rational arithmetic (never float multiplication) so ranks at
    exact decimal targets (e.g. 0.90) are correct by construction.

    Raises ExecutionError carrying INSUFFICIENT EVIDENCE status when
    ``k > n`` (quantile does not exist): callers must abstain, never fall
    back to a naive percentile or the maximum score.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ExecutionError("conformal calibration size must be a positive integer",
                             "UNSUPPORTED_INPUT")
    try:
        target = Fraction(str(target_coverage))
    except (ValueError, ArithmeticError) as exc:
        raise ExecutionError(f"conformal target coverage is invalid: {exc}",
                             "UNSUPPORTED_INPUT") from exc
    if not 0 < target < 1:
        raise ExecutionError("conformal target coverage must lie in (0, 1)",
                             "UNSUPPORTED_INPUT")
    rank = math.ceil((n + 1) * target)
    if rank > n:
        raise ExecutionError(
            f"conformal rank k={rank} exceeds n={n} at target {float(target)}: "
            "INSUFFICIENT EVIDENCE (calibration cannot be constructed)",
            "UNSUPPORTED_INPUT")
    return rank


def conformal_quantile_from_scores(scores, *, target_coverage=S2V2_TARGET_COVERAGE):
    """Frozen conformal rule applied to EXPLICITLY SUPPLIED scores.

    Returns the k-th ascending order statistic (k from conformal_rank).
    Closed-interval semantics: equality counts as covered; ties need no
    statistical tie-break (equal values are interchangeable); canonical
    ascending sort keeps provenance reproducible. NaN/non-finite scores are
    rejected. This is the frozen RULE, not learned calibration: Stage A
    never supplies DEV scores, so it never learns q_hat.
    """
    values = list(scores)
    if len(values) < 1:
        raise ExecutionError("conformal calibration requires at least one score",
                             "UNSUPPORTED_INPUT")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values):
        raise ExecutionError("conformal scores must be numeric", "UNSUPPORTED_INPUT")
    import math as _math
    if any(not _math.isfinite(v) for v in values):
        raise ExecutionError("conformal scores must be finite", "UNSUPPORTED_INPUT")
    rank = conformal_rank(len(values), target_coverage=target_coverage)
    return sorted(values)[rank - 1]


def exact_one_sided_lcb(successes, total, confidence):
    """Exact one-sided Clopper-Pearson lower confidence bound."""
    if (isinstance(successes, bool) or isinstance(total, bool)
            or not isinstance(successes, int) or not isinstance(total, int)):
        raise ExecutionError("binomial counts must be integers", "UNSUPPORTED_INPUT")
    if not 0 <= successes <= total or total < 1:
        raise ExecutionError("invalid binomial counts", "UNSUPPORTED_INPUT")
    if not 0 < confidence < 1:
        raise ExecutionError("confidence must lie in (0, 1)", "UNSUPPORTED_INPUT")
    if successes == 0:
        return 0.0
    return float(beta.ppf(1 - confidence, successes, total - successes + 1))


def calibration_minimum_n(coverage_resolution=S2V2_COVERAGE_RESOLUTION):
    """Smallest n with 1 / (n + 1) <= coverage_resolution (exact rational).

    Bounds the split-conformal finite-sample overshoot price 1/(n+1).
    Frozen policy resolution 0.01 derives n_A >= 99.
    """
    try:
        resolution = Fraction(str(coverage_resolution))
    except (ValueError, ArithmeticError) as exc:
        raise ExecutionError(f"coverage resolution is invalid: {exc}",
                             "UNSUPPORTED_INPUT") from exc
    if not 0 < resolution < 1:
        raise ExecutionError("coverage resolution must lie in (0, 1)",
                             "UNSUPPORTED_INPUT")
    # n = ceil(1/resolution - 1), exact via integer arithmetic.
    numerator, denominator = (1 / resolution).numerator, (1 / resolution).denominator
    minimum = -(-numerator // denominator) - 1
    return int(minimum)


def devb_exact_width_n(*, planning_p=S2V2_DEVB_PLANNING_P,
                       confidence=S2V2_DEVB_CONFIDENCE,
                       max_total_width=S2V2_DEVB_MAX_WIDTH):
    """Smallest n whose exact two-sided Clopper-Pearson CI width <= maximum.

    Planning-count rule (predeclared, exact-verified): for candidate n the
    planned success count is x_n = round(planning_p * n) (the expected
    outcome under the planning assumption), clamped to [0, n]; the width is
    the exact two-sided Clopper-Pearson interval at that count via the
    repository's binomial_interval. Search ascends from n = 1, so the
    returned n is minimal for this rule by construction. Pure function: no
    filesystem, no observed data.
    """
    for name, value in (("planning_p", planning_p), ("confidence", confidence)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ExecutionError(f"DEV-B planning {name} must be numeric",
                                 "UNSUPPORTED_INPUT")
    if not 0 < planning_p < 1 or not 0 < confidence < 1:
        raise ExecutionError("DEV-B planning probabilities must lie in (0, 1)",
                             "UNSUPPORTED_INPUT")
    if not max_total_width > 0:
        raise ExecutionError("DEV-B maximum width must be positive", "UNSUPPORTED_INPUT")
    n = 1
    while True:
        planned = min(max(int(round(planning_p * n)), 0), n)
        interval = binomial_interval(planned, n, confidence)
        if interval[1] - interval[0] <= max_total_width:
            return n
        n += 1


def heldout_exact_power_n(*, p_true=S2V2_HELDOUT_P_TRUE,
                          minimum_coverage=S2V2_MINIMUM_COVERAGE,
                          one_sided_confidence=S2V2_HELDOUT_CONFIDENCE,
                          target_power=S2V2_HELDOUT_TARGET_POWER):
    """Smallest n passing the blind rule with at least target power.

    For each candidate n (ascending from 1): x* = smallest success count
    whose exact one-sided Clopper-Pearson lower bound >= minimum_coverage
    (bound monotone in x; located by bisection); pass probability =
    P[X >= x* | Binomial(n, p_true)] via the exact binomial tail. First n
    with pass probability >= target_power is returned with its critical
    count, bound, and power. Pure function: no filesystem, no observed data.
    """
    for name, value in (("p_true", p_true), ("minimum_coverage", minimum_coverage),
                        ("one_sided_confidence", one_sided_confidence),
                        ("target_power", target_power)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ExecutionError(f"HELD_OUT planning {name} must be numeric",
                                 "UNSUPPORTED_INPUT")
    if not 0 < p_true < 1 or not 0 < minimum_coverage < 1:
        raise ExecutionError("HELD_OUT planning coverages must lie in (0, 1)",
                             "UNSUPPORTED_INPUT")
    if not 0 < one_sided_confidence < 1 or not 0 < target_power < 1:
        raise ExecutionError("HELD_OUT confidence/power must lie in (0, 1)",
                             "UNSUPPORTED_INPUT")
    if not p_true > minimum_coverage:
        raise ExecutionError(
            "HELD_OUT planning is infeasible for p_true <= minimum_coverage: "
            "INSUFFICIENT EVIDENCE (no sample size can deliver power against "
            "a deficit that does not exist)",
            "UNSUPPORTED_INPUT")
    n = 1
    while True:
        # Bisection for x*: LCB is nondecreasing in successes.
        low, high, critical = 0, n, None
        while low <= high:
            mid = (low + high) // 2
            if exact_one_sided_lcb(mid, n, one_sided_confidence) >= minimum_coverage:
                critical, high = mid, mid - 1
            else:
                low = mid + 1
        if critical is None:  # even n/n cannot pass; larger n required
            n += 1
            continue
        bound = exact_one_sided_lcb(critical, n, one_sided_confidence)
        power = float(binom.sf(critical - 1, n, p_true))
        if power >= target_power:
            return {"n": n, "critical_successes": critical,
                    "lcb_at_critical": bound, "power": power}
        n += 1


def devb_pooling_after_inspection_allowed():
    """Whether DEV-B may be pooled into DEV-A after its results are seen.

    Always False: refitting the quantile on DEV-A + DEV-B after inspecting
    DEV-B outcomes conditions the calibration set on its own validation
    result and destroys prospectiveness. Any DEV-B-motivated change requires
    a NEW procedure version with fresh evidence. Policy-as-code so the rule
    is frozen, not merely documented.
    """
    return False


def build_s2v2_criterion():
    """Prospective qualification-criterion CONTENT (definition only).

    No evaluation, no result, and no qualification outcome state. The digest of
    this mapping is the criterion identity bound into the method contract.
    """
    return {
        "version": "s2-v2-criterion-v1",
        "coverage_rule": "exact-one-sided-CP-LCB",
        "minimum_true_coverage": S2V2_MINIMUM_COVERAGE,
        "one_sided_confidence": S2V2_HELDOUT_CONFIDENCE,
        "target_marginal_coverage": S2V2_TARGET_COVERAGE,
        "bias_rule": "abs-mean-signed-error",
        "bias_metric": S2V2_BIAS_METRIC,
        "bias_tolerance_m2_per_s": S2V2_BIAS_TOLERANCE_M2_PER_S,
        "abstention_ceiling": S2V2_ABSTENTION_CEILING,
        "execution_failure_ceiling": S2V2_EXECUTION_FAILURE_CEILING,
        "estimator_failure_ceiling": S2V2_ESTIMATOR_FAILURE_CEILING,
        "interval_failure_ceiling": S2V2_INTERVAL_FAILURE_CEILING,
        "integrity_policy": "zero-tolerance-package-invalid",
        "out_of_scope_policy": "abstain-never-extrapolate-tracked-separately",
    }


S2V2_CRITERION = build_s2v2_criterion()
S2V2_CRITERION_HASH = digest(S2V2_CRITERION)


def build_s2v2_method():
    """PRE-DEV v2 method identity content (no learned calibration inside).

    ``calibration_package`` is explicitly None: Stage B binds the learned
    quantile under a separate hash. The v1 procedure hash is a provenance
    citation only (``enters_calibration: False``): v1/v3 evidence must never
    enter v2 calibration.
    """
    return {
        "version": S2V2_VERSION,
        "interval_form": S2V2_INTERVAL_FORM,
        "architecture": S2V2_ARCHITECTURE,
        "score": {
            "name": S2V2_SCORE_NAME,
            "definition": "s_i = abs(D_hat_i - D_true)",
            "future_interval": "[D_hat_new - q_hat, D_hat_new + q_hat]",
            "interval_closure": "closed-equality-counts-as-covered",
            "tie_policy": "no-statistical-tie-break-required",
            "ordering": "canonical-ascending-sort",
        },
        "conformal_rule": {
            "alpha": S2V2_ALPHA,
            "target_coverage": S2V2_TARGET_COVERAGE,
            "rank": "ceil((n + 1) * target_coverage)",
            "rank_arithmetic": "exact-rational",
            "small_n_policy": "INSUFFICIENT-EVIDENCE-abstain-no-fallback",
            "forbidden_substitutes": ["naive-empirical-quantile", "max-score-fallback"],
        },
        "target_coverage": S2V2_TARGET_COVERAGE,
        "criterion_hash": S2V2_CRITERION_HASH,
        "estimator": {
            "name": ESTIMATOR_NAME,
            "module": ESTIMATOR_MODULE,
            "config": dict(S1_ESTIMATOR_CONFIG),
            "config_hash": digest(dict(S1_ESTIMATOR_CONFIG)),
        },
        "truth": {"type": "ANALYTICAL", "interpretation": "ensemble/long-time/bulk",
                  "value": {"D_m2_per_s": S1_TRUTH_D_M2_PER_S}, "units": "m2/s"},
        "scope": {"descriptor": "S1-isotropic-Brownian-scope-verbatim",
                  "parameter_cell": "cell-a",
                  "calibration_class": "isotropic_brownian"},
        "generator_protocol": {"generator": "brownian", "version": "synthetic-v1",
                               "trajectory_geometry": "8-frames-2-ions-1ps",
                               "seed_policy": "fresh-disjoint-committed-range"},
        "populations": {
            "dev_a_role": "learn-conformal-quantile",
            "dev_b_role": "independent-descriptive-validation-never-qualification",
            "dev_b_pooling_after_inspection": "FORBIDDEN",
            "heldout_role": "single-blind-confirmatory-qualification",
            "seed_policy": "fresh-ranges-disjoint-from-11-12-21-22-101-108-201-264",
        },
        "planning": {
            "coverage_resolution": S2V2_COVERAGE_RESOLUTION,
            "dev_b": {"planning_p": S2V2_DEVB_PLANNING_P,
                      "confidence_two_sided": S2V2_DEVB_CONFIDENCE,
                      "max_total_width": S2V2_DEVB_MAX_WIDTH,
                      "count_rule": "round(planning_p-times-n)-exact-verified-minimal"},
            "heldout": {"p_true": S2V2_HELDOUT_P_TRUE,
                        "minimum_coverage": S2V2_MINIMUM_COVERAGE,
                        "one_sided_confidence": S2V2_HELDOUT_CONFIDENCE,
                        "target_power": S2V2_HELDOUT_TARGET_POWER,
                        "rule": "exact-binomial-power-ascending-minimal"},
        },
        "bias": {"metric": S2V2_BIAS_METRIC,
                 "tolerance_m2_per_s": S2V2_BIAS_TOLERANCE_M2_PER_S},
        "abstention_policy": {
            "in_scope_ceiling": S2V2_ABSTENTION_CEILING,
            "on_occurrence": "investigation-hold-INSUFFICIENT-EVIDENCE",
            "out_of_scope": "abstain-never-extrapolate-tracked-separately",
        },
        "operational_policy": {
            "execution_ceiling": S2V2_EXECUTION_FAILURE_CEILING,
            "estimator_ceiling": S2V2_ESTIMATOR_FAILURE_CEILING,
            "interval_ceiling": S2V2_INTERVAL_FAILURE_CEILING,
            "integrity": "zero-tolerance-package-invalid",
        },
        "post_heldout_tuning": "FORBIDDEN",
        "calibration_package": None,  # STAGE-B ABSENT: bound separately, never here
        "historical_v1": {"procedure_hash": S2V2_V1_PROCEDURE_HASH,
                          "role": "provenance-citation-only",
                          "enters_calibration": False},
    }


S2V2_METHOD = build_s2v2_method()
S2V2_METHOD_HASH = digest(S2V2_METHOD)

# Stage-A learned-content absence, explicit (Stage B binds q_hat separately).
S2V2_CALIBRATION_PACKAGE = None


__all__ = [
    "S2V2_VERSION", "S2V2_TARGET_COVERAGE", "S2V2_ALPHA", "S2V2_MINIMUM_COVERAGE",
    "S2V2_ALLOWED_SHORTFALL", "S2V2_HELDOUT_CONFIDENCE", "S2V2_BIAS_METRIC",
    "S2V2_BIAS_TOLERANCE_M2_PER_S", "S2V2_ABSTENTION_CEILING",
    "S2V2_EXECUTION_FAILURE_CEILING", "S2V2_ESTIMATOR_FAILURE_CEILING",
    "S2V2_INTERVAL_FAILURE_CEILING", "S2V2_COVERAGE_RESOLUTION",
    "S2V2_DEVB_CONFIDENCE", "S2V2_DEVB_MAX_WIDTH", "S2V2_DEVB_PLANNING_P",
    "S2V2_HELDOUT_P_TRUE", "S2V2_HELDOUT_TARGET_POWER", "S2V2_V1_PROCEDURE_HASH",
    "S2V2_METHOD", "S2V2_METHOD_HASH", "S2V2_CRITERION", "S2V2_CRITERION_HASH",
    "S2V2_CALIBRATION_PACKAGE", "assert_frozen_v2_policy", "build_s2v2_criterion",
    "build_s2v2_method", "calibration_minimum_n", "conformal_quantile_from_scores",
    "conformal_rank", "devb_exact_width_n", "devb_pooling_after_inspection_allowed",
    "exact_one_sided_lcb", "heldout_exact_power_n",
]
