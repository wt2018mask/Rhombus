"""Strictly metadata-only, *hypothetical* group-risk power envelope for Tier A.

This is a statistical **planning impossibility check**, not a calibration,
confidence claim about real source groups, or benchmark freeze. It never reads
energy targets, predicts migration energies, or authorizes execution.

The one-sided zero-event binomial upper bound assumes IID group Bernoulli
failures, a selected hypothesis, and independent pre-registered testing.
LiTraj chemsys labels DO NOT prove such independence or model train separation.
"""
from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Mapping

from .tier_a_preflight import FIELDS, SCHEMA as REGISTRY_SCHEMA, build_metadata_registry

SCHEMA = "rhombus-0205-tier-a-hypothetical-group-power-envelope-v1"
MAX_GROUPS = 100_000


def _fraction(x: Any, name: str) -> float:
    if type(x) not in (int, float) or not math.isfinite(x) or not 0 < x < 1:
        raise ValueError(f"{name}: STRICT_FRACTION_REQUIRED")
    return float(x)


def required_zero_event_groups(*, risk_target: float, confidence: float) -> int:
    """Minimum hypothetical independent zero-event groups for upper bound <= risk.

    This is a *best case* minimum, NOT a power guarantee when errors occur.
    """
    risk = _fraction(risk_target, "RISK_TARGET")
    conf = _fraction(confidence, "CONFIDENCE")
    if conf <= 0.5:
        raise ValueError("CONFIDENCE_MUST_EXCEED_ONE_HALF")
    # log1p prevents catastrophic cancellation for small risk.
    raw = math.log1p(-conf) / math.log1p(-risk)
    n = max(1, math.ceil(raw))
    if n > MAX_GROUPS:
        raise ValueError("REQUIRED_ZERO_ERROR_GROUPS_EXCEED_SUPPORTED_LIMIT")
    # Roundoff can cause ceil to be one group too pessimistic/optimistic.
    while n > 1 and one_sided_zero_event_upper(n - 1, confidence=conf) <= risk:
        n -= 1
    while one_sided_zero_event_upper(n, confidence=conf) > risk:
        n += 1
    return n


def one_sided_zero_event_upper(groups: int, *, confidence: float) -> float | None:
    """Exact one-sided Clopper-Pearson upper bound when observed events == 0.

    groups=0 has undefined risk, NEVER 0. No actual data supplied or inspected.
    """
    conf = _fraction(confidence, "CONFIDENCE")
    if conf <= 0.5:
        raise ValueError("CONFIDENCE_MUST_EXCEED_ONE_HALF")
    if type(groups) is not int or not 0 <= groups <= MAX_GROUPS:
        raise ValueError("INVALID_GROUP_COUNT")
    return None if groups == 0 else -math.expm1(math.log1p(-conf) / groups)


def _groups_from_verified_registry(registry: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, int], str]:
    if type(registry) is not dict or registry.get("schema_version") != REGISTRY_SCHEMA:
        raise ValueError("UNKNOWN_REGISTRY_SCHEMA")
    rows = registry.get("rows")
    if type(rows) is not list or not rows:
        raise ValueError("MISSING_REGISTRY_ROWS")
    try:
        originals = [{k: r[k] for k in FIELDS} for r in rows]
    except (KeyError, TypeError) as exc:
        raise ValueError("REGISTRY_METADATA_FIELDS_REQUIRED") from exc
    canonical = build_metadata_registry(originals)
    if registry != canonical:
        raise ValueError("REGISTRY_COUNT_OR_GROUP_TAMPERING")
    retained = dict(canonical["counts"]["retained_groups"])
    memberships: dict[str, set[str]] = defaultdict(set)
    for r in originals:
        memberships[r["chemsys"]].add(r["published_split"])
    # An *alternative sensitivity only*: groups unshared in original splits.
    strict = {split: 0 for split in ("train", "val", "test")}
    for splits in memberships.values():
        if len(splits) == 1:
            strict[next(iter(splits))] += 1
    return retained, strict, canonical["rows_sha256"]


def _scenario(groups: int, n_needed: int, confidence: float) -> dict[str, Any]:
    if type(groups) is not int or not 0 <= groups <= MAX_GROUPS:
        raise ValueError("INVALID_GROUP_COUNT")
    feasible = groups >= n_needed
    return {
        "retained_chemsys_groups": groups,
        "optimistic_upper_risk_if_every_group_accepted_and_zero_failures":
            one_sided_zero_event_upper(groups, confidence=confidence),
        "min_zero_failure_accepted_groups_for_target": n_needed,
        "zero_failure_bound_attainable_with_available_groups_in_IID_idealization": feasible,
        "minimum_required_group_coverage_in_IID_zero_failure_idealization":
            n_needed / groups if feasible else None,
        "observed_risk": None,
        "evidence_of_IID": False,
        "scientific_claim_allowed": False,
    }


def metadata_only_power_envelope(
    registry: Mapping[str, Any], *, risk_target: float, confidence: float
) -> dict[str, Any]:
    """State an optimistic feasibility limitation without reading any truth labels."""
    target = _fraction(risk_target, "RISK_TARGET")
    conf = _fraction(confidence, "CONFIDENCE")
    needed = required_zero_event_groups(risk_target=target, confidence=conf)
    retained, strict, digest = _groups_from_verified_registry(registry)
    out = {
        "schema_version": SCHEMA,
        "source_registry_rows_sha256": digest,
        "hypothesis_only": {"group_failure_risk_target": target,
                            "one_sided_confidence": conf,
                            "IID_accepted_group_bernoulli_assumption": "UNPROVEN",
                            "zero_observed_severe_errors_assumption": "HYPOTHETICAL_NOT_OBSERVED",
                            "minimum_accepted_groups_in_ideal_zero_failure_case": needed},
        "planned_train_pilot_four_groups": _scenario(4, needed, conf),
        "retained_chemsys_candidate": {key: _scenario(retained[key], needed, conf)
                                        for key in ("train", "val", "test")},
        "strict_exclusive_chemsys_sensitivity_only": {
            key: _scenario(strict[key], needed, conf) for key in ("train", "val", "test")},
        "independence_limits": [
            "CHEMSYS_GROUPS_ARE_NOT_ESTABLISHED_INDEPENDENT_MATERIALS_OR_SOURCES",
            "MODEL_TRAINING_OVERLAP_UNKNOWN",
            "WITHIN_GROUP_EDGE_CORRELATIONS_NOT_ACCOUNTED_FOR_BY_IID_BINOMIAL_FORMULA",
            "GROUP_COVERAGE_IS_NOT_EDGE_COVERAGE",
            "ZERO_FAILURE_SCENARIO_IS_THE_OPTIMISTIC_BEST_CASE_NOT_AN_OBSERVATION",
            "NO_INFERENCE_WITHOUT_PRE_REGISTERED_SELECTION_AND_SEALED_TEST_EVALUATION",
        ],
        "data_access": "ALLOWLIST_METADATA_ONLY_NO_DFT_OR_MLIP_TARGET_VALUES",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN",
        "execution_authorized": False,
    }
    return out
