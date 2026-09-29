"""RED contract for evidence-limited P0 geometry-failure taxonomy.

The persisted panel schema contains p0_state, p0_neutrality_ok,
p0_pauling_ok, and p0_geometry_ok. It does not persist P0 ``details``,
clash measurements, coordination results, or geometry reason codes. Therefore
these fixtures require the generic GEOMETRY_FAIL_UNSPECIFIED fallback; the
context fields intentionally cannot be used to infer a physical cause.
"""

from __future__ import annotations

import copy


SIGMAS = [0.25, 0.30, 0.35, 0.40]
PARENTS = [
    ("fixture:geom-030", "alpha", 8, 2),
    ("fixture:geom-035", "beta", 16, 4),
    ("fixture:geom-040", "gamma", 24, 12),
    ("fixture:non-geometry", "alpha", 8, 1),
    ("fixture:plausible", "beta", 16, 8),
    ("fixture:blocked", "gamma", 24, 6),
    ("fixture:inapplicable", "beta", 8, 0),
]


def _panel():
    rows = []
    for parent_id, family, sites, target_sites in PARENTS:
        for sigma in SIGMAS:
            row = {
                "parent_id": parent_id,
                "parent_chemical_family": family,
                "site_count": sites,
                "target_site_count": target_sites,
                "target_species": "Mg",
                "sigma_A_provisional": sigma,
                "base_seed": 17,
                "diagnostic_state": "GENERATED",
                "child_material_id": f"child-{parent_id}-{sigma}",
                "novelty_tag": "rediscovery",
                "p0_state": "PLAUSIBLE",
                "p0_neutrality_ok": True,
                "p0_pauling_ok": True,
                "p0_geometry_ok": True,
            }
            if parent_id.startswith("fixture:geom-"):
                threshold = float(parent_id.rsplit("-", 1)[1]) / 100
                if sigma >= threshold:
                    row.update(
                        p0_state="FAIL",
                        p0_geometry_ok=False,
                        novelty_tag="novel" if sigma == threshold else "rediscovery",
                    )
            elif parent_id == "fixture:non-geometry" and sigma == 0.25:
                row.update(p0_state="FAIL", p0_neutrality_ok=False)
            elif parent_id == "fixture:blocked":
                row.update(
                    diagnostic_state="BLOCKED_BY_PARENT_P0",
                    child_material_id=None,
                    novelty_tag=None,
                    p0_state=None,
                    p0_neutrality_ok=None,
                    p0_pauling_ok=None,
                    p0_geometry_ok=None,
                )
            elif parent_id == "fixture:inapplicable":
                row.update(
                    diagnostic_state="INAPPLICABLE",
                    child_material_id=None,
                    novelty_tag=None,
                    p0_state=None,
                    p0_neutrality_ok=None,
                    p0_pauling_ok=None,
                    p0_geometry_ok=None,
                )
            rows.append(row)
    return {
        "schema_version": "mobile-ion-displacement-diagnostic-panel-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "authorization": {
            "scheduler_activation": False,
            "p1_eligibility": False,
            "downstream_scientific_superiority_claim": False,
        },
        "metadata": {
            "operator_name": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "target_species": "Mg",
            "sigma_values_A_provisional": SIGMAS[:],
            "base_seeds": [17],
            "ordered_parent_ids": [parent[0] for parent in PARENTS],
            "ordered_cohort_identity": "synthetic-v1",
            "diagnostic_config_hash": "synthetic-config-v1",
        },
        "rows": rows,
    }


def _taxonomy(panel):
    from rudeus.generation.mobile_ion_geometry_taxonomy import (
        build_mobile_ion_geometry_failure_taxonomy,
    )

    return build_mobile_ion_geometry_failure_taxonomy(panel)


def test_geometry_failures_without_persisted_causes_use_only_unspecified_fallback():
    panel = _panel()
    geometry_rows = [
        row for row in panel["rows"]
        if row["diagnostic_state"] == "GENERATED" and row["p0_geometry_ok"] is False
    ]
    assert geometry_rows
    assert not any(
        any(token in key.lower() for token in ("detail", "cause", "clash", "coordination"))
        for row in geometry_rows for key in row
    )

    taxonomy = _taxonomy(panel)
    assert taxonomy["limitations"]["geometry_failure_cause_detail_available"] is False
    assert taxonomy["limitations"]["geometry_failure_fallback_category"] == "GEOMETRY_FAIL_UNSPECIFIED"
    categorized = [
        row for row in taxonomy["rows"]
        if row["diagnostic_state"] == "GENERATED" and row["p0_geometry_ok"] is False
    ]
    assert len(categorized) == len(geometry_rows)
    assert {row["evidence_category"] for row in categorized} == {"GEOMETRY_FAIL_UNSPECIFIED"}

    # Family, target occupancy, sigma, novelty, and material identity must not
    # be promoted into unsupported physical diagnoses.
    assert len({row["parent_chemical_family"] for row in geometry_rows}) == 3
    assert len({row["target_site_count"] for row in geometry_rows}) == 3
    assert len({row["sigma_A_provisional"] for row in geometry_rows}) > 1
    assert len({row["novelty_tag"] for row in geometry_rows}) > 1


