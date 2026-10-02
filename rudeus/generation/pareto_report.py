"""Deterministic, non-authorizing wrapper for Candidate Supply v2 Pareto evidence."""

from __future__ import annotations

import copy
from collections.abc import Mapping

from rudeus.generation.pareto_selection import (
    build_candidate_supply_v2_pareto_evidence,
    normalize_candidate_supply_v2_tournament_evidence,
)


_REPORT_SCHEMA_VERSION = "candidate-supply-v2-pareto-report-v1"


def _source_identity(tournament_artifact):
    panel = tournament_artifact["panel"]
    metadata = panel["metadata"]
    rows = panel.get("rows")
    if not isinstance(rows, list):
        raise ValueError("tournament source rows are required for source identity")
    if not isinstance(metadata.get("diagnostic_config_hash"), str):
        raise ValueError("tournament diagnostic_config_hash is required")
    parent_ids = metadata.get("ordered_parent_ids")
    arm_order = metadata.get("configurations")
    if not isinstance(parent_ids, list) or not isinstance(arm_order, list):
        raise ValueError("tournament parent identity and configured arm order are required")

    arm_observation_count = 0
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("arms"), Mapping):
            raise ValueError("malformed tournament row arm observations")
        arm_observation_count += len(row["arms"])

    return {
        "artifact_type": tournament_artifact["artifact_type"],
        "validation_state": tournament_artifact["validation_state"],
        "integrity": copy.deepcopy(tournament_artifact["integrity"]),
        "diagnostic_config_hash": metadata["diagnostic_config_hash"],
        "parent_count": len(parent_ids),
        "pair_count": len(rows),
        "arm_observation_count": arm_observation_count,
        "configured_arm_order": list(arm_order),
    }


def build_candidate_supply_v2_pareto_report(tournament_artifact, *, lane_policy):
    """Wrap existing reconciled tournament evidence without rerunning science."""
    normalized = normalize_candidate_supply_v2_tournament_evidence(
        tournament_artifact
    )
    pareto_evidence = build_candidate_supply_v2_pareto_evidence(
        normalized,
        lane_policy=lane_policy,
    )
    source = _source_identity(tournament_artifact)
    full_diversity = all(
        arm["dimensions"]["diversity"]["evidence_state"] == "COMPLETE"
        and arm["dimensions"]["diversity"]["distinct_structural_outcomes"].get(
            "value"
        ) is not None
        for arm in pareto_evidence["arms"]
    )
    return {
        "schema_version": _REPORT_SCHEMA_VERSION,
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "validation_state": "RECONCILED",
        "source": source,
        "configuration": {"lane_policy": copy.deepcopy(lane_policy)},
        "pareto_evidence": pareto_evidence,
        "authorization": copy.deepcopy(pareto_evidence["authorization"]),
        "limitations": {
            "observational_only": True,
            "scheduler_activation_authorized": False,
            "operator_superiority_authorized": False,
            "optimal_budget_authorized": False,
            "downstream_diffusion_claim_authorized": False,
            "full_structural_diversity_available": full_diversity,
        },
    }
