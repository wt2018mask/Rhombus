"""Exact finite-cohort label-reveal utility, not physical experiment dispatch.

All target values were exposed historically. Hypothetical measurement stress
is independent of 0196's training-label stress and is not measured uncertainty.
"""
from __future__ import annotations

import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import resource
import statistics
import time

from rhombus.evidence import (
    Applicability, DomainStatus, EvidenceRecord, OperationalStatus,
    ScientificVerdict, Uncertainty,
)
from rhombus.evidence.identity import SourceBinding

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = "data/development/observation_budget_0198_protocol_v1.json"
PROTOCOL_SHA256 = "00d60b81d8cc05dedff337e7849733db6982ea3855dd7c3ee0a848e1dbcebf2c"


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_study(root=ROOT):
    raw = (root / PROTOCOL_PATH).read_bytes()
    if _sha(raw) != PROTOCOL_SHA256:
        raise ValueError("frozen observation protocol changed")
    protocol = json.loads(raw)
    raw = (root / protocol["input_path"]).read_bytes()
    if _sha(raw) != protocol["input_sha256"]:
        raise ValueError("historical source receipt changed")
    source = json.loads(raw)
    checks = {
        "doi": protocol["doi"], "pdf_sha256": protocol["original_pdf_sha256"],
        "source_authenticity_status": "AUTHENTICATED_INSTITUTIONAL_PUBLISHER_VOR",
        "verification_status": "VERIFIED", "qualifies_0194_original_source": True,
        "table_2_all_18_values_exact_match": True, "table_2_condition_count": 18,
        "table_2_conductivity_target_temperature_C": 25,
        "single_directly_measured_25C_EIS_label_unattested": True,
        "scientific_GO": False, "production_enabled": False,
        "official_OBELiX_TEST_121_read": False,
    }
    if any(source.get(k) != v or type(source.get(k)) is not type(v) for k, v in checks.items()):
        raise ValueError("historical source identity or scientific scope mismatch")
    rows = source["table_mapping"]
    expected = {(s, t) for s in protocol["series"] for t in protocol["temperatures_C"]}
    actual = [(r["nominal_series"], r["hot_press_temperature_C"]) for r in rows]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError("missing, duplicate or unexpected source condition")
    for r in rows:
        value = r["total_ionic_conductivity_S_cm"]
        if (type(value) not in (int, float) or not math.isfinite(value) or value <= 0
                or type(r["author_reported_target_temperature_C"]) is not int
                or r["author_reported_target_temperature_C"] != 25):
            raise ValueError("invalid conductivity or measurement temperature")
    groups = [[r for r in rows if r["nominal_series"] == s] for s in protocol["series"]]
    return protocol, source, groups


def select_subsets(temperatures, budget, policy):
    """Metadata-only allocation: this function receives no outcome labels."""
    if (len(temperatures) != 3 or len(set(temperatures)) != 3
            or any(type(t) not in (int, float) or not math.isfinite(t) for t in temperatures)
            or type(budget) is not int or not 1 <= budget <= 3):
        raise ValueError("three finite unique temperatures and integer budget 1..3 required")
    if policy == "UNIFORM_WITHOUT_REPLACEMENT_EXACT":
        return list(combinations(range(3), budget))
    if policy not in ("HOTTEST_FIRST", "COLDEST_FIRST"):
        raise ValueError("unsupported observation policy")
    order = sorted(range(3), key=lambda i: temperatures[i], reverse=policy == "HOTTEST_FIRST")
    return [tuple(order[:budget])]


