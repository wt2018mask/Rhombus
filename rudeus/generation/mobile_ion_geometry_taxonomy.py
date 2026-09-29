"""Observational taxonomy of P0 outcomes retained in mobile-ion panel rows.

The panel persists a geometry Boolean, not P0's detailed geometry or
coordination evidence. A failed geometry check therefore has no known physical
cause in this artifact.
"""

from __future__ import annotations

from collections import defaultdict


_GEOMETRY_FAIL_UNSPECIFIED = "GEOMETRY_FAIL_UNSPECIFIED"
_GEOMETRY_CATEGORIES = (_GEOMETRY_FAIL_UNSPECIFIED,)
_FRACTION_EDGES = (0.0, 0.25, 0.5, 1.0)


def _category(row):
    state = row["diagnostic_state"]
    if state == "BLOCKED_BY_PARENT_P0":
        return state
    if state == "INAPPLICABLE":
        return state
    if state != "GENERATED":
        raise ValueError(f"unknown diagnostic state: {state}")
    if row["p0_geometry_ok"] is False:
        return _GEOMETRY_FAIL_UNSPECIFIED
    if row["p0_state"] == "PLAUSIBLE":
        return "P0_PLAUSIBLE"
    if row["p0_state"] == "FAIL" and row["p0_geometry_ok"] is True:
        return "P0_FAIL_NON_GEOMETRY"
    if row["p0_state"] == "UNKNOWN":
        return "P0_UNKNOWN"
    return "P0_STATUS_UNSPECIFIED"


def _geometry_counts(rows):
    generated = sum(row["diagnostic_state"] == "GENERATED" for row in rows)
    categories = {
        category: sum(row["evidence_category"] == category for row in rows)
        for category in _GEOMETRY_CATEGORIES
    }
    failures = sum(categories.values())
    return {
        "generated_count": generated,
        "geometry_fail_count": failures,
        "geometry_failure_category_counts": categories,
        "geometry_failure_category_frequencies": {
            category: count / generated if generated else 0.0
            for category, count in categories.items()
        },
    }


def _fraction_bin(site_count, target_site_count):
    if site_count <= 0:
        return "UNKNOWN"
    fraction = target_site_count / site_count
    if fraction == 0:
        return "0"
    for lower, upper in zip(_FRACTION_EDGES, _FRACTION_EDGES[1:]):
        if lower < fraction <= upper:
            return f"({lower:g},{upper:g}]"
    raise ValueError("target fraction must be in [0, 1]")


