"""Default-off, diagnostic-only Candidate Supply portfolio decisions.

No function in this module calls a generator or changes an allocation.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping


ARMS = {
    "BASELINE_GAUSSIAN": "mobile-ion-displace-v2",
    "GAUSSIAN_LOCAL_D8": "mobile-ion-local-clearance-gaussian-radius-v1",
}
M6B_OBSERVATION = {
    "evidence_class": "FROZEN_OBSERVATIONAL_DIAGNOSTIC",
    "validation_profile_species": "Li", "sigma_A_provisional": 0.35,
    "parents": 15, "paired_identities": 45, "seeds": [44, 45, 46],
    "families": 5, "generated_each_arm": 24, "parent_p0_blocked_each_arm": 21,
    "exhausted_each_arm": 0, "inapplicable_each_arm": 0,
    "geometry_failures": {"BASELINE_GAUSSIAN": 9, "GAUSSIAN_LOCAL_D8": 0},
    "useful_diagnostic": {"BASELINE_GAUSSIAN": 8, "GAUSSIAN_LOCAL_D8": 16},
    "novel": {"BASELINE_GAUSSIAN": 17, "GAUSSIAN_LOCAL_D8": 16},
    "geometry_transitions": {"FAIL_TO_PASS": 9, "PASS_TO_PASS": 15},
    "geometry_effect_seed_blocks": "ALL_EVALUABLE_44_45_46",
    "geometry_effect_families_observed": ["halide", "oxide", "oxyhalide"],
    "generation_coverage_difference": 0,
    "scope": "Li validation profile; no global superiority or P1 authorization",
    "original_validation": "SCIENTIFIC_VALIDATION_FAIL",
    "selection_provenance": "reconcilable only with bound original bytes",
    "standalone_protected_state": "UNVERIFIED_BYTES_NOT_SUPPLIED",
}
FROZEN_EVIDENCE_CONTEXT = {
    "M5": "version-9 observational Pareto evidence; no allocation authorization",
    "M6_A": "geometry-aware D8 effect replicated in its validation scope",
    "M6_B": M6B_OBSERVATION,
}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def operator_rng_identity(parent_id: str, seed: int, arm_id: str,
                          policy_identity: str) -> dict:
    """Stable operator-scoped seed; arm changes cannot perturb another arm."""
    if not all(isinstance(value, str) and value for value in
               (parent_id, arm_id, policy_identity)) or arm_id not in ARMS:
        raise ValueError("invalid operator RNG identity")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    identity = _digest({"domain": "rhombus-m7-operator-rng-v1",
                        "parent_id": parent_id, "base_seed": seed,
                        "operator_version": ARMS[arm_id],
                        "policy_identity": policy_identity})
    return {"sha256": identity, "seed": int(identity[:16], 16)}


def _arm_evidence(value: Mapping, arm: str) -> dict:
    row = value.get(arm)
    if not isinstance(row, Mapping):
        raise ValueError(f"missing evidence for {arm}")
    fields = ("generated", "geometry_failures", "exhausted", "novel", "useful")
    if any(type(row.get(field)) is not int or row[field] < 0 for field in fields):
        raise ValueError(f"invalid count evidence for {arm}")
    if (row["geometry_failures"] > row["generated"]
            or row["novel"] > row["generated"]
            or row["useful"] > row["generated"]):
        raise ValueError(f"count exceeds generated for {arm}")
    effort = row.get("effort")
    if (not isinstance(effort, Mapping) or not isinstance(effort.get("unit"), str)
            or not effort["unit"] or type(effort.get("value")) is not int
            or effort["value"] < 0):
        raise ValueError(f"invalid effort evidence for {arm}")
    return {field: row[field] for field in fields} | {"effort": dict(effort)}


def decide_candidate_supply(*, enabled: bool = False, parent_context: Mapping,
                            evidence: Mapping, sigma_policy: Mapping,
                            base_seed: int, policy_identity: str,
                            lane: str = "EXPLORATION") -> dict:
    """Describe one bounded choice without executing or activating it.

    `sigma_policy` is an input interface: species -> provisional Å value.
    Evidence is per arm and context; no raw novelty maximization occurs.
    """
    if enabled is not False:
        raise ValueError("M7 execution is default-off and has no activation contract")
    if lane not in ("EXPLORATION", "EXPLOITATION"):
        raise ValueError("unknown lane")
    if not isinstance(parent_context, Mapping) or not isinstance(evidence, Mapping):
        raise ValueError("parent context and evidence must be mappings")
    parent_id, species = parent_context.get("parent_id"), parent_context.get("target_species")
    if not isinstance(parent_id, str) or not parent_id or not isinstance(species, str) or not species:
        raise ValueError("parent identity and target species are required")
    if parent_context.get("parent_p0_neutrality_ok") is not True:
        return {"schema_version": "candidate-supply-m7-decision-v1",
                "status": "BLOCKED_BY_PARENT_P0", "enabled": False,
                "parent_id": parent_id, "selected_arm": None,
                "authorization": {"execution": False, "p1_eligibility": False}}
    if not isinstance(sigma_policy, Mapping):
        raise ValueError("sigma policy must be a mapping")
    sigma = sigma_policy.get(species)
    if (isinstance(sigma, bool) or not isinstance(sigma, (int, float))
            or not math.isfinite(sigma) or sigma < 0):
        raise ValueError("missing provisional species-specific sigma")
    rows = {arm: _arm_evidence(evidence, arm) for arm in ARMS}
    # Comparable axes only. Effort is reported with units, never added or ranked.
    def dominates(a, b):
        x, y = rows[a], rows[b]
        axes_x = (x["useful"], x["generated"] - x["geometry_failures"], x["novel"], -x["exhausted"])
        axes_y = (y["useful"], y["generated"] - y["geometry_failures"], y["novel"], -y["exhausted"])
        return all(left >= right for left, right in zip(axes_x, axes_y)) and axes_x != axes_y
    front = [arm for arm in ARMS if not any(dominates(other, arm) for other in ARMS if other != arm)]
    # Exploration preserves both arms; exploitation uses useful yield and geometry,
    # with a hash tie break. Neither branch ranks on raw novelty alone.
    rank = _digest({"policy": policy_identity, "parent": parent_id, "seed": base_seed,
                    "lane": lane})
    if lane == "EXPLORATION":
        selected = list(ARMS)[int(rank[:16], 16) % len(ARMS)]
    else:
        selected = max(ARMS, key=lambda arm: (
            rows[arm]["useful"], rows[arm]["generated"] - rows[arm]["geometry_failures"],
            int(_digest({"rank": rank, "arm": arm})[:16], 16)))
    return {
        "schema_version": "candidate-supply-m7-decision-v1",
        "status": "DIAGNOSTIC_PROPOSAL_ONLY", "enabled": False,
        "parent_context": dict(parent_context), "policy_identity": policy_identity,
        "lane": lane, "portfolio": list(ARMS), "pareto_front": front,
        "selection_rule": ("DETERMINISTIC_HASH_PORTFOLIO_V1" if lane == "EXPLORATION"
                           else "USEFUL_THEN_GEOMETRY_V1"),
        "selected_arm": selected, "operator_version": ARMS[selected],
        "operator_rng": operator_rng_identity(parent_id, base_seed, selected, policy_identity),
        "sigma_policy": {"target_species": species, "sigma_A_provisional": float(sigma),
                         "qualification": "PROVISIONAL"},
        "evidence": rows,
        "evidence_sha256": _digest(rows),
        "frozen_evidence_context": FROZEN_EVIDENCE_CONTEXT,
        "effort_comparison": "UNSUPPORTED_DIFFERENT_OPERATOR_UNITS",
        "authorization": {"execution": False, "scheduler_activation": False,
                          "p1_eligibility": False, "operator_superiority": False,
                          "threshold_modification": False},
    }
