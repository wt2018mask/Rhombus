"""Tier-A decision-policy *design* and strictly synthetic denominator diagnostics.

This module never opens LiTraj, loads models, reads real targets or authorizes
compute. Its fixture diagnostic accepts synthetic *boolean* error indicators
only, not energies or predictions. Nothing here qualifies the science.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
import math
from statistics import NormalDist
from typing import Any, Mapping

from .tier_a_budget_contract import inspect_budget_draft, REQUIRED_MODEL_IDS

SCHEMA = "rhombus-0204-tier-a-selective-decision-design-v1"
FIXTURE_SCHEMA = "rhombus-0204-tier-a-synthetic-paired-decision-v1"
DECISIONS = ("ACCEPT", "ABSTAIN", "ESCALATE")
OUTCOMES = ("CONVERGED", "NONCONVERGED", "TIMEOUT", "OUT_OF_MEMORY", "MODEL_ERROR", "INPUT_INVALID")
CONFIDENCE = 0.95
MAX_SYNTHETIC_EDGES = 1000
MAX_GROUPS = 1000


def _shape(obj: Any, required: tuple[str, ...], where: str) -> None:
    if type(obj) is not dict or set(obj) != set(required):
        raise ValueError(f"{where}: EXACT_FIELDS_REQUIRED")


def _hash(obj: Any) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def make_decision_design(budget_draft: Mapping[str, Any]) -> dict[str, Any]:
    """Bind a policy-design draft to an existing non-executable budget contract.

    Numeric severity, target risk and coverage choices remain unset until
    *separate owner preregistration*. This does NOT freeze the benchmark.
    """
    inspect_budget_draft(budget_draft)
    return {
        "schema_version": SCHEMA,
        "task": "TIER_A_RETROSPECTIVE_LI_HOP_ENERGY_SPAN",
        "observable": "max(E_images)-min(E_images); NONDIRECTIONAL_DISCRETE_NEB_SPAN",
        "budget_draft_sha256": _hash(budget_draft),
        "source_sha256": budget_draft["source_sha256"],
        "registry_rows_sha256": budget_draft["registry_rows_sha256"],
        "model_arms": sorted(x["arm_id"] for x in budget_draft["model_arms"]),
        "group_unit": "CHEMSYS; NOT_PROTOTYPE_OR_INDEPENDENT_SOURCE",
        "decision_inputs": "PRE_REFERENCE_ONLY; PREDICTION_UNCERTAINTY_AND_APPLICABILITY",
        "decision_set": list(DECISIONS),
        "failure_policy": "ALL_PLANNED_ARM_EDGE_PAIRS_IN_DENOMINATOR; FAILURE_NOT_ACCEPT",
        "decision_rules": {
            "accept_rule": "PRE_REGISTERED_UNCERTAINTY_AND_APPLICABILITY; NO_REFERENCE_LOOKUP",
            "abstain_rule": "NO_VALID_PREDICTION_OR_UNQUALIFIED_APPLICABILITY",
            "escalate_rule": "PRE_REGISTERED_HIGHER_FIDELITY_REQUEST; NOT_AUTO_EXECUTED",
        },
        "owner_review": {
            "severe_error_delta_eV": None,
            "maximum_false_accept_risk": None,
            "minimum_coverage": None,
            "confidence_level": CONFIDENCE,
            "uncertainty_threshold": None,
            "escalation_cost_budget_cpu_seconds": None,
            "group_resampling_plan": "CHEMSYS_CLUSTER; SOURCE_INDEPENDENCE_UNVERIFIED",
        },
        "model_overlap": "UNKNOWN_TRAINING_OVERLAP",
        "reference_access": "SEALED; NO_VALIDATION_OR_TEST_ENERGY_ACCESS",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "scientific_verdict": "SCIENTIFIC_NO_GO_ABSTAIN",
        "execution_authorized": False,
        "result_qualification": "NOT_EVALUATED",
    }


def inspect_decision_design(design: Mapping[str, Any], budget_draft: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on draft tampering. Even a filled owner sheet cannot authorize execution."""
    _shape(design, ("schema_version", "task", "observable", "budget_draft_sha256",
                   "source_sha256", "registry_rows_sha256", "model_arms", "group_unit",
                   "decision_inputs", "decision_set", "failure_policy", "decision_rules",
                   "owner_review", "model_overlap", "reference_access", "benchmark_status",
                   "scientific_verdict", "execution_authorized", "result_qualification"), "DESIGN")
    expected = make_decision_design(budget_draft)
    for key in expected:
        if key == "owner_review":
            continue
        if design[key] != expected[key]:
            raise ValueError(f"DESIGN_TAMPERING_{key}")
    review = design["owner_review"]
    _shape(review, tuple(expected["owner_review"]), "OWNER_REVIEW")
    if (review["confidence_level"] != CONFIDENCE
            or review["group_resampling_plan"] != expected["owner_review"]["group_resampling_plan"]):
        raise ValueError("GROUP_UNCERTAINTY_CONTRACT_CHANGED")
    missing = []
    for key in ("severe_error_delta_eV", "maximum_false_accept_risk", "minimum_coverage",
                "uncertainty_threshold", "escalation_cost_budget_cpu_seconds"):
        x = review[key]
        if x is None:
            missing.append(key)
            continue
        if type(x) not in (int, float) or not math.isfinite(x):
            raise ValueError(f"INVALID_OWNER_THRESHOLD_{key}")
        if key in ("maximum_false_accept_risk", "minimum_coverage"):
            if not 0 < x < 1:
                raise ValueError(f"INVALID_OWNER_THRESHOLD_{key}")
        elif x <= 0:
            raise ValueError(f"INVALID_OWNER_THRESHOLD_{key}")
    if not set(design["model_arms"]) == REQUIRED_MODEL_IDS:
        raise ValueError("MODEL_ARM_SET_CHANGED")
    return {
        "schema_version": SCHEMA,
        "draft_integrity_valid": True,
        "status": "CANDIDATE_ONLY_NEVER_FROZEN",
        "owner_thresholds_missing": missing,
        "requires_independent_pre_registration": True,
        "training_overlap": "UNKNOWN",
        "risk_confidence_intervals_qualified": False,
        "execution_authorized": False,
        "scientific_verdict": "SCIENTIFIC_NO_GO_ABSTAIN",
    }


