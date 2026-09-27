"""Observational CPU cohort diagnostic for versioned mobile-ion displacement."""

from __future__ import annotations

import hashlib
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
    op_mobile_ion_displace_v2,
)
from rudeus.generation.scheduler import (
    _operator_rng_seed,
    derive_candidate_supply_v2_operator_rng_identity,
)


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
        "schema_version": "mobile-ion-displacement-diagnostic-panel-v1",
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
            novelty_tag=novelty["novelty_tag"],
            novelty_matched=novelty["novelty_matched"],
            novelty_matcher_version=novelty["novelty_matcher_version"],
        )
        rows.append(row)

    return {"rows": rows, "summary": _summary(rows)}