def score_subsets(conductivity, subsets, *, budget):
    if (len(conductivity) != 3 or any(type(v) not in (float, int)
            or not math.isfinite(v) or v <= 0 for v in conductivity)
            or type(budget) is not int or not 1 <= budget <= 3 or not subsets):
        raise ValueError("invalid conductivity or observation budget")
    logs = [math.log10(v) for v in conductivity]
    maximum = max(logs)
    observations = []
    for subset in subsets:
        if (len(subset) != budget or len(set(subset)) != budget
                or any(type(i) is not int or not 0 <= i < 3 for i in subset)):
            raise ValueError("invalid or over-budget observation subset")
        chosen = max(logs[i] for i in subset)
        observations.append({"observed_indices": list(subset),
                             "regret_log10": maximum - chosen,
                             "recovers_source_maximum": chosen == maximum})
    if len({tuple(sorted(s)) for s in subsets}) != len(subsets):
        raise ValueError("duplicate observation subset")
    return {
        "observation_budget": budget, "subsets_evaluated": len(observations),
        "expected_regret_log10": statistics.mean(o["regret_log10"] for o in observations),
        "worst_subset_regret_log10": max(o["regret_log10"] for o in observations),
        "source_maximum_recovery_fraction": statistics.mean(o["recovers_source_maximum"] for o in observations),
        "subset_results": observations,
    }


def assess_target_label_stress(conductivity, epsilons):
    if (len(conductivity) != 3 or any(type(v) not in (float, int)
            or not math.isfinite(v) or v <= 0 for v in conductivity)
            or not epsilons or any(type(e) not in (float, int)
                                  or not math.isfinite(e) or e < 0 for e in epsilons)):
        raise ValueError("finite positive conductivities and nonnegative stress required")
    ranked = sorted((math.log10(v), i) for i, v in enumerate(conductivity))
    gap = ranked[-1][0] - ranked[-2][0]
    radius = gap / 2
    return {
        "source_winner_index": ranked[-1][1] if gap > 0 else None,
        "top_runnerup_gap_log10": gap,
        "minimum_Linf_target_label_shift_to_tie_log10": radius,
        "is_measured_EIS_error": False,
        "stress_scenarios": [{"epsilon_log10": e, "unique_winner_certified": gap > 2 * e}
                             for e in epsilons],
    }