def build_mobile_ion_geometry_failure_taxonomy(panel_payload):
    """Summarize only P0 evidence actually persisted in the panel's raw rows."""
    metadata = panel_payload["metadata"]
    parent_ids = metadata["ordered_parent_ids"]
    sigmas = metadata["sigma_values_A_provisional"]
    seeds = metadata["base_seeds"]
    parent_order = {parent_id: index for index, parent_id in enumerate(parent_ids)}
    sigma_order = {sigma: index for index, sigma in enumerate(sigmas)}
    seed_order = {seed: index for index, seed in enumerate(seeds)}

    rows = [{**row, "evidence_category": _category(row)} for row in panel_payload["rows"]]
    rows.sort(key=lambda row: (
        parent_order[row["parent_id"]],
        sigma_order[row["sigma_A_provisional"]],
        seed_order[row["base_seed"]],
    ))

    parents = []
    for parent_id in parent_ids:
        parent_rows = [row for row in rows if row["parent_id"] == parent_id]
        if not parent_rows:
            raise ValueError(f"missing raw observations for {parent_id}")
        counts = _geometry_counts(parent_rows)
        category_counts = counts["geometry_failure_category_counts"]
        maximum = max(category_counts.values(), default=0)
        dominant = [name for name, count in category_counts.items() if count == maximum]
        parents.append({
            "parent_id": parent_id,
            "chemical_family": parent_rows[0]["parent_chemical_family"],
            "site_count": parent_rows[0]["site_count"],
            "target_site_count": parent_rows[0]["target_site_count"],
            "generated_observations": counts["generated_count"],
            "geometry_fail_count": counts["geometry_fail_count"],
            "geometry_failure_category_counts": category_counts,
            "geometry_failure_category_frequencies": counts["geometry_failure_category_frequencies"],
            "dominant_geometry_failure_category": (
                dominant[0] if maximum > 0 and len(dominant) == 1 else None
            ),
            "per_sigma": [
                {
                    "sigma_A_provisional": sigma,
                    **_geometry_counts([
                        row for row in parent_rows
                        if row["sigma_A_provisional"] == sigma
                    ]),
                }
                for sigma in sigmas
            ],
        })

    cohort = _geometry_counts(rows)
    total_generated = cohort["generated_count"]
    total_failures = cohort["geometry_fail_count"]
    by_category = {}
    for category in sorted({row["evidence_category"] for row in rows} | set(_GEOMETRY_CATEGORIES)):
        count = sum(row["evidence_category"] == category for row in rows)
        geometry_fail_count = count if category in _GEOMETRY_CATEGORIES else 0
        by_category[category] = {
            "count": count,
            "geometry_fail_count": geometry_fail_count,
            "fraction_of_generated": (
                geometry_fail_count / total_generated if total_generated else 0.0
            ),
            "fraction_of_geometry_failures": (
                geometry_fail_count / total_failures if total_failures else 0.0
            ),
        }

    def grouped(key):
        groups = defaultdict(list)
        for parent in parents:
            groups[str(key(parent))].append(parent)
        return {
            name: {
                "parent_count": len(group),
                "generated_observations": sum(p["generated_observations"] for p in group),
                "geometry_fail_count": sum(p["geometry_fail_count"] for p in group),
            }
            for name, group in sorted(groups.items())
        }

    first_counts = {
        str(sigma): {category: 0 for category in _GEOMETRY_CATEGORIES}
        for sigma in sigmas
    }
    first_ids = {str(sigma): [] for sigma in sigmas}
    for parent in parents:
        for category in _GEOMETRY_CATEGORIES:
            observed = [
                item["sigma_A_provisional"] for item in parent["per_sigma"]
                if item["geometry_failure_category_counts"][category] > 0
            ]
            if observed:
                first = min(observed)
                first_counts[str(first)][category] += 1
                if parent["parent_id"] not in first_ids[str(first)]:
                    first_ids[str(first)].append(parent["parent_id"])

    return {
        "schema_version": "mobile-ion-geometry-failure-taxonomy-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "authorization": {
            "scheduler_activation": False,
            "p1_eligibility": False,
            "operator_superiority": False,
            "parent_exclusion": False,
            "chemistry_exclusion": False,
            "threshold_modification": False,
        },
        "activation_authorized": False,
        "p1_eligibility_authorized": False,
        "downstream_scientific_claims_authorized": False,
        "source": {"schema_version": panel_payload["schema_version"], **metadata},
        "limitations": {
            "geometry_failure_cause_detail_available": False,
            "geometry_failure_fallback_category": _GEOMETRY_FAIL_UNSPECIFIED,
        },
        "rows": rows,
        "parents": parents,
        "summary": {
            "total_generated": total_generated,
            "total_geometry_failures": total_failures,
            "cohort": {
                "total_generated": total_generated,
                "total_geometry_failures": total_failures,
                "by_category": by_category,
            },
            "sigma_transitions": [
                {"sigma_A_provisional": sigma, **_geometry_counts([
                    row for row in rows if row["sigma_A_provisional"] == sigma
                ])}
                for sigma in sigmas
            ],
            "first_parent_counts_by_category": first_counts,
            "first_parent_ids_by_sigma": first_ids,
            "by_chemical_family": grouped(lambda parent: parent["chemical_family"]),
            "by_target_site_count": grouped(lambda parent: parent["target_site_count"]),
            "target_fraction_bin_edges": list(_FRACTION_EDGES),
            "by_target_fraction_bin": grouped(lambda parent: _fraction_bin(
                parent["site_count"], parent["target_site_count"]
            )),
        },
    }
