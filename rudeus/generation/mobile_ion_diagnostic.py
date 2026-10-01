"""Observational CPU cohort diagnostic for versioned mobile-ion displacement."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import tempfile
from pathlib import Path

import numpy as np
from pymatgen.analysis.structure_matcher import StructureMatcher

from rudeus.filters.p0 import evaluate_p0
from rudeus.generation.generator import (
    _mobile_site_indices,
    classify_candidate_supply_v2_novelty,
    op_mobile_ion_displace_clearance_v1,
    op_mobile_ion_displace_v2,
    op_mobile_ion_local_clearance_displace_v1,
    op_mobile_ion_local_clearance_gaussian_radius_v1,
)
from rudeus.generation.scheduler import (
    _operator_rng_seed,
    derive_candidate_supply_v2_operator_rng_identity,
)


def _p0_details_json_ready(value):
    """Convert P0 detail containers/scalars without inventing representations."""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, np.generic):
        return _p0_details_json_ready(value.item())
    if isinstance(value, (list, tuple)):
        return [_p0_details_json_ready(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("P0 detail dictionary keys must be strings")
        return {
            key: _p0_details_json_ready(item)
            for key, item in sorted(value.items())
        }
    raise TypeError(f"unsupported non-JSON P0 detail value: {type(value).__name__}")


def _counts(rows):
    """Derive descriptive counts solely from raw diagnostic rows."""

    generated = [row for row in rows if row["diagnostic_state"] == "GENERATED"]
    return {
        "requested_parents": len(rows),
        "blocked_parents": sum(
            row["diagnostic_state"] == "BLOCKED_BY_PARENT_P0" for row in rows
        ),
        "inapplicable_parents": sum(
            row["diagnostic_state"] == "INAPPLICABLE" for row in rows
        ),
        "generated_children": len(generated),
        "novel": sum(row["novelty_tag"] == "novel" for row in generated),
        "rediscovery": sum(
            row["novelty_tag"] == "rediscovery" for row in generated
        ),
        "p0_plausible": sum(
            row["p0_state"] == "PLAUSIBLE" for row in generated
        ),
        "geometry_failures": sum(
            row["p0_geometry_ok"] is False for row in generated
        ),
        "useful_diagnostic_yield": sum(
            row["novelty_tag"] == "novel" and row["p0_state"] == "PLAUSIBLE"
            for row in generated
        ),
    }


def _summary(rows):
    summary = _counts(rows)
    summary["by_chemical_family"] = {
        family: _counts(
            [row for row in rows if row["parent_chemical_family"] == family]
        )
        for family in sorted({row["parent_chemical_family"] for row in rows})
    }
    summary["by_site_count"] = {
        str(site_count): _counts(
            [row for row in rows if row["site_count"] == site_count]
        )
        for site_count in sorted({row["site_count"] for row in rows})
    }
    return summary


def _panel_counts(rows):
    """Summarize persisted diagnostic rows without a parallel counter path."""
    return _counts(rows)


def _parent_persistence(rows, threshold):
    parent_ids = sorted({row["parent_id"] for row in rows})
    output = {}
    for parent_id in parent_ids:
        parent_rows = [row for row in rows if row["parent_id"] == parent_id]
        generated = [row for row in parent_rows if row["diagnostic_state"] == "GENERATED"]
        useful_count = sum(
            row["novelty_tag"] == "novel" and row["p0_state"] == "PLAUSIBLE"
            for row in generated
        )
        novelty_count = sum(row["novelty_tag"] == "novel" for row in generated)
        geometry_count = sum(row["p0_geometry_ok"] is False for row in generated)
        denominator = len(generated)
        useful_fraction = useful_count / denominator if denominator else 0.0
        output[parent_id] = {
            "generated_count": len(generated),
            "observations_count": denominator,
            "useful_count": useful_count,
            "novelty_count": novelty_count,
            "geometry_fail_count": geometry_count,
            "useful_frequency": useful_fraction,
            "persistent_useful": useful_fraction >= threshold,
        }
    return output


def _panel_summary(rows, runs, sigmas, seeds, threshold):
    per_sigma = {}
    parent_persistence_by_sigma = {}
    family_persistence_by_sigma = {}
    for sigma in sigmas:
        sigma_runs = [run for run in runs if run["sigma_A_provisional"] == sigma]
        metrics = {}
        for metric in ("novel", "geometry_failures", "useful_diagnostic_yield"):
            values = [run["summary"][metric] for run in sigma_runs]
            metrics[metric] = {
                "mean": sum(values) / len(values) if values else 0.0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
            }
        metrics["replicate_values"] = {
            metric: [run["summary"][metric] for run in sigma_runs]
            for metric in ("novel", "geometry_failures", "useful_diagnostic_yield")
        }
        per_sigma[str(sigma)] = metrics

        sigma_rows = [row for row in rows if row["sigma_A_provisional"] == sigma]
        persistence = _parent_persistence(sigma_rows, threshold)
        parent_persistence_by_sigma[str(sigma)] = persistence
        families = sorted({row["parent_chemical_family"] for row in sigma_rows})
        family_summary = {}
        for family in families:
            family_rows = [
                row for row in sigma_rows
                if row["parent_chemical_family"] == family
            ]
            family_parent_ids = sorted({row["parent_id"] for row in family_rows})
            family_persistent = sum(
                persistence[parent_id]["persistent_useful"]
                for parent_id in family_parent_ids
            )
            ever_useful = sum(
                persistence[parent_id]["useful_count"] > 0
                for parent_id in family_parent_ids
            )
            family_summary[family] = {
                "parent_count": len(family_parent_ids),
                "persistent_useful_count": family_persistent,
                "ever_useful_count": ever_useful,
                "never_useful_count": len(family_parent_ids) - ever_useful,
            }
        family_persistence_by_sigma[str(sigma)] = family_summary

    # The top-level per-parent view pools the raw panel rows; the explicitly
    # sigma-scoped persistence above is the scientifically interpretable view.
    pooled = _parent_persistence(rows, threshold)
    per_parent_useful_frequency = {
        parent_id: {
            "observations_count": values["observations_count"],
            "useful_count": values["useful_count"],
            "useful_frequency": values["useful_frequency"],
        }
        for parent_id, values in pooled.items()
    }


def _paired_geometry_label(geometry_ok):
    if geometry_ok is True:
        return "PASS"
    if geometry_ok is False:
        return "FAIL"
    return "UNKNOWN"


def _paired_useful_label(useful):
    if useful is True:
        return "TRUE"
    if useful is False:
        return "FALSE"
    return "NOT_EVALUATED"


def _paired_transition_counts(rows, key):
    counts = {}
    for row in rows:
        transition = row["transitions"][key]
        counts[transition] = counts.get(transition, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _paired_distribution(rows, value_getter):
    counts = {}
    for row in rows:
        value = str(value_getter(row))
        counts[value] = counts.get(value, 0) + 1
    return {key: counts[key] for key in sorted(counts, key=lambda item: int(item))}


def _paired_diagnostic_summary(rows):
    """Derive paired counts and denominators exclusively from raw rows."""
    requested = len(rows)
    baseline_generated = sum(row["baseline"]["generated"] for row in rows)
    accepted_rows = [
        row for row in rows
        if row["clearance"]["proposal_status"] == "ACCEPTED"
    ]
    exhausted = sum(
        row["clearance"]["proposal_status"] == "EXHAUSTED" for row in rows
    )
    paired_rows = [
        row for row in rows
        if row["baseline"]["generated"] and row["clearance"]["generated"]
    ]

    def count(rows_, predicate):
        return sum(bool(predicate(row)) for row in rows_)

    baseline_geometry_fail = count(
        rows, lambda row: row["baseline"]["p0_geometry_ok"] is False
    )
    clearance_geometry_fail = count(
        accepted_rows, lambda row: row["clearance"]["p0_geometry_ok"] is False
    )
    baseline_novel = count(
        rows, lambda row: row["baseline"]["novelty_tag"] == "novel"
    )
    clearance_novel = count(
        accepted_rows, lambda row: row["clearance"]["novelty_tag"] == "novel"
    )
    baseline_useful = count(rows, lambda row: row["baseline"]["useful"] is True)
    clearance_useful = count(
        accepted_rows, lambda row: row["clearance"]["useful"] is True
    )
    common_denominator = len(paired_rows)

    def common_count(arm, predicate):
        return count(paired_rows, lambda row: predicate(row[arm]))

    def fraction(numerator, denominator):
        return numerator / denominator if denominator else 0.0

    baseline_common_geometry = common_count(
        "baseline", lambda arm: arm["p0_geometry_ok"] is False
    )
    clearance_common_geometry = common_count(
        "clearance", lambda arm: arm["p0_geometry_ok"] is False
    )
    baseline_common_novel = common_count(
        "baseline", lambda arm: arm["novelty_tag"] == "novel"
    )
    clearance_common_novel = common_count(
        "clearance", lambda arm: arm["novelty_tag"] == "novel"
    )
    baseline_common_useful = common_count(
        "baseline", lambda arm: arm["useful"] is True
    )
    clearance_common_useful = common_count(
        "clearance", lambda arm: arm["useful"] is True
    )

    return {
        "requested_pairs": requested,
        "baseline_generated": baseline_generated,
        "clearance_accepted": len(accepted_rows),
        "clearance_exhausted": exhausted,
        "exhaustion_rate": fraction(exhausted, requested),
        "baseline_geometry_fail_rows": baseline_geometry_fail,
        "clearance_geometry_fail_rows": clearance_geometry_fail,
        "paired_generated_both": common_denominator,
        "baseline_novel_rows": baseline_novel,
        "clearance_novel_rows": clearance_novel,
        "baseline_useful_rows": baseline_useful,
        "clearance_useful_rows": clearance_useful,
        "geometry_transition_counts": _paired_transition_counts(rows, "geometry"),
        "useful_transition_counts": _paired_transition_counts(rows, "useful"),
        "attempts_used_distribution": _paired_distribution(
            rows, lambda row: row["clearance"]["attempts_used"]
        ),
        "rejected_clash_attempts_distribution": _paired_distribution(
            rows, lambda row: row["clearance"]["rejected_clash_attempts"]
        ),
        "max_attempts_used": max(
            (row["clearance"]["attempts_used"] for row in rows), default=0
        ),
        "paired_common_subset": {
            "denominator": common_denominator,
            "baseline_geometry_fail_rows": baseline_common_geometry,
            "baseline_geometry_fail_denominator": common_denominator,
            "baseline_geometry_fail_fraction": fraction(
                baseline_common_geometry, common_denominator
            ),
            "clearance_geometry_fail_rows": clearance_common_geometry,
            "clearance_geometry_fail_denominator": common_denominator,
            "clearance_geometry_fail_fraction": fraction(
                clearance_common_geometry, common_denominator
            ),
            "baseline_novel_rows": baseline_common_novel,
            "baseline_novel_denominator": common_denominator,
            "baseline_novel_fraction": fraction(
                baseline_common_novel, common_denominator
            ),
            "clearance_novel_rows": clearance_common_novel,
            "clearance_novel_denominator": common_denominator,
            "clearance_novel_fraction": fraction(
                clearance_common_novel, common_denominator
            ),
            "baseline_useful_rows": baseline_common_useful,
            "baseline_useful_denominator": common_denominator,
            "baseline_useful_fraction": fraction(
                baseline_common_useful, common_denominator
            ),
            "clearance_useful_rows": clearance_common_useful,
            "clearance_useful_denominator": common_denominator,
            "clearance_useful_fraction": fraction(
                clearance_common_useful, common_denominator
            ),
        },
        "overall_clearance_yield": {
            "accepted_over_requested": fraction(len(accepted_rows), requested),
            "exhausted_over_requested": fraction(exhausted, requested),
            "novel_accepted_over_requested": fraction(clearance_novel, requested),
            "useful_accepted_over_requested": fraction(clearance_useful, requested),
            "requested_denominator": requested,
        },
    }


def _three_arm_child_record(parent_structure, child, params, *, pair_id, arm, matcher):
    p0 = evaluate_p0(
        str(child.composition.reduced_formula), structure=child
    )
    novelty = classify_candidate_supply_v2_novelty(
        parent_structure, child, matcher=matcher, operator_name="displace"
    )
    p0_plausible = p0.existence_state.value == "PLAUSIBLE"
    useful = novelty["novelty_tag"] == "novel" and p0_plausible
    child_dict = child.as_dict()
    child_hash = hashlib.sha256(
        json.dumps(
            {"pair_id": pair_id, "arm": arm, "structure": child_dict},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    geometry_details = (
        p0.details.get("geometry", {}) if isinstance(p0.details, dict) else {}
    )
    return {
        "operator_name": params["operator"],
        "operator_version": params["operator_version"],
        "operator_rng_identity": params.get("operator_rng_identity"),
        "operator_rng_seed": params.get("operator_rng_seed"),
        "generated": True,
        "child_material_id": f"g-three-arm-{child_hash}",
        "child_structure_dict": child_dict,
        "novelty_tag": novelty["novelty_tag"],
        "novelty_matched": novelty.get("novelty_matched"),
        "novelty_matcher_version": novelty["novelty_matcher_version"],
        "p0_state": p0.existence_state.value,
        "p0_plausible": p0_plausible,
        "p0_geometry_ok": p0.geometry_ok,
        "p0_details": _p0_details_json_ready(p0.details),
        "geometry_clash_evidence": geometry_details,
        "useful": useful,
    }


def _three_arm_exhausted_record(params, *, status_key, effort_keys):
    record = {
        "operator_name": params["operator"],
        "operator_version": params["operator_version"],
        "operator_rng_identity": params.get("operator_rng_identity"),
        "operator_rng_seed": params.get("operator_rng_seed"),
        "proposal_status": "EXHAUSTED",
        "generated": False,
        "child_material_id": None,
        "child_structure_dict": None,
        "novelty_tag": None,
        "novelty_matched": None,
        "novelty_matcher_version": None,
        "p0_state": None,
        "p0_plausible": None,
        "p0_geometry_ok": None,
        "p0_details": None,
        "geometry_clash_evidence": None,
        "useful": None,
    }
    record.update({key: params.get(key) for key in effort_keys})
    record[status_key] = "EXHAUSTED"
    return record


def _three_arm_summary(rows):
    requested = len(rows)
    bounded_accepted = [
        row for row in rows
        if row["bounded_clearance"]["proposal_status"] == "ACCEPTED"
    ]
    local_accepted = [
        row for row in rows
        if row["local_clearance"]["proposal_status"] == "ACCEPTED"
    ]

    def transition_counts(key):
        counts = {}
        for row in rows:
            label = row["transitions"][key]
            counts[label] = counts.get(label, 0) + 1
        return {label: counts[label] for label in sorted(counts)}

    def effort_distribution(arm_name, field):
        counts = {}
        for row in rows:
            value = row[arm_name].get(field)
            if value is not None:
                key = str(value)
                counts[key] = counts.get(key, 0) + 1
        return {key: counts[key] for key in sorted(counts, key=lambda x: int(x))}

    def arm_counts(arm_name, eligible_rows):
        generated = [row[arm_name] for row in eligible_rows if row[arm_name]["generated"]]
        return {
            "generated": len(generated),
            "exhausted": sum(
                row[arm_name].get("proposal_status") == "EXHAUSTED"
                for row in eligible_rows
            ),
            "geometry_fail": sum(item["p0_geometry_ok"] is False for item in generated),
            "novel": sum(item["novelty_tag"] == "novel" for item in generated),
            "p0_plausible": sum(item["p0_plausible"] is True for item in generated),
            "useful": sum(item["useful"] is True for item in generated),
            "requested_pairs": len(eligible_rows),
            "generated_over_requested": len(generated) / len(eligible_rows) if eligible_rows else 0.0,
            "useful_over_requested": (
                sum(item["useful"] is True for item in generated) / len(eligible_rows)
                if eligible_rows else 0.0
            ),
        }

    bounded_status = {"ACCEPTED/ACCEPTED": 0, "ACCEPTED/EXHAUSTED": 0,
                      "EXHAUSTED/ACCEPTED": 0, "EXHAUSTED/EXHAUSTED": 0}
    for row in rows:
        key = (
            f"{row['bounded_clearance']['proposal_status']}/"
            f"{row['local_clearance']['proposal_status']}"
        )
        bounded_status[key] += 1

    attempt1_rows = [
        row for row in rows
        if row["bounded_clearance"]["proposal_status"] == "ACCEPTED"
        and row["bounded_clearance"]["attempts_used"] == 1
    ]
    attempt1_matches = sum(
        row["baseline"]["child_structure_dict"]
        == row["bounded_clearance"]["child_structure_dict"]
        for row in attempt1_rows
    )
    local_magnitudes = [
        value
        for row in local_accepted
        for value in row["local_clearance"]["realized_displacement_magnitudes_A"]
    ]

    return {
        "requested_pairs": requested,
        "baseline_generated": sum(row["baseline"]["generated"] for row in rows),
        "bounded_accepted": len(bounded_accepted),
        "bounded_exhausted": requested - len(bounded_accepted),
        "local_accepted": len(local_accepted),
        "local_exhausted": requested - len(local_accepted),
        "baseline_bounded_generated_both": sum(
            row["baseline"]["generated"] and row["bounded_clearance"]["generated"]
            for row in rows
        ),
        "baseline_local_generated_both": sum(
            row["baseline"]["generated"] and row["local_clearance"]["generated"]
            for row in rows
        ),
        "all_three_generated": sum(
            row["baseline"]["generated"]
            and row["bounded_clearance"]["generated"]
            and row["local_clearance"]["generated"]
            for row in rows
        ),
        "arms": {
            name: arm_counts(name, rows)
            for name in ("baseline", "bounded_clearance", "local_clearance")
        },
        "baseline_to_bounded": {
            "geometry_transition_counts": transition_counts("baseline_to_bounded_geometry"),
            "useful_transition_counts": transition_counts("baseline_to_bounded_useful"),
        },
        "baseline_to_local": {
            "geometry_transition_counts": transition_counts("baseline_to_local_geometry"),
            "useful_transition_counts": transition_counts("baseline_to_local_useful"),
        },
        "bounded_local_status_cross_tab": bounded_status,
        "bounded_attempt1_accept_count": len(attempt1_rows),
        "baseline_bounded_attempt1_exact_match_count": attempt1_matches,
        "bounded_attempts_used_distribution": effort_distribution(
            "bounded_clearance", "attempts_used"
        ),
        "bounded_rejected_clash_attempts_distribution": effort_distribution(
            "bounded_clearance", "rejected_clash_attempts"
        ),
        "local_direction_trials_used_distribution": effort_distribution(
            "local_clearance", "direction_trials_used"
        ),
        "local_direction_trials_by_site": [
            row["local_clearance"].get("direction_trials_by_site") for row in rows
        ],
        "local_realized_displacement_A": {
            "count": len(local_magnitudes),
            "mean": float(np.mean(local_magnitudes)) if local_magnitudes else None,
            "median": float(np.median(local_magnitudes)) if local_magnitudes else None,
            "min": float(np.min(local_magnitudes)) if local_magnitudes else None,
            "max": float(np.max(local_magnitudes)) if local_magnitudes else None,
        },
    }


def build_mobile_ion_three_arm_paired_diagnostic_panel(
    parents,
    *,
    mobile_ion,
    sigma_values_A_provisional,
    base_seeds,
    diagnostic_config_hash,
    clearance_max_attempts,
    local_clearance_max_direction_trials,
):
    """Build an observational baseline/bounded/local paired diagnostic panel."""
    parents = list(parents)
    sigmas = list(sigma_values_A_provisional)
    seeds = list(base_seeds)
    if type(clearance_max_attempts) is not int or clearance_max_attempts <= 0:
        raise ValueError("clearance_max_attempts must be a positive integer")
    if (type(local_clearance_max_direction_trials) is not int
            or local_clearance_max_direction_trials <= 0):
        raise ValueError("local_clearance_max_direction_trials must be a positive integer")

    rows = []
    for parent in parents:
        if parent.structure is None or not parent.perturbable:
            raise ValueError(
                f"three-arm diagnostic requires a perturbable structured parent: {parent.parent_id}"
            )
        source = parent.structure
        for sigma in sigmas:
            for seed in seeds:
                pair_payload = {
                    "parent_id": parent.parent_id,
                    "sigma_A_provisional": sigma,
                    "base_seed": seed,
                }
                pair_bytes = json.dumps(
                    pair_payload, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
                pair_id = hashlib.sha256(pair_bytes).hexdigest()
                rng_parent_identity = json.dumps(
                    {
                        "pair_id": pair_id,
                        "mobile_ion": mobile_ion,
                        "diagnostic_config_hash": diagnostic_config_hash,
                    },
                    sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                )
                pair_rng_identity = derive_candidate_supply_v2_operator_rng_identity(
                    parent_id=rng_parent_identity,
                    seed=seed,
                    operator_name="mobile-ion-displace-paired",
                    operator_version="mobile-ion-clearance-paired-v1",
                )
                pair_rng_seed = _operator_rng_seed(pair_rng_identity)
                local_rng_identity = derive_candidate_supply_v2_operator_rng_identity(
                    parent_id=rng_parent_identity,
                    seed=seed,
                    operator_name="mobile-ion-local-clearance-displace",
                    operator_version="mobile-ion-local-clearance-displace-v1",
                )
                local_rng_seed = _operator_rng_seed(local_rng_identity)

                baseline_child, baseline_params = op_mobile_ion_displace_v2(
                    source.copy(), np.random.default_rng(pair_rng_seed),
                    mobile_ion=mobile_ion, sigma_A_provisional=sigma,
                    operator_rng_identity=pair_rng_identity,
                )
                baseline_params = {
                    **baseline_params, "operator_rng_identity": pair_rng_identity,
                    "operator_rng_seed": pair_rng_seed,
                }
                baseline = _three_arm_child_record(
                    source, baseline_child, baseline_params,
                    pair_id=pair_id, arm="baseline", matcher=None,
                )

                bounded_child, bounded_params = op_mobile_ion_displace_clearance_v1(
                    source.copy(), np.random.default_rng(pair_rng_seed),
                    mobile_ion=mobile_ion, sigma_A_provisional=sigma,
                    max_attempts=clearance_max_attempts,
                    operator_rng_identity=pair_rng_identity,
                )
                bounded_status = bounded_params["proposal_status"]
                if bounded_status not in {"ACCEPTED", "EXHAUSTED"}:
                    raise RuntimeError(f"unknown bounded-clearance status: {bounded_status}")
                if (bounded_status == "ACCEPTED") != (bounded_child is not None):
                    raise RuntimeError("bounded-clearance status disagrees with child result")
                if (bounded_status == "ACCEPTED"
                        and bounded_params["attempts_used"] == 1
                        and baseline_child.as_dict() != bounded_child.as_dict()):
                    raise RuntimeError(
                        "bounded-clearance first proposal differs from paired baseline"
                    )
                bounded_params = {
                    **bounded_params, "operator_rng_identity": pair_rng_identity,
                    "operator_rng_seed": pair_rng_seed,
                }
                if bounded_status == "ACCEPTED":
                    bounded = _three_arm_child_record(
                        source, bounded_child, bounded_params,
                        pair_id=pair_id, arm="bounded-clearance", matcher=None,
                    )
                    bounded.update({
                        "proposal_status": "ACCEPTED",
                        "attempts_used": bounded_params["attempts_used"],
                        "rejected_clash_attempts": bounded_params["rejected_clash_attempts"],
                    })
                else:
                    bounded = _three_arm_exhausted_record(
                        bounded_params, status_key="proposal_status",
                        effort_keys=("attempts_used", "rejected_clash_attempts"),
                    )

                local_child, local_params = op_mobile_ion_local_clearance_displace_v1(
                    source.copy(), np.random.default_rng(local_rng_seed),
                    mobile_ion=mobile_ion, sigma_A_provisional=sigma,
                    max_direction_trials=local_clearance_max_direction_trials,
                    operator_rng_identity=local_rng_identity,
                )
                local_status = local_params["proposal_status"]
                if local_status not in {"ACCEPTED", "EXHAUSTED"}:
                    raise RuntimeError(f"unknown local-clearance status: {local_status}")
                if (local_status == "ACCEPTED") != (local_child is not None):
                    raise RuntimeError("local-clearance status disagrees with child result")
                local_params = {
                    **local_params, "operator_rng_identity": local_rng_identity,
                    "operator_rng_seed": local_rng_seed,
                }
                if local_status == "ACCEPTED":
                    local = _three_arm_child_record(
                        source, local_child, local_params,
                        pair_id=pair_id, arm="local-clearance", matcher=None,
                    )
                    local.update({
                        "proposal_status": "ACCEPTED",
                        "direction_trials_used": local_params["direction_trials_used"],
                        "direction_trials_by_site": local_params.get("direction_trials_by_site"),
                        "realized_displacement_magnitudes_A": local_params[
                            "realized_displacement_magnitudes_A"
                        ],
                        "whole_child_geometry_ok": local["p0_geometry_ok"],
                    })
                else:
                    local = _three_arm_exhausted_record(
                        local_params, status_key="proposal_status",
                        effort_keys=(
                            "direction_trials_used", "direction_trials_by_site",
                            "realized_displacement_magnitudes_A",
                        ),
                    )
                    local["realized_displacement_magnitudes_A"] = (
                        local["realized_displacement_magnitudes_A"] or []
                    )
                    local["whole_child_geometry_ok"] = None

                transitions = {
                    "baseline_to_bounded_geometry": (
                        f"{_paired_geometry_label(baseline['p0_geometry_ok'])}_TO_"
                        f"{_paired_geometry_label(bounded['p0_geometry_ok']) if bounded['generated'] else 'EXHAUSTED'}"
                    ),
                    "baseline_to_bounded_useful": (
                        f"{_paired_useful_label(baseline['useful'])}_TO_"
                        f"{_paired_useful_label(bounded['useful'])}"
                    ),
                    "baseline_to_local_geometry": (
                        f"{_paired_geometry_label(baseline['p0_geometry_ok'])}_TO_"
                        f"{_paired_geometry_label(local['p0_geometry_ok']) if local['generated'] else 'EXHAUSTED'}"
                    ),
                    "baseline_to_local_useful": (
                        f"{_paired_useful_label(baseline['useful'])}_TO_"
                        f"{_paired_useful_label(local['useful'])}"
                    ),
                }
                rows.append({
                    "pair_id": pair_id,
                    "pair_rng_identity": pair_rng_identity,
                    "pair_rng_seed": pair_rng_seed,
                    "local_rng_identity": local_rng_identity,
                    "local_rng_seed": local_rng_seed,
                    "parent_id": parent.parent_id,
                    "chemical_family": parent.chemical_family,
                    "target_species": mobile_ion,
                    "sigma_A_provisional": sigma,
                    "base_seed": seed,
                    "diagnostic_config_hash": diagnostic_config_hash,
                    "site_count": len(source),
                    "target_site_count": len(_mobile_site_indices(source, mobile_ion)),
                    "baseline": baseline,
                    "bounded_clearance": bounded,
                    "local_clearance": local,
                    "transitions": transitions,
                })

    return {
        "schema_version": "mobile-ion-three-arm-paired-diagnostic-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "authorization": {
            "scheduler_activation": False,
            "p1_eligibility": False,
            "downstream_scientific_claims": False,
            "operator_superiority": False,
            "automatic_promotion": False,
            "parent_exclusion": False,
            "chemistry_exclusion": False,
            "threshold_modification": False,
        },
        "metadata": {
            "baseline_operator_name": "mobile-ion-displace",
            "baseline_operator_version": "mobile-ion-displace-v2",
            "bounded_clearance_operator_name": "mobile-ion-displace-clearance",
            "bounded_clearance_operator_version": "mobile-ion-displace-clearance-v1",
            "local_clearance_operator_name": "mobile-ion-local-clearance-displace",
            "local_clearance_operator_version": "mobile-ion-local-clearance-displace-v1",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "target_species": mobile_ion,
            "sigma_values_A_provisional": sigmas,
            "base_seeds": seeds,
            "ordered_parent_ids": [parent.parent_id for parent in parents],
            "diagnostic_config_hash": diagnostic_config_hash,
            "bounded_clearance_max_attempts": clearance_max_attempts,
            "local_clearance_max_direction_trials": local_clearance_max_direction_trials,
        },
        "rows": rows,
        "summary": _three_arm_summary(rows),
    }


def _gaussian_semantics_displacement_summary(rows, arm_name, sigmas):
    def bucket(subset):
        measurements = [
            (row, value)
            for row in subset
            for value in row[arm_name]["derived_mobile_displacements_A"]
        ]
        values = [value for _, value in measurements]
        result = _local_parameterization_series(values)
        ratios = [
            value / float(row["sigma_A_provisional"])
            for row, value in measurements
            if float(row["sigma_A_provisional"]) != 0.0
        ]
        result.update({
            "mobile_site_count": len(values),
            "mean_over_sigma": float(np.mean(ratios)) if ratios else None,
            "rms_over_sigma": (
                float(np.sqrt(np.mean(np.square(ratios)))) if ratios else None
            ),
        })
        if arm_name == "gaussian_local_clearance":
            site_records = [
                item
                for row in subset
                for item in row[arm_name]["site_displacements"]
            ]
            sampled = [item["sampled_gaussian_radius_A"] for item in site_records]
            errors = [item["realized_minus_sampled_radius_A"] for item in site_records]
            result["sampled_radius"] = _local_parameterization_series(sampled)
            result["realized_minus_sampled_radius"] = {
                **_local_parameterization_series(errors),
                "max_abs_A": max((abs(value) for value in errors), default=None),
            }
        return result

    generated = [row for row in rows if row[arm_name]["generated"]]
    output = {"global": bucket(generated), "by_sigma": {}}
    for sigma in sigmas:
        output["by_sigma"][str(sigma)] = bucket([
            row for row in generated if row["sigma_A_provisional"] == sigma
        ])
    return output


def _gaussian_semantics_summary(rows, sigmas):
    arm_names = ("baseline", "bounded_clearance", "gaussian_local_clearance")

    def arm_summary(arm_name):
        arm_rows = [row[arm_name] for row in rows]
        generated = [item for item in arm_rows if item["generated"]]
        novel = sum(item["novelty_tag"] == "novel" for item in generated)
        useful = sum(item["useful"] is True for item in generated)
        requested = len(rows)
        generated_count = len(generated)
        return {
            "requested_pairs": requested,
            "generated": generated_count,
            "accepted": generated_count if arm_name != "baseline" else None,
            "exhausted": sum(item.get("proposal_status") == "EXHAUSTED" for item in arm_rows),
            "geometry_fail": sum(item["p0_geometry_ok"] is False for item in generated),
            "novel": novel,
            "rediscovery": sum(item["novelty_tag"] == "rediscovery" for item in generated),
            "p0_plausible": sum(item["p0_plausible"] is True for item in generated),
            "useful": useful,
            "novel_per_requested": novel / requested if requested else 0.0,
            "useful_per_requested": useful / requested if requested else 0.0,
            "useful_per_generated": useful / generated_count if generated_count else 0.0,
        }

    def transition_counts(key):
        counts = {}
        for row in rows:
            label = row["transitions"][key]
            counts[label] = counts.get(label, 0) + 1
        return {label: counts[label] for label in sorted(counts)}

    status_cross = {
        "ACCEPTED/ACCEPTED": 0,
        "ACCEPTED/EXHAUSTED": 0,
        "EXHAUSTED/ACCEPTED": 0,
        "EXHAUSTED/EXHAUSTED": 0,
    }
    novelty_cross = {
        "NOVEL/NOVEL": 0,
        "NOVEL/REDISCOVERY": 0,
        "REDISCOVERY/NOVEL": 0,
        "REDISCOVERY/REDISCOVERY": 0,
    }
    useful_cross = {"TRUE/TRUE": 0, "TRUE/FALSE": 0, "FALSE/TRUE": 0, "FALSE/FALSE": 0}
    for row in rows:
        bounded = row["bounded_clearance"]
        local = row["gaussian_local_clearance"]
        status_cross[f"{bounded['proposal_status']}/{local['proposal_status']}"] += 1
        if bounded["generated"] and local["generated"]:
            novelty_cross[f"{bounded['novelty_tag'].upper()}/{local['novelty_tag'].upper()}"] += 1
            useful_cross[f"{str(bounded['useful']).upper()}/{str(local['useful']).upper()}"] += 1

    bounded_attempt1 = [
        row for row in rows
        if row["bounded_clearance"]["generated"]
        and row["bounded_clearance"]["attempts_used"] == 1
    ]
    displacement = {
        arm_name: _gaussian_semantics_displacement_summary(rows, arm_name, sigmas)
        for arm_name in arm_names
    }

    local_measurements = [
        (row, item)
        for row in rows
        for item in row["gaussian_local_clearance"]["site_displacements"]
    ]
    sampled_radii = [item["sampled_gaussian_radius_A"] for _, item in local_measurements]
    radius_errors = [item["realized_minus_sampled_radius_A"] for _, item in local_measurements]
    radius_consistency = {
        "mobile_site_count": len(radius_errors),
        "sampled_radius": _local_parameterization_series(sampled_radii),
        "realized_minus_sampled_radius": {
            **_local_parameterization_series(radius_errors),
            "max_abs_A": max((abs(value) for value in radius_errors), default=None),
        },
    }

    def distribution(values):
        counts = {}
        for value in values:
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
        return {key: counts[key] for key in sorted(counts, key=lambda value: int(value))}

    bounded_rows = [row["bounded_clearance"] for row in rows]
    local_trials = [
        value for row in rows
        for value in (row["gaussian_local_clearance"].get("direction_trials_by_site") or [])
    ]
    local_row_effort = [sum(row["gaussian_local_clearance"].get("direction_trials_by_site") or [])
                        for row in rows]

    structural = {}
    for arm_name in arm_names:
        generated = [row[arm_name]["structural_change"] for row in rows if row[arm_name]["generated"]]
        names = (
            "mobile_displacement_rms_A",
            "mobile_mobile_pair_distance_changes_abs_A",
            "nearest_host_distance_changes_A",
        )
        structural[arm_name] = {
            name: _local_parameterization_series([
                value for record in generated
                for value in ([record[name]] if name == names[0] else record[name])
                if value is not None
            ])
            for name in names
        }

    requested = len(rows)
    counts = {
        "requested_pairs": requested,
        "baseline_generated": sum(row["baseline"]["generated"] for row in rows),
        "bounded_accepted": sum(row["bounded_clearance"]["generated"] for row in rows),
        "bounded_exhausted": sum(not row["bounded_clearance"]["generated"] for row in rows),
        "gaussian_local_accepted": sum(row["gaussian_local_clearance"]["generated"] for row in rows),
        "gaussian_local_exhausted": sum(not row["gaussian_local_clearance"]["generated"] for row in rows),
        "baseline_bounded_generated_both": sum(row["baseline"]["generated"] and row["bounded_clearance"]["generated"] for row in rows),
        "baseline_gaussian_local_generated_both": sum(row["baseline"]["generated"] and row["gaussian_local_clearance"]["generated"] for row in rows),
        "bounded_gaussian_local_generated_both": sum(row["bounded_clearance"]["generated"] and row["gaussian_local_clearance"]["generated"] for row in rows),
        "all_three_generated": sum(all(row[name]["generated"] for name in arm_names) for row in rows),
    }
    if counts["bounded_accepted"] + counts["bounded_exhausted"] != requested:
        raise RuntimeError("bounded arm counts do not reconcile to requested pairs")
    if counts["gaussian_local_accepted"] + counts["gaussian_local_exhausted"] != requested:
        raise RuntimeError("Gaussian-local arm counts do not reconcile to requested pairs")
    attempt1_match_count = sum(
        row["baseline"]["child_structure_dict"] == row["bounded_clearance"]["child_structure_dict"]
        for row in bounded_attempt1
    )
    if attempt1_match_count != len(bounded_attempt1):
        raise RuntimeError("bounded first proposal differs from paired baseline")
    if sum(status_cross.values()) != requested:
        raise RuntimeError("bounded/Gaussian-local status cross-tab does not reconcile")
    if sum(novelty_cross.values()) != counts["bounded_gaussian_local_generated_both"]:
        raise RuntimeError("novelty cross-tab does not reconcile to both-generated pairs")
    if sum(useful_cross.values()) != counts["bounded_gaussian_local_generated_both"]:
        raise RuntimeError("useful cross-tab does not reconcile to both-generated pairs")

    return {
        **counts,
        "arms": {name: arm_summary(name) for name in arm_names},
        "baseline_to_bounded": {
            "geometry_transition_counts": transition_counts("baseline_to_bounded_geometry"),
            "useful_transition_counts": transition_counts("baseline_to_bounded_useful"),
        },
        "baseline_to_gaussian_local": {
            "geometry_transition_counts": transition_counts("baseline_to_gaussian_local_geometry"),
            "useful_transition_counts": transition_counts("baseline_to_gaussian_local_useful"),
        },
        "bounded_gaussian_local_status_cross_tab": status_cross,
        "bounded_gaussian_local_novelty_cross_tab": novelty_cross,
        "bounded_gaussian_local_useful_cross_tab": useful_cross,
        "bounded_gaussian_local_cross_tab_denominator": counts["bounded_gaussian_local_generated_both"],
        "bounded_attempt1_accept_count": len(bounded_attempt1),
        "baseline_bounded_attempt1_exact_match_count": attempt1_match_count,
        "arms_summary": {name: arm_summary(name) for name in arm_names},
        "bounded_effort": {
            "attempts_used_distribution": distribution([row.get("attempts_used") for row in bounded_rows]),
            "rejected_clash_attempts_distribution": distribution([row.get("rejected_clash_attempts") for row in bounded_rows]),
        },
        "gaussian_local_effort": {
            "per_site_direction_trial_distribution": distribution(local_trials),
            "total_direction_trials": sum(local_trials),
            "row_total_direction_trials_distribution": distribution(local_row_effort),
        },
        "displacement": displacement,
        "gaussian_local_radius_consistency": radius_consistency,
        "structural_change": structural,
    }


def build_mobile_ion_gaussian_semantics_three_arm_diagnostic_panel(
    parents,
    *,
    mobile_ion,
    sigma_values_A_provisional,
    base_seeds,
    diagnostic_config_hash,
    clearance_max_attempts,
    gaussian_local_max_direction_trials,
):
    """Build an observational paired panel for three Gaussian-source arms."""
    parents = list(parents)
    sigmas = list(sigma_values_A_provisional)
    seeds = list(base_seeds)
    if type(clearance_max_attempts) is not int or clearance_max_attempts <= 0:
        raise ValueError("clearance_max_attempts must be a positive integer")
    if type(gaussian_local_max_direction_trials) is not int or gaussian_local_max_direction_trials <= 0:
        raise ValueError("gaussian_local_max_direction_trials must be a positive integer")
    if any(not np.isfinite(sigma) or sigma < 0 for sigma in sigmas):
        raise ValueError("sigma values must be finite and non-negative")

    matcher = None
    rows = []
    for parent in parents:
        if parent.structure is None or not parent.perturbable:
            raise ValueError(f"diagnostic requires a perturbable structured parent: {parent.parent_id}")
        source = parent.structure
        mobile_indices = _mobile_site_indices(source, mobile_ion)
        if not mobile_indices:
            raise ValueError(f"no sites matching mobile_ion='{mobile_ion}' in {parent.parent_id}")
        for sigma in sigmas:
            for seed in seeds:
                pair_payload = {
                    "parent_id": parent.parent_id,
                    "sigma_A_provisional": sigma,
                    "base_seed": seed,
                }
                pair_bytes = json.dumps(
                    pair_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
                pair_id = hashlib.sha256(pair_bytes).hexdigest()
                rng_parent_identity = json.dumps({
                    "pair_id": pair_id,
                    "mobile_ion": mobile_ion,
                    "diagnostic_config_hash": diagnostic_config_hash,
                }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                pair_rng_identity = derive_candidate_supply_v2_operator_rng_identity(
                    parent_id=rng_parent_identity,
                    seed=seed,
                    operator_name="mobile-ion-displace-paired",
                    operator_version="mobile-ion-clearance-paired-v1",
                )
                pair_rng_seed = _operator_rng_seed(pair_rng_identity)
                local_rng_identity = derive_candidate_supply_v2_operator_rng_identity(
                    parent_id=rng_parent_identity,
                    seed=seed,
                    operator_name="mobile-ion-local-clearance-gaussian-radius",
                    operator_version="mobile-ion-local-clearance-gaussian-radius-v1",
                )
                local_rng_seed = _operator_rng_seed(local_rng_identity)

                baseline_child, baseline_params = op_mobile_ion_displace_v2(
                    source.copy(), np.random.default_rng(pair_rng_seed),
                    mobile_ion=mobile_ion, sigma_A_provisional=sigma,
                    operator_rng_identity=pair_rng_identity,
                )
                baseline_params = {
                    **baseline_params, "operator_rng_identity": pair_rng_identity,
                    "operator_rng_seed": pair_rng_seed,
                }
                baseline = _three_arm_child_record(
                    source, baseline_child, baseline_params, pair_id=pair_id,
                    arm="baseline", matcher=matcher,
                )
                baseline.update({
                    "proposal_status": "GENERATED", "same_cell_mode": True,
                    "skip_structure_reduction": True,
                })

                bounded_child, bounded_params = op_mobile_ion_displace_clearance_v1(
                    source.copy(), np.random.default_rng(pair_rng_seed),
                    mobile_ion=mobile_ion, sigma_A_provisional=sigma,
                    max_attempts=clearance_max_attempts,
                    operator_rng_identity=pair_rng_identity,
                )
                bounded_status = bounded_params.get("proposal_status")
                if bounded_status not in {"ACCEPTED", "EXHAUSTED"}:
                    raise RuntimeError(f"unknown bounded-clearance status: {bounded_status}")
                if (bounded_status == "ACCEPTED") != (bounded_child is not None):
                    raise RuntimeError("bounded-clearance status disagrees with child result")
                bounded_params = {
                    **bounded_params, "operator_rng_identity": pair_rng_identity,
                    "operator_rng_seed": pair_rng_seed,
                }
                if bounded_child is None:
                    bounded = _three_arm_exhausted_record(
                        bounded_params, status_key="proposal_status",
                        effort_keys=("attempts_used", "rejected_clash_attempts"),
                    )
                else:
                    if bounded_params["attempts_used"] == 1 and baseline_child.as_dict() != bounded_child.as_dict():
                        raise RuntimeError("bounded first proposal differs from paired baseline")
                    bounded = _three_arm_child_record(
                        source, bounded_child, bounded_params, pair_id=pair_id,
                        arm="bounded-clearance", matcher=matcher,
                    )
                    bounded.update({
                        "proposal_status": "ACCEPTED",
                        "attempts_used": bounded_params["attempts_used"],
                        "rejected_clash_attempts": bounded_params["rejected_clash_attempts"],
                        "same_cell_mode": True,
                        "skip_structure_reduction": True,
                    })

                local_child, local_params = op_mobile_ion_local_clearance_gaussian_radius_v1(
                    source.copy(), np.random.default_rng(local_rng_seed),
                    mobile_ion=mobile_ion, sigma_A_provisional=sigma,
                    max_direction_trials=gaussian_local_max_direction_trials,
                    operator_rng_identity=local_rng_identity,
                )
                local_status = local_params.get("proposal_status")
                if local_status not in {"ACCEPTED", "EXHAUSTED"}:
                    raise RuntimeError(f"unknown Gaussian-local status: {local_status}")
                if (local_status == "ACCEPTED") != (local_child is not None):
                    raise RuntimeError("Gaussian-local status disagrees with child result")
                local_params = {
                    **local_params, "operator_rng_identity": local_rng_identity,
                    "operator_rng_seed": local_rng_seed,
                }
                if local_child is None:
                    local = _three_arm_exhausted_record(
                        local_params, status_key="proposal_status",
                        effort_keys=("direction_trials_by_site",),
                    )
                    local["direction_trials_by_site"] = local_params.get("direction_trials_by_site")
                    local["direction_trials_used"] = sum(local["direction_trials_by_site"] or [])
                    local["sampled_gaussian_components_A"] = local_params.get("sampled_gaussian_components_A")
                    local["sampled_radii_A"] = local_params.get("sampled_radii_A")
                    local["realized_displacement_magnitudes_A"] = []
                    local["site_displacements"] = []
                    local["derived_mobile_displacements_A"] = []
                    local["structural_change"] = None
                else:
                    local = _three_arm_child_record(
                        source, local_child, local_params, pair_id=pair_id,
                        arm="gaussian-local-clearance", matcher=matcher,
                    )
                    local.update({
                        "proposal_status": "ACCEPTED",
                        "direction_trials_by_site": local_params.get("direction_trials_by_site"),
                        "direction_trials_used": sum(local_params.get("direction_trials_by_site") or []),
                        "sampled_gaussian_components_A": local_params.get("sampled_gaussian_components_A"),
                        "sampled_radii_A": local_params.get("sampled_radii_A"),
                        "same_cell_mode": True,
                        "skip_structure_reduction": True,
                    })

                for arm_name, child, record in (
                    ("baseline", baseline_child, baseline),
                    ("bounded_clearance", bounded_child, bounded),
                    ("gaussian_local_clearance", local_child, local),
                ):
                    if child is None:
                        continue
                    if (child.composition != source.composition or child.lattice != source.lattice
                            or len(child) != len(source)
                            or [str(site.species) for site in child] != [str(site.species) for site in source]):
                        raise RuntimeError(f"{arm_name} changed same-cell structure invariants")
                    site_displacements = []
                    for offset, index in enumerate(mobile_indices):
                        realized = float(source.lattice.get_distance_and_image(
                            source[index].frac_coords, child[index].frac_coords
                        )[0])
                        item = {
                            "mobile_site_index": index,
                            "minimum_image_displacement_A": realized,
                        }
                        if arm_name == "gaussian_local_clearance":
                            sampled = float(local_params["sampled_radii_A"][offset])
                            item.update({
                                "sampled_gaussian_radius_A": sampled,
                                "realized_minus_sampled_radius_A": realized - sampled,
                            })
                        site_displacements.append(item)
                    magnitudes = [item["minimum_image_displacement_A"] for item in site_displacements]
                    structural_change = _local_parameterization_geometry_summary(source, child, mobile_indices)
                    structural_change["mobile_displacement_rms_A"] = float(
                        np.sqrt(np.mean(np.square(magnitudes)))
                    ) if magnitudes else None
                    record["site_displacements"] = site_displacements
                    record["derived_mobile_displacements_A"] = magnitudes
                    record["structural_change"] = structural_change
                    if arm_name == "gaussian_local_clearance":
                        record["realized_displacement_magnitudes_A"] = magnitudes
                    record["operator_provenance"] = dict(
                        baseline_params if arm_name == "baseline" else
                        bounded_params if arm_name == "bounded_clearance" else local_params
                    )

                row = {
                    "pair_id": pair_id,
                    "pair_rng_identity": pair_rng_identity,
                    "pair_rng_seed": pair_rng_seed,
                    "gaussian_local_rng_identity": local_rng_identity,
                    "gaussian_local_rng_seed": local_rng_seed,
                    "parent_id": parent.parent_id,
                    "chemical_family": parent.chemical_family,
                    "target_species": mobile_ion,
                    "sigma_A_provisional": sigma,
                    "base_seed": seed,
                    "diagnostic_config_hash": diagnostic_config_hash,
                    "site_count": len(source),
                    "target_site_count": len(mobile_indices),
                    "baseline": baseline,
                    "bounded_clearance": bounded,
                    "gaussian_local_clearance": local,
                    "transitions": {
                        "baseline_to_bounded_geometry": (
                            f"{_paired_geometry_label(baseline['p0_geometry_ok'])}_TO_"
                            f"{_paired_geometry_label(bounded['p0_geometry_ok']) if bounded['generated'] else 'EXHAUSTED'}"
                        ),
                        "baseline_to_bounded_useful": (
                            f"{_paired_useful_label(baseline['useful'])}_TO_{_paired_useful_label(bounded['useful'])}"
                        ),
                        "baseline_to_gaussian_local_geometry": (
                            f"{_paired_geometry_label(baseline['p0_geometry_ok'])}_TO_"
                            f"{_paired_geometry_label(local['p0_geometry_ok']) if local['generated'] else 'EXHAUSTED'}"
                        ),
                        "baseline_to_gaussian_local_useful": (
                            f"{_paired_useful_label(baseline['useful'])}_TO_{_paired_useful_label(local['useful'])}"
                        ),
                    },
                }
                rows.append(row)

    rows = json.loads(json.dumps(rows, sort_keys=True, ensure_ascii=False))
    return {
        "schema_version": "mobile-ion-gaussian-semantics-three-arm-diagnostic-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "authorization": {
            "scheduler_activation": False,
            "p1_eligibility": False,
            "downstream_scientific_claims": False,
            "operator_superiority": False,
            "automatic_promotion": False,
            "sigma_selection": False,
            "budget_selection": False,
            "parent_exclusion": False,
            "chemistry_exclusion": False,
            "threshold_modification": False,
        },
        "metadata": {
            "baseline_operator_name": "mobile-ion-displace",
            "baseline_operator_version": "mobile-ion-displace-v2",
            "bounded_clearance_operator_name": "mobile-ion-displace-clearance",
            "bounded_clearance_operator_version": "mobile-ion-displace-clearance-v1",
            "gaussian_local_operator_name": "mobile-ion-local-clearance-gaussian-radius",
            "gaussian_local_operator_version": "mobile-ion-local-clearance-gaussian-radius-v1",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "target_species": mobile_ion,
            "sigma_values_A_provisional": sigmas,
            "base_seeds": seeds,
            "ordered_parent_ids": [parent.parent_id for parent in parents],
            "diagnostic_config_hash": diagnostic_config_hash,
            "clearance_max_attempts": clearance_max_attempts,
            "gaussian_local_max_direction_trials": gaussian_local_max_direction_trials,
            "sigma_A_provisional_semantics": "PER_CARTESIAN_COMPONENT_GAUSSIAN_STDDEV",
            "arm_mechanics": {
                "baseline": "GAUSSIAN_VECTOR_FINAL",
                "bounded_clearance": "REPEATED_COMPLETE_GAUSSIAN_PROPOSALS",
                "gaussian_local_clearance": "GAUSSIAN_RADIUS_LOCAL_DIRECTION_SEARCH",
            },
            "final_proposal_distributions_identical": False,
            "effort_units": {
                "bounded_clearance": "COMPLETE_GAUSSIAN_PROPOSAL_ATTEMPTS",
                "gaussian_local_clearance": "PER_SITE_DIRECTION_TRIALS",
            },
        },
        "rows": rows,
        "summary": _gaussian_semantics_summary(rows, sigmas),
    }


def _local_parameterization_child_record(parent, child, params, *, pair_id, arm_name):
    p0 = evaluate_p0(str(child.composition.reduced_formula), structure=child)
    novelty = classify_candidate_supply_v2_novelty(
        parent, child, matcher=None, operator_name="displace"
    )
    p0_plausible = p0.existence_state.value == "PLAUSIBLE"
    child_dict = child.as_dict()
    child_hash = hashlib.sha256(json.dumps(
        {"pair_id": pair_id, "arm": arm_name, "structure": child_dict},
        sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()[:16]
    geometry_details = (
        p0.details.get("geometry", {}) if isinstance(p0.details, dict) else {}
    )
    return {
        "operator_name": params["operator"],
        "operator_version": params["operator_version"],
        "operator_rng_identity": params["operator_rng_identity"],
        "operator_rng_seed": params["operator_rng_seed"],
        "proposal_status": "ACCEPTED",
        "generated": True,
        "child_material_id": f"g-local-parameterization-{child_hash}",
        "child_structure_dict": child_dict,
        "novelty_tag": novelty["novelty_tag"],
        "novelty_matched": novelty.get("novelty_matched"),
        "novelty_matcher_version": novelty["novelty_matcher_version"],
        "same_cell_mode": True,
        "skip_structure_reduction": True,
        "p0_state": p0.existence_state.value,
        "p0_plausible": p0_plausible,
        "p0_neutrality_ok": p0.neutrality_ok,
        "p0_pauling_ok": p0.pauling_ok,
        "p0_geometry_ok": p0.geometry_ok,
        "p0_details": _p0_details_json_ready(p0.details),
        "geometry_clash_evidence": _p0_details_json_ready(geometry_details),
        "useful": novelty["novelty_tag"] == "novel" and p0_plausible,
    }


def _local_parameterization_geometry_summary(parent, child, mobile_indices):
    host_indices = [index for index in range(len(parent)) if index not in mobile_indices]

    def distance(structure, first, second):
        return float(structure.lattice.get_distance_and_image(
            structure[first].frac_coords, structure[second].frac_coords
        )[0])

    mobile_pair_changes = [
        abs(distance(child, first, second) - distance(parent, first, second))
        for first, second in itertools.combinations(mobile_indices, 2)
    ]
    nearest_host_changes = []
    for mobile_index in mobile_indices:
        if host_indices:
            before = min(distance(parent, mobile_index, host) for host in host_indices)
            after = min(distance(child, mobile_index, host) for host in host_indices)
            nearest_host_changes.append(after - before)
    return {
        "mobile_displacement_rms_A": None,
        "mobile_mobile_pair_distance_changes_abs_A": mobile_pair_changes,
        "nearest_host_distance_changes_A": nearest_host_changes,
    }


def _local_parameterization_series(values):
    values = [float(value) for value in values]
    if not values:
        return {"count": 0, "min_A": None, "median_A": None, "mean_A": None,
                "rms_A": None, "max_A": None}
    return {
        "count": len(values),
        "min_A": float(np.min(values)),
        "median_A": float(np.median(values)),
        "mean_A": float(np.mean(values)),
        "rms_A": float(np.sqrt(np.mean(np.square(values)))),
        "max_A": float(np.max(values)),
    }


def _local_parameterization_summary(rows, sigmas):
    requested = len(rows)
    arm_names = ("fixed_radius", "gaussian_radius")

    def arm_rows(name, subset):
        return [row[name] for row in subset]

    def arm_counts(name, subset):
        values = arm_rows(name, subset)
        generated = [value for value in values if value["generated"]]
        novel = sum(value["novelty_tag"] == "novel" for value in generated)
        useful = sum(value["useful"] is True for value in generated)
        return {
            "requested_pairs": len(subset),
            "accepted": len(generated),
            "generated": len(generated),
            "exhausted": sum(value["proposal_status"] == "EXHAUSTED" for value in values),
            "geometry_fail": sum(value["p0_geometry_ok"] is False for value in generated),
            "novel": novel,
            "rediscovery": sum(value["novelty_tag"] == "rediscovery" for value in generated),
            "p0_plausible": sum(value["p0_plausible"] is True for value in generated),
            "useful": useful,
            "novel_per_requested": novel / len(subset) if subset else 0.0,
            "novel_per_generated": novel / len(generated) if generated else 0.0,
            "useful_per_requested": useful / len(subset) if subset else 0.0,
            "useful_per_generated": useful / len(generated) if generated else 0.0,
        }

    status_labels = ("ACCEPTED", "EXHAUSTED")
    novelty_labels = ("NOVEL", "REDISCOVERY")
    useful_labels = ("TRUE", "FALSE")
    status_cross = {f"{left}_TO_{right}": 0
                    for left in status_labels for right in status_labels}
    novelty_cross = {f"{left}_TO_{right}": 0
                     for left in novelty_labels for right in novelty_labels}
    useful_cross = {f"{left}_TO_{right}": 0
                    for left in useful_labels for right in useful_labels}
    for row in rows:
        fixed, gaussian = row["fixed_radius"], row["gaussian_radius"]
        status_cross[f"{fixed['proposal_status']}_TO_{gaussian['proposal_status']}"] += 1
        if fixed["generated"] and gaussian["generated"]:
            novelty_cross[f"{fixed['novelty_tag'].upper()}_TO_{gaussian['novelty_tag'].upper()}"] += 1
            useful_cross[f"{str(fixed['useful']).upper()}_TO_{str(gaussian['useful']).upper()}"] += 1

    displacement = {}
    structural = {}
    effort = {}
    for arm_name in arm_names:
        def displacement_bucket(subset):
            values = [
                (row, arm, item)
                for row in subset
                for arm in [row[arm_name]] if arm["generated"]
                for item in arm["site_displacements"]
            ]
            magnitudes = [item["minimum_image_displacement_A"] for _, _, item in values]
            stats = _local_parameterization_series(magnitudes)
            sigmas_per_site = [row["sigma_A_provisional"] for row, _, _ in values]
            ratios = [magnitude / sigma for magnitude, sigma in zip(magnitudes, sigmas_per_site)
                      if sigma != 0]
            stats["mobile_site_count"] = len(magnitudes)
            stats["mean_over_sigma"] = float(np.mean(ratios)) if ratios else None
            stats["rms_over_sigma"] = (
                float(np.sqrt(np.mean(np.square(ratios)))) if ratios else None
            )
            if arm_name == "gaussian_radius":
                sampled = [item["sampled_gaussian_radius_A"] for _, _, item in values]
                errors = [item["realized_minus_sampled_radius_A"] for _, _, item in values]
                stats["sampled_radius"] = _local_parameterization_series(sampled)
                stats["realized_minus_sampled_radius"] = {
                    **_local_parameterization_series(errors),
                    "max_abs_A": float(max(map(abs, errors))) if errors else None,
                }
            return stats

        displacement[arm_name] = {
            "global": displacement_bucket(rows),
            "by_sigma": {
                str(sigma): displacement_bucket([
                    row for row in rows if row["sigma_A_provisional"] == sigma
                ]) for sigma in sigmas
            },
        }
        structural[arm_name] = {}
        effort[arm_name] = {"direction_trials_by_site": {}, "row_direction_search_effort": {}}
        for sigma in [None, *sigmas]:
            subset = rows if sigma is None else [
                row for row in rows if row["sigma_A_provisional"] == sigma
            ]
            label = "global" if sigma is None else str(sigma)
            accepted = [row[arm_name] for row in subset if row[arm_name]["generated"]]
            change_names = (
                "mobile_displacement_rms_A",
                "mobile_mobile_pair_distance_changes_abs_A",
                "nearest_host_distance_changes_A",
            )
            structural_values = {
                name: [value for record in accepted
                       for value in record["structural_change"][name]
                       if value is not None]
                for name in change_names[1:]
            }
            structural_values[change_names[0]] = [
                record["structural_change"][change_names[0]] for record in accepted
                if record["structural_change"][change_names[0]] is not None
            ]
            structural[arm_name][label] = {
                name: _local_parameterization_series(values)
                for name, values in structural_values.items()
            }
            trials = [trial for record in subset for trial in (record.get("direction_trials_by_site") or [])]
            effort[arm_name]["direction_trials_by_site"][label] = {
                str(value): trials.count(value) for value in sorted(set(trials))
            }
            row_effort = [record["direction_search_effort"] for record in subset
                          if record.get("direction_search_effort") is not None]
            effort[arm_name]["row_direction_search_effort"][label] = {
                str(value): row_effort.count(value) for value in sorted(set(row_effort))
            }

    return {
        "requested_pairs": requested,
        "fixed_accepted": sum(row["fixed_radius"]["generated"] for row in rows),
        "fixed_exhausted": sum(row["fixed_radius"]["proposal_status"] == "EXHAUSTED" for row in rows),
        "gaussian_accepted": sum(row["gaussian_radius"]["generated"] for row in rows),
        "gaussian_exhausted": sum(row["gaussian_radius"]["proposal_status"] == "EXHAUSTED" for row in rows),
        "both_generated": sum(row["fixed_radius"]["generated"] and row["gaussian_radius"]["generated"] for row in rows),
        "fixed_only_generated": sum(row["fixed_radius"]["generated"] and not row["gaussian_radius"]["generated"] for row in rows),
        "gaussian_only_generated": sum(not row["fixed_radius"]["generated"] and row["gaussian_radius"]["generated"] for row in rows),
        "neither_generated": sum(not row["fixed_radius"]["generated"] and not row["gaussian_radius"]["generated"] for row in rows),
        "arms": {name: arm_counts(name, rows) for name in arm_names},
        "status_cross_tab": status_cross,
        "novelty_cross_tab": novelty_cross,
        "novelty_cross_tab_denominator": sum(
            row["fixed_radius"]["generated"] and row["gaussian_radius"]["generated"] for row in rows
        ),
        "useful_cross_tab": useful_cross,
        "useful_cross_tab_denominator": sum(
            row["fixed_radius"]["generated"] and row["gaussian_radius"]["generated"] for row in rows
        ),
        "displacement": displacement,
        "structural_change": {
            name: {"global": values["global"], "by_sigma": {
                str(sigma): values[str(sigma)] for sigma in sigmas
            }} for name, values in structural.items()
        },
        "effort": effort,
    }


def build_mobile_ion_local_parameterization_paired_diagnostic_panel(
    parents,
    *,
    mobile_ion,
    sigma_values_A_provisional,
    base_seeds,
    diagnostic_config_hash,
    fixed_radius_max_direction_trials,
    gaussian_radius_max_direction_trials,
):
    """Build a deterministic observational comparison of two local parameterizations."""
    parents = list(parents)
    sigmas = list(sigma_values_A_provisional)
    seeds = list(base_seeds)
    for name, value in (
        ("fixed_radius_max_direction_trials", fixed_radius_max_direction_trials),
        ("gaussian_radius_max_direction_trials", gaussian_radius_max_direction_trials),
    ):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")

    rows = []
    for parent_record in parents:
        if parent_record.structure is None or not parent_record.perturbable:
            raise ValueError(
                "local parameterization diagnostic requires a perturbable structured parent: "
                f"{parent_record.parent_id}"
            )
        source = parent_record.structure
        mobile_indices = _mobile_site_indices(source, mobile_ion)
        if not mobile_indices:
            raise ValueError(f"no sites matching mobile_ion='{mobile_ion}' in {parent_record.parent_id}")
        for sigma in sigmas:
            for seed in seeds:
                pair_payload = {
                    "parent_id": parent_record.parent_id,
                    "sigma_A_provisional": sigma,
                    "base_seed": seed,
                }
                pair_id = hashlib.sha256(json.dumps(
                    pair_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")).hexdigest()
                rng_parent_identity = json.dumps({
                    "pair_id": pair_id,
                    "mobile_ion": mobile_ion,
                    "diagnostic_config_hash": diagnostic_config_hash,
                }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                arm_specs = (
                    ("fixed_radius", "mobile-ion-local-clearance-displace",
                     "mobile-ion-local-clearance-displace-v1",
                     fixed_radius_max_direction_trials, op_mobile_ion_local_clearance_displace_v1),
                    ("gaussian_radius", "mobile-ion-local-clearance-gaussian-radius",
                     "mobile-ion-local-clearance-gaussian-radius-v1",
                     gaussian_radius_max_direction_trials,
                     op_mobile_ion_local_clearance_gaussian_radius_v1),
                )
                arm_rows = {}
                for arm_name, operator_name, operator_version, budget, operator in arm_specs:
                    identity = derive_candidate_supply_v2_operator_rng_identity(
                        parent_id=rng_parent_identity,
                        seed=seed,
                        operator_name=operator_name,
                        operator_version=operator_version,
                    )
                    rng_seed = _operator_rng_seed(identity)
                    child, params = operator(
                        source.copy(), np.random.default_rng(rng_seed),
                        mobile_ion=mobile_ion,
                        sigma_A_provisional=sigma,
                        max_direction_trials=budget,
                        operator_rng_identity=identity,
                    )
                    params = {**params, "operator_rng_identity": identity,
                              "operator_rng_seed": rng_seed}
                    status = params.get("proposal_status")
                    if status not in {"ACCEPTED", "EXHAUSTED"}:
                        raise RuntimeError(f"unknown {arm_name} proposal status: {status}")
                    if (status == "ACCEPTED") != (child is not None):
                        raise RuntimeError(f"{arm_name} proposal status disagrees with child result")
                    if child is None:
                        effort = params.get("direction_trials_by_site")
                        arm = {
                            "operator_name": params["operator"],
                            "operator_version": params["operator_version"],
                            "operator_rng_identity": identity,
                            "operator_rng_seed": rng_seed,
                            "proposal_status": "EXHAUSTED",
                            "generated": False,
                            "child_material_id": None,
                            "child_structure_dict": None,
                            "novelty_tag": None, "novelty_matched": None,
                            "novelty_matcher_version": None,
                            "same_cell_mode": None, "skip_structure_reduction": None,
                            "p0_state": None, "p0_plausible": None,
                            "p0_neutrality_ok": None, "p0_pauling_ok": None,
                            "p0_geometry_ok": None, "p0_details": None,
                            "geometry_clash_evidence": None, "useful": None,
                        }
                    else:
                        arm = _local_parameterization_child_record(
                            source, child, params, pair_id=pair_id, arm_name=arm_name
                        )
                        if (child.composition != source.composition
                                or child.lattice != source.lattice
                                or len(child) != len(source)
                                or [str(site.species) for site in child]
                                != [str(site.species) for site in source]):
                            raise RuntimeError(f"{arm_name} changed same-cell structure invariants")
                        arm["operator_provenance"] = dict(params)
                        arm["direction_trials_by_site"] = params.get("direction_trials_by_site")
                        trial_values = params.get("direction_trials_by_site")
                        arm["direction_search_effort"] = (
                            sum(trial_values) if trial_values is not None else None
                        )
                        arm["sampled_gaussian_components_A"] = params.get(
                            "sampled_gaussian_components_A"
                        )
                        arm["sampled_radii_A"] = params.get("sampled_radii_A")
                        site_displacements = []
                        for offset, site_index in enumerate(mobile_indices):
                            realized = float(source.lattice.get_distance_and_image(
                                source[site_index].frac_coords, child[site_index].frac_coords
                            )[0])
                            item = {
                                "mobile_site_index": site_index,
                                "minimum_image_displacement_A": realized,
                                "requested_sigma_A_provisional": sigma,
                            }
                            if arm_name == "gaussian_radius":
                                sampled = params["sampled_radii_A"][offset]
                                item["sampled_gaussian_radius_A"] = float(sampled)
                                item["realized_minus_sampled_radius_A"] = realized - float(sampled)
                            site_displacements.append(item)
                        arm["site_displacements"] = site_displacements
                        arm["derived_mobile_displacements_A"] = [
                            item["minimum_image_displacement_A"] for item in site_displacements
                        ]
                        arm["structural_change"] = _local_parameterization_geometry_summary(
                            source, child, mobile_indices
                        )
                        arm["structural_change"]["mobile_displacement_rms_A"] = float(
                            np.sqrt(np.mean(np.square(arm["derived_mobile_displacements_A"])))
                        )
                    if child is None:
                        arm["operator_provenance"] = dict(params)
                        arm["direction_trials_by_site"] = params.get("direction_trials_by_site")
                        arm["direction_search_effort"] = (
                            sum(params["direction_trials_by_site"])
                            if params.get("direction_trials_by_site") is not None else None
                        )
                        arm["sampled_gaussian_components_A"] = params.get(
                            "sampled_gaussian_components_A"
                        )
                        arm["sampled_radii_A"] = params.get("sampled_radii_A")
                        arm["site_displacements"] = []
                        arm["derived_mobile_displacements_A"] = []
                        arm["structural_change"] = None
                    arm_rows[arm_name] = arm

                fixed, gaussian = arm_rows["fixed_radius"], arm_rows["gaussian_radius"]
                transitions = {
                    "generation": f"{fixed['proposal_status']}_TO_{gaussian['proposal_status']}",
                    "novelty": (
                        f"{fixed['novelty_tag'].upper()}_TO_{gaussian['novelty_tag'].upper()}"
                        if fixed["generated"] and gaussian["generated"] else None
                    ),
                    "useful": (
                        f"{str(fixed['useful']).upper()}_TO_{str(gaussian['useful']).upper()}"
                        if fixed["generated"] and gaussian["generated"] else None
                    ),
                }
                rows.append({
                    "pair_id": pair_id,
                    "parent_id": parent_record.parent_id,
                    "chemical_family": parent_record.chemical_family,
                    "target_species": mobile_ion,
                    "sigma_A_provisional": sigma,
                    "base_seed": seed,
                    "diagnostic_config_hash": diagnostic_config_hash,
                    "site_count": len(source),
                    "target_site_count": len(mobile_indices),
                    "fixed_radius": fixed,
                    "gaussian_radius": gaussian,
                    "transitions": transitions,
                })

    return {
        "schema_version": "mobile-ion-local-parameterization-paired-diagnostic-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "authorization": {
            "scheduler_activation": False,
            "p1_eligibility": False,
            "downstream_scientific_claims": False,
            "operator_superiority": False,
            "automatic_promotion": False,
            "sigma_selection": False,
            "parent_exclusion": False,
            "chemistry_exclusion": False,
            "threshold_modification": False,
        },
        "metadata": {
            "fixed_radius_operator_name": "mobile-ion-local-clearance-displace",
            "fixed_radius_operator_version": "mobile-ion-local-clearance-displace-v1",
            "gaussian_radius_operator_name": "mobile-ion-local-clearance-gaussian-radius",
            "gaussian_radius_operator_version": "mobile-ion-local-clearance-gaussian-radius-v1",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "target_species": mobile_ion,
            "sigma_values_A_provisional": sigmas,
            "base_seeds": seeds,
            "ordered_parent_ids": [parent.parent_id for parent in parents],
            "diagnostic_config_hash": diagnostic_config_hash,
            "fixed_radius_max_direction_trials": fixed_radius_max_direction_trials,
            "gaussian_radius_max_direction_trials": gaussian_radius_max_direction_trials,
        },
        "rows": rows,
        "summary": _local_parameterization_summary(rows, sigmas),
    }


def build_mobile_ion_clearance_paired_diagnostic_panel(
    parents,
    *,
    mobile_ion,
    sigma_values_A_provisional,
    base_seeds,
    diagnostic_config_hash,
    max_attempts,
    matcher=None,
):
    """Build an in-memory, observationally paired operator comparison panel.

    Both arms receive fresh structures and RNGs initialized from the same
    stable pair stream. Operator names/versions remain arm-specific provenance;
    the shared stream makes clearance proposal one identical to baseline.
    """
    parents = list(parents)
    sigmas = list(sigma_values_A_provisional)
    seeds = list(base_seeds)
    rows = []

    for parent in parents:
        if parent.structure is None or not parent.perturbable:
            raise ValueError(
                f"paired diagnostic requires a perturbable structured parent: {parent.parent_id}"
            )
        for sigma in sigmas:
            for seed in seeds:
                pair_payload = {
                    "parent_id": parent.parent_id,
                    "sigma_A_provisional": sigma,
                    "base_seed": seed,
                }
                pair_bytes = json.dumps(
                    pair_payload, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
                pair_id = hashlib.sha256(pair_bytes).hexdigest()
                rng_parent_identity = json.dumps(
                    {
                        "pair_id": pair_id,
                        "mobile_ion": mobile_ion,
                        "diagnostic_config_hash": diagnostic_config_hash,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                pair_rng_identity = derive_candidate_supply_v2_operator_rng_identity(
                    parent_id=rng_parent_identity,
                    seed=seed,
                    operator_name="mobile-ion-displace-paired",
                    operator_version="mobile-ion-clearance-paired-v1",
                )
                pair_rng_seed = int(pair_rng_identity[:16], 16) & ((1 << 63) - 1)
                source = parent.structure

                baseline_child, baseline_params = op_mobile_ion_displace_v2(
                    source.copy(),
                    np.random.default_rng(pair_rng_seed),
                    mobile_ion=mobile_ion,
                    sigma_A_provisional=sigma,
                    operator_rng_identity=pair_rng_identity,
                )
                baseline_p0 = evaluate_p0(
                    str(baseline_child.composition.reduced_formula),
                    structure=baseline_child,
                )
                baseline_novelty = classify_candidate_supply_v2_novelty(
                    source, baseline_child, matcher=matcher, operator_name="displace"
                )
                baseline_plausible = (
                    baseline_p0.existence_state.value == "PLAUSIBLE"
                )
                baseline_useful = (
                    baseline_novelty["novelty_tag"] == "novel"
                    and baseline_plausible
                )
                baseline_geometry_details = (
                    baseline_p0.details.get("geometry", {})
                    if isinstance(baseline_p0.details, dict) else {}
                )
                baseline_child_id = hashlib.sha256(
                    json.dumps(
                        {"pair_id": pair_id, "arm": "baseline",
                         "structure": baseline_child.as_dict()},
                        sort_keys=True, default=str,
                    ).encode("utf-8")
                ).hexdigest()[:16]
                baseline = {
                    "operator_name": baseline_params["operator"],
                    "operator_version": baseline_params["operator_version"],
                    "operator_rng_identity": pair_rng_identity,
                    "operator_rng_seed": pair_rng_seed,
                    "generated": True,
                    "child_material_id": f"g-clearance-pair-{baseline_child_id}",
                    "child_structure_dict": baseline_child.as_dict(),
                    "novelty_tag": baseline_novelty["novelty_tag"],
                    "novelty_matched": baseline_novelty["novelty_matched"],
                    "novelty_matcher_version": baseline_novelty[
                        "novelty_matcher_version"
                    ],
                    "p0_state": baseline_p0.existence_state.value,
                    "p0_plausible": baseline_plausible,
                    "p0_geometry_ok": baseline_p0.geometry_ok,
                    "p0_details": _p0_details_json_ready(baseline_p0.details),
                    "geometry_clash_evidence": baseline_geometry_details,
                    "useful": baseline_useful,
                }

                clearance_child, clearance_params = (
                    op_mobile_ion_displace_clearance_v1(
                        source.copy(),
                        np.random.default_rng(pair_rng_seed),
                        mobile_ion=mobile_ion,
                        sigma_A_provisional=sigma,
                        max_attempts=max_attempts,
                        operator_rng_identity=pair_rng_identity,
                    )
                )
                accepted = clearance_params["proposal_status"] == "ACCEPTED"
                if accepted != (clearance_child is not None):
                    raise RuntimeError(
                        "clearance operator result disagrees with proposal_status"
                    )
                if accepted:
                    clearance_p0 = evaluate_p0(
                        str(clearance_child.composition.reduced_formula),
                        structure=clearance_child,
                    )
                    clearance_novelty = classify_candidate_supply_v2_novelty(
                        source, clearance_child, matcher=matcher,
                        operator_name="displace",
                    )
                    clearance_plausible = (
                        clearance_p0.existence_state.value == "PLAUSIBLE"
                    )
                    clearance_useful = (
                        clearance_novelty["novelty_tag"] == "novel"
                        and clearance_plausible
                    )
                    clearance_geometry_details = (
                        clearance_p0.details.get("geometry", {})
                        if isinstance(clearance_p0.details, dict) else {}
                    )
                    clearance_child_id = hashlib.sha256(
                        json.dumps(
                            {"pair_id": pair_id, "arm": "clearance",
                             "structure": clearance_child.as_dict()},
                            sort_keys=True, default=str,
                        ).encode("utf-8")
                    ).hexdigest()[:16]
                    clearance = {
                        "operator_name": clearance_params["operator"],
                        "operator_version": clearance_params["operator_version"],
                        "operator_rng_identity": pair_rng_identity,
                        "operator_rng_seed": pair_rng_seed,
                        "proposal_status": "ACCEPTED",
                        "attempts_used": clearance_params["attempts_used"],
                        "rejected_clash_attempts": clearance_params[
                            "rejected_clash_attempts"
                        ],
                        "generated": True,
                        "child_material_id": f"g-clearance-pair-{clearance_child_id}",
                        "child_structure_dict": clearance_child.as_dict(),
                        "novelty_tag": clearance_novelty["novelty_tag"],
                        "novelty_matched": clearance_novelty["novelty_matched"],
                        "novelty_matcher_version": clearance_novelty[
                            "novelty_matcher_version"
                        ],
                        "p0_state": clearance_p0.existence_state.value,
                        "p0_plausible": clearance_plausible,
                        "p0_geometry_ok": clearance_p0.geometry_ok,
                        "p0_details": _p0_details_json_ready(clearance_p0.details),
                        "geometry_clash_evidence": clearance_geometry_details,
                        "useful": clearance_useful,
                    }
                else:
                    clearance = {
                        "operator_name": clearance_params["operator"],
                        "operator_version": clearance_params["operator_version"],
                        "operator_rng_identity": pair_rng_identity,
                        "operator_rng_seed": pair_rng_seed,
                        "proposal_status": "EXHAUSTED",
                        "attempts_used": clearance_params["attempts_used"],
                        "rejected_clash_attempts": clearance_params[
                            "rejected_clash_attempts"
                        ],
                        "generated": False,
                        "child_material_id": None,
                        "child_structure_dict": None,
                        "novelty_tag": None,
                        "novelty_matched": None,
                        "novelty_matcher_version": None,
                        "p0_state": None,
                        "p0_plausible": None,
                        "p0_geometry_ok": None,
                        "p0_details": None,
                        "geometry_clash_evidence": None,
                        "useful": None,
                    }

                baseline_geometry = _paired_geometry_label(
                    baseline["p0_geometry_ok"]
                )
                clearance_geometry = (
                    _paired_geometry_label(clearance["p0_geometry_ok"])
                    if accepted else "EXHAUSTED"
                )
                baseline_useful_label = _paired_useful_label(baseline["useful"])
                clearance_useful_label = _paired_useful_label(clearance["useful"])
                row = {
                    "pair_id": pair_id,
                    "pair_rng_identity": pair_rng_identity,
                    "pair_rng_seed": pair_rng_seed,
                    "parent_id": parent.parent_id,
                    "chemical_family": parent.chemical_family,
                    "target_species": mobile_ion,
                    "sigma_A_provisional": sigma,
                    "base_seed": seed,
                    "diagnostic_config_hash": diagnostic_config_hash,
                    "site_count": len(source),
                    "target_site_count": len(_mobile_site_indices(source, mobile_ion)),
                    "baseline": baseline,
                    "clearance": clearance,
                    "transitions": {
                        "geometry": f"{baseline_geometry}_TO_{clearance_geometry}",
                        "useful": (
                            f"{baseline_useful_label}_TO_{clearance_useful_label}"
                        ),
                    },
                }
                rows.append(row)

    authorization = {
        "scheduler_activation": False,
        "p1_eligibility": False,
        "downstream_scientific_claims": False,
        "operator_superiority": False,
        "automatic_parent_exclusion": False,
        "chemistry_exclusion": False,
        "threshold_modification": False,
    }
    return {
        "schema_version": "mobile-ion-clearance-paired-diagnostic-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "authorization": authorization,
        "metadata": {
            "baseline_operator_name": "mobile-ion-displace",
            "baseline_operator_version": "mobile-ion-displace-v2",
            "clearance_operator_name": "mobile-ion-displace-clearance",
            "clearance_operator_version": "mobile-ion-displace-clearance-v1",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "target_species": mobile_ion,
            "sigma_values_A_provisional": sigmas,
            "base_seeds": seeds,
            "ordered_parent_ids": [parent.parent_id for parent in parents],
            "diagnostic_config_hash": diagnostic_config_hash,
            "max_attempts": max_attempts,
        },
        "rows": rows,
        "summary": _paired_diagnostic_summary(rows),
    }
    per_parent_geometry_frequency = {
        parent_id: {
            "observations_count": values["observations_count"],
            "geometry_fail_count": values["geometry_fail_count"],
            "geometry_fail_frequency": (
                values["geometry_fail_count"] / values["observations_count"]
                if values["observations_count"] else 0.0
            ),
        }
        for parent_id, values in pooled.items()
    }

    all_families = sorted({row["parent_chemical_family"] for row in rows})
    family_summary = {}
    for family in all_families:
        family_parent_ids = sorted({
            row["parent_id"] for row in rows
            if row["parent_chemical_family"] == family
        })
        family_persistent = sum(
            any(
                parent_persistence_by_sigma[str(sigma)][parent_id]["persistent_useful"]
                for sigma in sigmas
            )
            for parent_id in family_parent_ids
        )
        ever_useful = sum(pooled[parent_id]["useful_count"] > 0 for parent_id in family_parent_ids)
        family_summary[family] = {
            "parent_count": len(family_parent_ids),
            "persistent_useful_count": family_persistent,
            "ever_useful_count": ever_useful,
            "never_useful_count": len(family_parent_ids) - ever_useful,
        }

    # Exact-site-count bins are deterministic and retain full resolution.
    by_site_count = {}
    for site_count in sorted({row["site_count"] for row in rows}):
        bin_rows = [row for row in rows if row["site_count"] == site_count]
        by_site_count[str(site_count)] = {
            **_panel_counts(bin_rows),
            "site_count_min": site_count,
            "site_count_max": site_count,
        }
    by_chemical_family = {
        family: _panel_counts([
            row for row in rows if row["parent_chemical_family"] == family
        ])
        for family in sorted({row["parent_chemical_family"] for row in rows})
    }

    return {
        **_panel_counts(rows),
        "per_sigma": per_sigma,
        "per_parent_useful_frequency": per_parent_useful_frequency,
        "per_parent_geometry_failure_frequency": per_parent_geometry_frequency,
        "persistent_useful_threshold": threshold,
        "persistent_useful_min_fraction": threshold,
        "parent_persistence_by_sigma": parent_persistence_by_sigma,
        "family_persistence": family_summary,
        "family_persistence_by_sigma": family_persistence_by_sigma,
        "by_chemical_family": by_chemical_family,
        "by_site_count_bin": by_site_count,
    }


def build_mobile_ion_displacement_diagnostic_panel(
    parents,
    *,
    mobile_ion,
    sigma_values_A_provisional,
    base_seeds,
    diagnostic_config_hash,
    persistent_useful_threshold=0.75,
    matcher=None,
):
    """Build an observational panel from fresh cohort-diagnostic executions."""
    parents = list(parents)
    sigmas = list(sigma_values_A_provisional)
    seeds = list(base_seeds)
    parent_ids = [parent.parent_id for parent in parents]
    ordered_cohort_identity = hashlib.sha256(
        json.dumps(parent_ids, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    rows = []
    runs = []
    for sigma in sigmas:
        for seed in seeds:
            report = diagnose_mobile_ion_displacement_cohort(
                parents,
                mobile_ion=mobile_ion,
                sigma_A_provisional=sigma,
                base_seed=seed,
                diagnostic_config_hash=diagnostic_config_hash,
                matcher=matcher,
            )
            run_rows = []
            for raw_row in report["rows"]:
                row = dict(raw_row)
                row["sigma_A_provisional"] = sigma
                row["base_seed"] = seed
                run_rows.append(row)
            rows.extend(run_rows)
            runs.append({"sigma_A_provisional": sigma, "base_seed": seed})

    # Normalize pymatgen/NumPy nested values into their JSON representation
    # before deriving any panel summaries; these rows are the persisted source.
    rows = json.loads(json.dumps(rows, sort_keys=True, ensure_ascii=False))
    for run in runs:
        run_rows = [
            row for row in rows
            if row["sigma_A_provisional"] == run["sigma_A_provisional"]
            and row["base_seed"] == run["base_seed"]
        ]
        run["summary"] = _panel_counts(run_rows)
    return {
        "schema_version": "mobile-ion-displacement-diagnostic-panel-v2",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "authorization": {
            "scheduler_activation": False,
            "p1_eligibility": False,
            "downstream_scientific_superiority_claim": False,
        },
        "activation_authorized": False,
        "p1_eligibility_authorized": False,
        "downstream_scientific_claims_authorized": False,
        "metadata": {
            "operator_name": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "target_species": mobile_ion,
            "sigma_values_A_provisional": sigmas,
            "base_seeds": seeds,
            "ordered_parent_ids": parent_ids,
            "ordered_cohort_identity": ordered_cohort_identity,
            "diagnostic_config_hash": diagnostic_config_hash,
            "persistent_useful_threshold": persistent_useful_threshold,
        },
        "runs": runs,
        "rows": rows,
        "summary": _panel_summary(
            rows, runs, sigmas, seeds, persistent_useful_threshold
        ),
    }


def write_mobile_ion_displacement_diagnostic_panel(path, parents, **kwargs):
    """Build and atomically persist deterministic panel JSON at ``path``."""
    payload = build_mobile_ion_displacement_diagnostic_panel(parents, **kwargs)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
            newline="\n",
        ) as temporary:
            temp_path = Path(temporary.name)
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temp_path, output_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()
    return payload


def diagnose_mobile_ion_displacement_cohort(
    parents,
    *,
    mobile_ion: str,
    sigma_A_provisional: float,
    base_seed: int,
    diagnostic_config_hash: str,
    matcher=None,
    matcher_ltol_provisional: float = 0.2,
    matcher_stol_provisional: float = 0.3,
    matcher_angle_tol_provisional: float = 5.0,
):
    """Evaluate one diagnostic child per applicable parent, in input order.

    The matcher tolerances and displacement sigma are PROVISIONAL. Counts are
    observational and do not authorize an operator or downstream execution.
    """

    if matcher is None:
        matcher = StructureMatcher(
            ltol=matcher_ltol_provisional,
            stol=matcher_stol_provisional,
            angle_tol=matcher_angle_tol_provisional,
        )

    rows = []
    for parent in parents:
        structure = parent.structure
        row = {
            "parent_id": parent.parent_id,
            "parent_chemical_family": parent.chemical_family,
            "target_species": mobile_ion,
            "sigma_A_provisional": sigma_A_provisional,
            "diagnostic_config_hash": diagnostic_config_hash,
            "operator_name": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "base_seed": base_seed,
            "site_count": len(structure) if structure is not None else 0,
            "target_site_count": 0,
            "parent_guard_state": "INAPPLICABLE",
            "diagnostic_state": "INAPPLICABLE",
            "reason": None,
            "parent_p0_neutrality_ok": None,
            "operator_rng_identity": None,
            "operator_rng_seed": None,
            "child_material_id": None,
            "child_structure_dict": None,
            "operator_params": None,
            "p0_neutrality_ok": None,
            "p0_pauling_ok": None,
            "p0_geometry_ok": None,
            "p0_state": None,
            "p0_details": None,
            "novelty_tag": None,
            "novelty_matched": None,
            "novelty_matcher_version": None,
        }

        if not parent.perturbable or structure is None:
            row["reason"] = "parent is not perturbable or has no structure"
            rows.append(row)
            continue

        row["target_site_count"] = len(_mobile_site_indices(structure, mobile_ion))
        parent_p0 = evaluate_p0(
            str(structure.composition.reduced_formula), structure=structure
        )
        row["parent_p0_neutrality_ok"] = parent_p0.neutrality_ok
        if parent_p0.neutrality_ok is False:
            row["parent_guard_state"] = "BLOCKED_BY_PARENT_P0"
            row["diagnostic_state"] = "BLOCKED_BY_PARENT_P0"
            row["reason"] = "parent P0 neutrality blocks execution"
            rows.append(row)
            continue

        if row["target_site_count"] == 0:
            row["reason"] = f"no sites matching mobile_ion='{mobile_ion}'"
            rows.append(row)
            continue

        identity = derive_candidate_supply_v2_operator_rng_identity(
            parent_id=parent.parent_id,
            seed=base_seed,
            operator_name="mobile-ion-displace",
            operator_version="mobile-ion-displace-v2",
        )
        rng_seed = _operator_rng_seed(identity)
        child_structure, operator_params = op_mobile_ion_displace_v2(
            structure,
            np.random.default_rng(rng_seed),
            mobile_ion=mobile_ion,
            sigma_A_provisional=sigma_A_provisional,
            operator_rng_identity=identity,
        )
        child_structure_dict = child_structure.as_dict()
        child_p0 = evaluate_p0(
            str(child_structure.composition.reduced_formula),
            structure=child_structure,
        )
        # The v2 classifier uses "displace" as its same-cell comparison type;
        # the diagnostic row retains the actual versioned operator identity.
        novelty = classify_candidate_supply_v2_novelty(
            structure,
            child_structure,
            matcher=matcher,
            operator_name="displace",
        )
        identity_payload = {
            "parent_id": parent.parent_id,
            "diagnostic_config_hash": diagnostic_config_hash,
            "operator_rng_identity": identity,
            "operator_params": operator_params,
            "child_structure": child_structure_dict,
        }
        child_hash = hashlib.sha256(
            json.dumps(identity_payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]

        row.update(
            parent_guard_state="ELIGIBLE",
            diagnostic_state="GENERATED",
            operator_rng_identity=identity,
            operator_rng_seed=rng_seed,
            child_material_id=f"g-v2-diagnostic-{child_hash}",
            child_structure_dict=child_structure_dict,
            operator_params=operator_params,
            p0_neutrality_ok=child_p0.neutrality_ok,
            p0_pauling_ok=child_p0.pauling_ok,
            p0_geometry_ok=child_p0.geometry_ok,
            p0_state=child_p0.existence_state.value,
            p0_details=_p0_details_json_ready(child_p0.details),
            novelty_tag=novelty["novelty_tag"],
            novelty_matched=novelty["novelty_matched"],
            novelty_matcher_version=novelty["novelty_matcher_version"],
        )
        rows.append(row)

    return {"rows": rows, "summary": _summary(rows)}