def test_taxonomy_distinguishes_p0_statuses_and_reconciles_all_geometry_failures():
    taxonomy = _taxonomy(_panel())
    rows = taxonomy["rows"]
    categories = {
        (row["parent_id"], row["sigma_A_provisional"]): row["evidence_category"]
        for row in rows
    }
    assert categories[("fixture:non-geometry", 0.25)] == "P0_FAIL_NON_GEOMETRY"
    assert categories[("fixture:plausible", 0.25)] == "P0_PLAUSIBLE"
    assert categories[("fixture:blocked", 0.25)] == "BLOCKED_BY_PARENT_P0"
    assert categories[("fixture:inapplicable", 0.25)] == "INAPPLICABLE"

    generated_geometry_fails = sum(
        row["diagnostic_state"] == "GENERATED" and row["p0_geometry_ok"] is False
        for row in rows
    )
    cohort = taxonomy["summary"]["cohort"]
    assert cohort["total_geometry_failures"] == generated_geometry_fails
    assert sum(
        item["geometry_fail_count"] for item in cohort["by_category"].values()
    ) == generated_geometry_fails
    assert cohort["by_category"]["GEOMETRY_FAIL_UNSPECIFIED"]["fraction_of_generated"] == (
        generated_geometry_fails / cohort["total_generated"]
    )
    assert cohort["by_category"]["GEOMETRY_FAIL_UNSPECIFIED"]["fraction_of_geometry_failures"] == 1.0


def test_parent_and_parent_sigma_category_counts_reconcile_to_raw_rows():
    panel = _panel()
    taxonomy = _taxonomy(panel)
    raw = panel["rows"]
    parents = taxonomy["parents"]
    assert [parent["parent_id"] for parent in parents] == panel["metadata"]["ordered_parent_ids"]

    for parent in parents:
        source_rows = [row for row in raw if row["parent_id"] == parent["parent_id"]]
        generated = [row for row in source_rows if row["diagnostic_state"] == "GENERATED"]
        geometry_failures = sum(row["p0_geometry_ok"] is False for row in generated)
        assert parent["generated_observations"] == len(generated)
        assert parent["geometry_fail_count"] == geometry_failures
        assert sum(parent["geometry_failure_category_counts"].values()) == geometry_failures
        for sigma_row, sigma in zip(parent["per_sigma"], SIGMAS):
            sigma_source = [
                row for row in source_rows
                if row["sigma_A_provisional"] == sigma and row["diagnostic_state"] == "GENERATED"
            ]
            sigma_failures = sum(row["p0_geometry_ok"] is False for row in sigma_source)
            assert sigma_row["generated_count"] == len(sigma_source)
            assert sigma_row["geometry_fail_count"] == sigma_failures
            assert sum(sigma_row["geometry_failure_category_counts"].values()) == sigma_failures
            assert sigma_row["geometry_failure_category_frequencies"]["GEOMETRY_FAIL_UNSPECIFIED"] == (
                sigma_failures / len(sigma_source) if sigma_source else 0.0
            )

    assert sum(parent["geometry_fail_count"] for parent in parents) == sum(
        row["diagnostic_state"] == "GENERATED" and row["p0_geometry_ok"] is False
        for row in raw
    )


def test_sigma_transitions_and_context_aggregates_keep_metadata_order():
    taxonomy = _taxonomy(_panel())
    assert [item["sigma_A_provisional"] for item in taxonomy["summary"]["sigma_transitions"]] == SIGMAS
    transitions = taxonomy["summary"]["first_parent_counts_by_category"]
    for sigma, parent_id in ((0.30, "fixture:geom-030"),
                             (0.35, "fixture:geom-035"),
                             (0.40, "fixture:geom-040")):
        assert transitions[str(sigma)]["GEOMETRY_FAIL_UNSPECIFIED"] == 1
        assert parent_id in taxonomy["summary"]["first_parent_ids_by_sigma"][str(sigma)]

    summary = taxonomy["summary"]
    assert sum(value["generated_observations"] for value in summary["by_chemical_family"].values()) == summary["total_generated"]
    assert sum(value["generated_observations"] for value in summary["by_target_site_count"].values()) == summary["total_generated"]
    assert sum(value["generated_observations"] for value in summary["by_target_fraction_bin"].values()) == summary["total_generated"]


def test_taxonomy_is_deterministic_observational_and_does_not_mutate_source_rows():
    panel = _panel()
    original = copy.deepcopy(panel)
    result = _taxonomy(panel)
    assert panel == original
    assert result == _taxonomy(copy.deepcopy(panel))
    assert result["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert result["authorization"] == {
        "scheduler_activation": False,
        "p1_eligibility": False,
        "operator_superiority": False,
        "parent_exclusion": False,
        "chemistry_exclusion": False,
        "threshold_modification": False,
    }
