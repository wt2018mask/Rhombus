"""Observational taxonomy derived from persisted mobile-ion P0 evidence."""

from __future__ import annotations

from collections import defaultdict


_UNSPECIFIED = "GEOMETRY_FAIL_UNSPECIFIED"
_CLASH = "GEOMETRY_FAIL_CLASH"
_COORDINATION = "GEOMETRY_FAIL_COORDINATION"
_GEOMETRY_CATEGORIES = (_CLASH, _COORDINATION, _UNSPECIFIED)
_FRACTION_EDGES = (0.0, 0.25, 0.5, 1.0)
_V2_SCHEMA = "mobile-ion-displacement-diagnostic-panel-v2"


def _json_ordered(value):
    """Copy JSON-shaped evidence into deterministic, non-mutating containers."""
    if isinstance(value, dict):
        return {key: _json_ordered(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_json_ordered(item) for item in value]
    return value


def _classify_row(row, schema_version):
    state = row["diagnostic_state"]
    if state in ("BLOCKED_BY_PARENT_P0", "INAPPLICABLE"):
        return state, [], [], "NOT_APPLICABLE"
    if state != "GENERATED":
        raise ValueError(f"unknown diagnostic state: {state}")

    geometry_ok = row.get("p0_geometry_ok")
    p0_state = row.get("p0_state")
    categories = []
    evidence = []
    consistency = "CONSISTENT"

    details = row.get("p0_details") if schema_version == _V2_SCHEMA else None
    if geometry_ok is False:
        if not isinstance(details, dict):
            categories = [_UNSPECIFIED]
            consistency = "UNAVAILABLE" if schema_version != _V2_SCHEMA else "INCOMPLETE"
        else:
            geometry = details.get("geometry")
            coordination = details.get("coordination")
            geometry_valid = (
                isinstance(geometry, dict)
                and isinstance(geometry.get("clash_detected"), bool)
            )
            coordination_valid = (
                isinstance(coordination, dict)
                and (
                    coordination.get("unphysical_coordination") is True
                    or coordination.get("all_sites_sane") is True
                    or (
                        coordination.get("coordination_skipped") is True
                        and coordination.get("all_sites_sane") is None
                    )
                )
            )
            if not geometry_valid or not coordination_valid:
                categories = [_UNSPECIFIED]
                consistency = "INCOMPLETE"
            elif p0_state != "FAIL":
                categories = [_UNSPECIFIED]
                consistency = "CONTRADICTORY"
            else:
                if geometry["clash_detected"] is True:
                    categories.append(_CLASH)
                    clash_evidence = {"geometry": _json_ordered(geometry)}
                    if "provisional_clash_ratio" in details:
                        clash_evidence["provisional_clash_ratio"] = _json_ordered(
                            details["provisional_clash_ratio"]
                        )
                    evidence.append({"category": _CLASH, "evidence": clash_evidence})
                if coordination.get("unphysical_coordination") is True:
                    categories.append(_COORDINATION)
                    evidence.append({
                        "category": _COORDINATION,
                        "evidence": {"coordination": _json_ordered(coordination)},
                    })
                if not categories:
                    categories = [_UNSPECIFIED]
                    consistency = "CONTRADICTORY"
    elif geometry_ok is True:
        if details is not None and isinstance(details, dict):
            geometry = details.get("geometry")
            coordination = details.get("coordination")
            contradicts = (
                isinstance(geometry, dict) and geometry.get("clash_detected") is True
            ) or (
                isinstance(coordination, dict)
                and coordination.get("unphysical_coordination") is True
            )
            if contradicts:
                consistency = "CONTRADICTORY"
        if p0_state == "PLAUSIBLE":
            return "P0_PLAUSIBLE", categories, evidence, consistency
        if p0_state == "FAIL":
            return "P0_FAIL_NON_GEOMETRY", categories, evidence, consistency
    elif p0_state == "UNKNOWN":
        return "P0_UNKNOWN", categories, evidence, "INCOMPLETE"

    if categories:
        return categories[0], categories, evidence, consistency
    return "P0_STATUS_UNSPECIFIED", [], [], "INCOMPLETE"


def _row_has_geometry_failure(row):
    return row["diagnostic_state"] == "GENERATED" and row.get("p0_geometry_ok") is False


def _is_specific(category):
    return category in (_CLASH, _COORDINATION)


def _row_categories(row):
    return row["geometry_failure_categories"]


def _metrics(rows):
    generated = [row for row in rows if row["diagnostic_state"] == "GENERATED"]
    failures = [row for row in generated if _row_has_geometry_failure(row)]
    row_counts = {category: 0 for category in _GEOMETRY_CATEGORIES}
    occurrences = {category: 0 for category in _GEOMETRY_CATEGORIES}
    for row in failures:
        for category in _row_categories(row):
            row_counts[category] += 1
            occurrences[category] += 1
    by_generated = {
        category: count / len(generated) if generated else 0.0
        for category, count in row_counts.items()
    }
    by_failures = {
        category: count / len(failures) if failures else 0.0
        for category, count in row_counts.items()
    }
    return {
        "generated_count": len(generated),
        "generated_observations": len(generated),
        "geometry_fail_row_count": len(failures),
        "geometry_fail_count": len(failures),  # v1 compatibility alias
        "category_row_counts": row_counts,
        "category_occurrence_counts": occurrences,
        "fraction_of_generated_rows_with_category": by_generated,
        "fraction_of_geometry_fail_rows_with_category": by_failures,
        "geometry_failure_category_counts": row_counts,  # v1 compatibility alias
        "geometry_failure_category_frequencies": by_generated,
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


def _context_summary(parents):
    generated = sum(parent["generated_observations"] for parent in parents)
    failures = sum(parent["geometry_fail_row_count"] for parent in parents)
    row_counts = {category: 0 for category in _GEOMETRY_CATEGORIES}
    occurrence_counts = {category: 0 for category in _GEOMETRY_CATEGORIES}
    specific_rows = unspecified_rows = 0
    for parent in parents:
        for category in _GEOMETRY_CATEGORIES:
            row_counts[category] += parent["category_row_counts"][category]
            occurrence_counts[category] += parent["category_occurrence_counts"][category]
        specific_rows += parent["rows_with_specific_cause"]
        unspecified_rows += parent["rows_unspecified"]
    return {
        "parent_count": len(parents),
        "generated_rows": generated,
        "geometry_fail_rows": failures,
        "category_row_counts": row_counts,
        "category_occurrence_counts": occurrence_counts,
        "rows_with_specific_cause": specific_rows,
        "rows_unspecified": unspecified_rows,
        "geometry_cause_evidence_coverage": specific_rows / failures if failures else 0.0,
        # Existing v1 summary names remain available.
        "generated_observations": generated,
        "geometry_fail_count": failures,
    }


def build_mobile_ion_geometry_failure_taxonomy(panel_payload):
    """Classify persisted P0 outcomes, using v2 details only when explicitly present."""
    metadata = panel_payload["metadata"]
    parent_ids = metadata["ordered_parent_ids"]
    sigmas = metadata["sigma_values_A_provisional"]
    parent_order = {parent_id: index for index, parent_id in enumerate(parent_ids)}
    sigma_order = {sigma: index for index, sigma in enumerate(sigmas)}
    seed_order = {seed: index for index, seed in enumerate(metadata["base_seeds"])}
    schema_version = panel_payload.get("schema_version")

    rows = []
    for raw in panel_payload["rows"]:
        category, categories, evidence, consistency = _classify_row(raw, schema_version)
        row = {
            **raw,
            "evidence_category": category,
            "geometry_failure_categories": categories,
            "geometry_failure_evidence": evidence,
            "evidence_consistency": consistency,
        }
        if "p0_details" in raw:
            row["p0_details"] = _json_ordered(raw["p0_details"])
        rows.append(row)
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
        totals = _metrics(parent_rows)
        category_counts = totals["category_row_counts"]
        maximum = max(category_counts.values(), default=0)
        dominant = [category for category, count in category_counts.items() if count == maximum]
        specific_rows = sum(
            _row_has_geometry_failure(row)
            and any(_is_specific(category) for category in _row_categories(row))
            for row in parent_rows
        )
        unspecified_rows = sum(
            _row_has_geometry_failure(row) and _UNSPECIFIED in _row_categories(row)
            for row in parent_rows
        )
        parents.append({
            "parent_id": parent_id,
            "chemical_family": parent_rows[0]["parent_chemical_family"],
            "site_count": parent_rows[0]["site_count"],
            "target_site_count": parent_rows[0]["target_site_count"],
            **totals,
            "rows_with_specific_cause": specific_rows,
            "rows_unspecified": unspecified_rows,
            "dominant_geometry_failure_category": (
                dominant[0] if maximum > 0 and len(dominant) == 1 else None
            ),
            "per_sigma": [
                {
                    "sigma_A_provisional": sigma,
                    **_metrics([
                        row for row in parent_rows
                        if row["sigma_A_provisional"] == sigma
                    ]),
                }
                for sigma in sigmas
            ],
        })

    generated_rows = [row for row in rows if row["diagnostic_state"] == "GENERATED"]
    geometry_fail_rows = [row for row in generated_rows if _row_has_geometry_failure(row)]
    rows_with_specific = sum(
        any(_is_specific(category) for category in _row_categories(row))
        for row in geometry_fail_rows
    )
    rows_unspecified = sum(_UNSPECIFIED in _row_categories(row) for row in geometry_fail_rows)
    category_row_counts = {category: 0 for category in _GEOMETRY_CATEGORIES}
    category_occurrences = {category: 0 for category in _GEOMETRY_CATEGORIES}
    for row in geometry_fail_rows:
        for category in _row_categories(row):
            category_row_counts[category] += 1
            category_occurrences[category] += 1

    cohort = {
        "total_generated": len(generated_rows),
        "total_geometry_fail_rows": len(geometry_fail_rows),
        "rows_with_specific_cause": rows_with_specific,
        "rows_unspecified": rows_unspecified,
        "category_row_counts": category_row_counts,
        "category_occurrence_counts": category_occurrences,
        "geometry_cause_evidence_coverage": (
            rows_with_specific / len(geometry_fail_rows) if geometry_fail_rows else 0.0
        ),
        # Existing v1 summary names remain available.
        "total_geometry_failures": len(geometry_fail_rows),
        "by_category": {},
    }
    all_categories = sorted({row["evidence_category"] for row in rows} | set(_GEOMETRY_CATEGORIES))
    for category in all_categories:
        category_rows = [row for row in geometry_fail_rows if category in _row_categories(row)]
        whole_category_count = sum(row["evidence_category"] == category for row in rows)
        cohort["by_category"][category] = {
            "count": whole_category_count,
            "geometry_fail_count": len(category_rows),
            "fraction_of_generated": len(category_rows) / len(generated_rows) if generated_rows else 0.0,
            "fraction_of_geometry_failures": len(category_rows) / len(geometry_fail_rows) if geometry_fail_rows else 0.0,
        }

    def grouped(key):
        groups = defaultdict(list)
        for parent in parents:
            groups[str(key(parent))].append(parent)
        return {name: _context_summary(groups[name]) for name in sorted(groups)}

    first_counts = {str(sigma): {category: 0 for category in _GEOMETRY_CATEGORIES} for sigma in sigmas}
    first_ids = {str(sigma): [] for sigma in sigmas}
    for parent in parents:
        for category in _GEOMETRY_CATEGORIES:
            observed = [
                item["sigma_A_provisional"] for item in parent["per_sigma"]
                if item["category_row_counts"][category] > 0
            ]
            if observed:
                first = min(observed)
                first_counts[str(first)][category] += 1
                if parent["parent_id"] not in first_ids[str(first)]:
                    first_ids[str(first)].append(parent["parent_id"])

    sigma_transitions = []
    for sigma in sigmas:
        sigma_rows = [row for row in rows if row["sigma_A_provisional"] == sigma]
        sigma_metrics = _metrics(sigma_rows)
        sigma_transitions.append({
            "sigma_A_provisional": sigma,
            **sigma_metrics,
            "category_row_counts": sigma_metrics["category_row_counts"],
            "category_occurrence_counts": sigma_metrics["category_occurrence_counts"],
        })

    detail_available = any(
        category in (_CLASH, _COORDINATION)
        for row in geometry_fail_rows for category in _row_categories(row)
    )
    return {
        "schema_version": "mobile-ion-geometry-failure-taxonomy-v2",
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
        "source": {"schema_version": schema_version, **metadata},
        "limitations": {
            "geometry_failure_cause_detail_available": detail_available,
            "geometry_failure_fallback_category": _UNSPECIFIED,
        },
        "rows": rows,
        "parents": parents,
        "summary": {
            "total_generated": len(generated_rows),
            "total_geometry_failures": len(geometry_fail_rows),
            "total_geometry_fail_rows": len(geometry_fail_rows),
            "cohort": cohort,
            "sigma_transitions": sigma_transitions,
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