def _wilson(success: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    z = NormalDist().inv_cdf((1 + CONFIDENCE) / 2)
    p = success / total
    d = 1 + z * z / total
    c = (p + z * z / (2 * total)) / d
    r = z * math.sqrt(p * (1-p) / total + z*z/(4*total*total))/d
    return [max(0.0, c-r), min(1.0, c+r)]


def summarize_synthetic_paired_decisions(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Test accounting mathematics on *synthetic* arm/edge pairs ONLY.

    No physical energies or model predictions are accepted. Source/prototype
    independence is NOT established and interval output is descriptive only.
    """
    _shape(fixture, ("schema_version", "scope", "model_arms", "planned_edges", "rows"), "FIXTURE")
    if fixture["schema_version"] != FIXTURE_SCHEMA or fixture["scope"] != "SYNTHETIC_ONLY_NO_REAL_LABELS":
        raise ValueError("REAL_DATA_SCORING_FORBIDDEN")
    if type(fixture["model_arms"]) is not list or set(fixture["model_arms"]) != REQUIRED_MODEL_IDS or len(fixture["model_arms"]) != 2:
        raise ValueError("INCORRECT_PAIRED_MODEL_ROLES")
    planned = fixture["planned_edges"]
    if type(planned) is not list or not 2 <= len(planned) <= MAX_SYNTHETIC_EDGES:
        raise ValueError("INVALID_PRECOMMITTED_SYNTHETIC_UNIVERSE")
    committed = {}
    for entry in planned:
        _shape(entry, ("edge_id", "group_id"), "PLANNED_EDGE")
        edge, group = entry["edge_id"], entry["group_id"]
        if (type(edge) is not str or not edge.startswith("synthetic-") or not 11 <= len(edge) <= 100
                or type(group) is not str or not group.startswith("CHEMSYS:")
                or not 8 <= len(group) <= 120 or edge in committed):
            raise ValueError("INVALID_OR_DUPLICATED_PLANNED_EDGE")
        committed[edge] = group
    if len(set(committed.values())) < 2:
        raise ValueError("INSUFFICIENT_SYNTHETIC_CHEMICAL_GROUPS")
    rows = fixture["rows"]
    if type(rows) is not list or not 4 <= len(rows) <= MAX_SYNTHETIC_EDGES * 2 or len(rows) % 2:
        raise ValueError("INVALID_SYNTHETIC_PAIR_COUNT")
    arms = set(fixture["model_arms"])
    keys, groups_by_edge, observations = set(), {}, defaultdict(list)
    for row in rows:
        _shape(row, ("edge_id", "group_id", "arm_id", "decision", "run_outcome",
                     "severe_error", "cpu_seconds"), "SYNTHETIC_ROW")
        edge, group, arm = row["edge_id"], row["group_id"], row["arm_id"]
        if (type(edge) is not str or not edge.startswith("synthetic-")
                or not 11 <= len(edge) <= 100 or type(group) is not str or not group.startswith("CHEMSYS:")
                or not 8 <= len(group) <= 120 or arm not in arms):
            raise ValueError("INVALID_SYNTHETIC_IDENTIFIERS")
        if (edge, arm) in keys:
            raise ValueError("DUPLICATE_PAIRED_EDGE_ARM")
        keys.add((edge, arm))
        if edge not in committed or committed[edge] != group:
            raise ValueError("EDGE_GROUP_INCONSISTENCY")
        if edge in groups_by_edge and groups_by_edge[edge] != group:
            raise ValueError("EDGE_GROUP_INCONSISTENCY")
        groups_by_edge[edge] = group
        decision, outcome = row["decision"], row["run_outcome"]
        if decision not in DECISIONS or outcome not in OUTCOMES:
            raise ValueError("INVALID_DECISION_OR_OUTCOME")
        if (outcome != "CONVERGED" and decision == "ACCEPT"):
            raise ValueError("FAILED_RUN_CANNOT_BE_ACCEPTED")
        sev = row["severe_error"]
        if (decision == "ACCEPT" and type(sev) is not bool) or (decision != "ACCEPT" and sev is not None):
            raise ValueError("SYNTHETIC_SEVERITY_ONLY_FOR_ACCEPTED")
        cost = row["cpu_seconds"]
        if type(cost) not in (int, float) or not math.isfinite(cost) or not 0 <= cost <= 1e10:
            raise ValueError("INVALID_SYNTHETIC_COST")
        observations[arm].append(row)
    if len(groups_by_edge) > MAX_GROUPS or len(set(groups_by_edge.values())) < 2:
        raise ValueError("INSUFFICIENT_OR_TOO_MANY_SYNTHETIC_GROUPS")
    expected = {(edge, arm) for edge in committed for arm in arms}
    if keys != expected:
        raise ValueError("MISSING_PAIRED_ARM_EDGE_OR_UNREPORTED_FAILURE")
    summary = {}
    accepted_sets = {}
    for arm in sorted(arms):
        armrows=observations[arm]
        accepted=[row for row in armrows if row["decision"]=="ACCEPT"]
        accepted_sets[arm] = {row["edge_id"] for row in accepted}
        groupwise=defaultdict(list)
        for row in accepted:
            groupwise[row["group_id"]].append(row["severe_error"])
        any_bad=sum(any(vals) for vals in groupwise.values())
        group_count=len(groupwise)
        n = len(accepted)
        summary[arm]={
            "planned_edges": len(committed),
            "accepted_edges": n,
            "abstained_edges": sum(x["decision"]=="ABSTAIN" for x in armrows),
            "escalated_edges": sum(x["decision"]=="ESCALATE" for x in armrows),
            "failed_edges": sum(x["run_outcome"]!="CONVERGED" for x in armrows),
            "coverage_all_planned_edges": n / len(committed),
            "severe_error_fraction_accepted_edges": (sum(x["severe_error"] for x in accepted)/n if n else None),
            "risk_if_no_accepts": "UNDEFINED_NOT_ZERO" if n == 0 else None,
            "accepted_chemsys_groups": group_count,
            "groups_with_any_severe_error": any_bad,
            "group_any_severe_error_fraction": any_bad/group_count if group_count else None,
            "group_wilson_interval_DESCRIPTIVE_ONLY": _wilson(any_bad,group_count),
            "observed_cpu_seconds_all_edges_including_failures": sum(x["cpu_seconds"] for x in armrows),
        }
    paired_same= len({frozenset(v) for v in accepted_sets.values()})==1
    return {
        "schema_version": FIXTURE_SCHEMA,
        "scope": "SYNTHETIC_ONLY_NO_REAL_LABELS",
        "status": "FORMULA_AND_DENOMINATOR_DIAGNOSTIC_ONLY",
        "group_intervals_not_independent_certification": True,
        "chemistry_source_prototype_independence": "UNKNOWN",
        "pretrained_model_overlap": "UNKNOWN",
        "matched_coverage_decision_sets": paired_same,
        "can_claim_paired_superiority": False,
        "model_summaries": summary,
        "scientific_verdict": "SCIENTIFIC_NO_GO_ABSTAIN",
    }
