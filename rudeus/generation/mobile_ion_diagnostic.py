"""Observational CPU cohort diagnostic for versioned mobile-ion displacement."""

from __future__ import annotations

import hashlib
import json

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