def run_study(root=ROOT):
    started, cpu_started = time.perf_counter(), time.process_time()
    protocol, source, groups = load_study(root)
    results, violations, strict_improvement = [], [], False
    for series, rows in zip(protocol["series"], groups):
        rows = sorted(rows, key=lambda r: r["hot_press_temperature_C"])
        temps = [r["hot_press_temperature_C"] for r in rows]
        values = [r["total_ionic_conductivity_S_cm"] for r in rows]
        policies = {}
        for budget in protocol["observation_budgets_per_series"]:
            policies[str(budget)] = {
                p: score_subsets(values, select_subsets(temps, budget, p), budget=budget)
                for p in protocol["policies"]
            }
            scores = policies[str(budget)]
            if budget < 3 and scores["HOTTEST_FIRST"]["expected_regret_log10"] > scores["UNIFORM_WITHOUT_REPLACEMENT_EXACT"]["expected_regret_log10"] + 1e-12:
                violations.append({"series": series, "budget": budget})
            if budget < 3 and scores["HOTTEST_FIRST"]["expected_regret_log10"] < scores["UNIFORM_WITHOUT_REPLACEMENT_EXACT"]["expected_regret_log10"] - 1e-12:
                strict_improvement = True
        results.append({"series": series, "policies": policies,
                        "target_label_stress": assess_target_label_stress(values, protocol["measurement_stress_epsilon_log10"])})
    aggregates = []
    for budget in protocol["observation_budgets_per_series"]:
        for policy in protocol["policies"]:
            scores = [r["policies"][str(budget)][policy] for r in results]
            aggregates.append({"budget_per_series": budget, "policy": policy,
                "series_count": 6, "source_group_count": 1,
                "nominal_label_reveals_across_series": budget * 6,
                "mean_series_expected_regret_log10": statistics.mean(s["expected_regret_log10"] for s in scores),
                "mean_series_maximum_recovery_fraction": statistics.mean(s["source_maximum_recovery_fraction"] for s in scores)})
    stress_failures = [r["series"] for r in results if not r["target_label_stress"]["stress_scenarios"][-1]["unique_winner_certified"]]
    evidence = EvidenceRecord.create(
        candidate_id="doi:" + protocol["doi"],
        evidence_kind="COMPUTED_RETROSPECTIVE_OBSERVATION_BUDGET",
        capability="assess_selection_utility",
        operational_status=OperationalStatus.SUCCEEDED,
        scientific_verdict=ScientificVerdict.INDETERMINATE,
        applicability=Applicability("manufacturing_selection", DomainStatus.UNQUALIFIED),
        uncertainty=Uncertainty(status="UNKNOWN", reason="Actual EIS error and specimen independence unverified"),
        limitations=("EXPOSED_ONE_SOURCE_RETROSPECTIVE_LABEL_REPLAY", "HYPOTHETICAL_STRESS_NOT_MEASURED_ERROR",
                     "NOMINAL_LABEL_REVEAL_COST_NOT_PHYSICAL_EXPERIMENT_COST", "NO_PREDICTION_OR_PRODUCTION_AUTHORIZATION"),
        protocol_id="observation-budget-0198-v1",
        source_bindings=(SourceBinding("INSTITUTIONAL_PUBLISHER_VOR", protocol["doi"], source["pdf_url"], source["pdf_sha256"]),),
        provenance={"protocol_sha256": PROTOCOL_SHA256, "source_receipt_sha256": protocol["input_sha256"]},
        payload={"H1_counterexamples": violations, "H2_uncertified_series_at_epsilon_0_1": stress_failures,
                 "aggregates": aggregates},
    )
    wall, cpu = time.perf_counter() - started, time.process_time() - cpu_started
    peak_memory_mib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    if wall > protocol["resource_budget"]["wall_seconds"]:
        raise RuntimeError("observation replay exceeded frozen wall budget")
    if peak_memory_mib > protocol["resource_budget"]["memory_mib_max"]:
        raise RuntimeError("observation replay exceeded frozen memory budget")
    return {
        "schema_version": "rhombus-observation-budget-result-v1",
        "protocol_sha256": PROTOCOL_SHA256, "source_receipt_sha256": protocol["input_sha256"],
        "computation_code_sha256": _sha(Path(__file__).read_bytes()),
        "series_results": results, "aggregates": aggregates,
        "hypotheses": {"H1": "PASS" if not violations and strict_improvement else "FAIL", "H1_counterexamples": violations,
                       "H1_at_least_one_strict_improvement": strict_improvement,
                       "H2": "FAIL" if stress_failures else "PASS", "H2_uncertified_series": stress_failures},
        "model_comparators": [{"model": name, "decision": "ABSTAIN", "eligible_series": 0,
                               "total_series": 6, "predictions_executed": 0,
                               "conditional_regret": None,
                               "reason": "Unqualified hot-press regime and/or unresolved complete per-condition composition"}
                              for name in ("FROZEN_PROCESS_RIDGE", "FROZEN_O_ONLY_RF", "FROZEN_POOLED_RF")],
        "scientific_utility_verdict": "INCONCLUSIVE_NO_RHOMBUS_MODEL_ADVANTAGE_DEMONSTRATED",
        "source_groups": 1, "source_conditions": 18, "new_independent_sources": 0,
        "new_physical_experiments": 0, "measurement_uncertainty": "UNKNOWN",
        "operational_status": "SUCCEEDED", "scientific_GO": False, "production_enabled": False,
        "TEST121_accessed": False, "P0_01": "BLOCKED", "P0_02": "BLOCKED", "P0_03": "BLOCKED",
        "cost": {"wall_seconds_including_input_verification": wall, "process_cpu_seconds": cpu,
                 "peak_process_memory_mib": peak_memory_mib,
                 "network_requests": 0, "model_fits": 0, "money_usd": 0,
                 "new_scientific_measurements": 0},
        "evidence_records": [evidence.to_dict()],
    }
