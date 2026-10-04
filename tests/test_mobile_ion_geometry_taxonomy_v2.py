"""RED contracts for interpreting persisted v2 P0 geometry evidence.

P0 clash semantics: a failure is emitted for a site pair when distance is
less than the sum of the two atomic radii times provisional_clash_ratio; the
detail payload preserves the first detected pair and measured distance/cutoff.
P0 coordination semantics: CrystalNN passes only coordination numbers from 1
through 16; an out-of-range value returns unphysical_coordination=True. A
disordered no-majority structure skips that check. The ratio is context for
the existing clash check and is not an independent taxonomy threshold.
"""

from __future__ import annotations

import copy


SIGMAS = [0.30, 0.35, 0.40]
PARENTS = [
    ("fixture:clash", "alpha", 8, 2),
    ("fixture:coordination", "beta", 12, 3),
    ("fixture:both", "gamma", 16, 8),
    ("fixture:unspecified", "alpha", 24, 6),
    ("fixture:plausible", "beta", 8, 4),
    ("fixture:non-geometry", "gamma", 12, 2),
    ("fixture:contradiction", "alpha", 16, 1),
    ("fixture:blocked", "beta", 8, 2),
    ("fixture:inapplicable", "gamma", 8, 0),
]


def _passing_details():
    return {
        "neutrality": {"neutral_found": True, "elements": ["Mg", "O"]},
        "pauling": {"pauling_test": True, "electronegativities": [1.31, 3.44]},
        "geometry": {"clash_detected": False},
        "coordination": {"mean_coordination": 4.0, "all_sites_sane": True},
        "provisional_clash_ratio": 0.6,
    }


def _clash_details():
    return {
        "neutrality": {"neutral_found": True, "elements": ["Mg", "O"]},
        "pauling": {"pauling_test": True, "electronegativities": [1.31, 3.44]},
        "geometry": {
            "clash_detected": True,
            "atom_i": "Mg",
            "atom_j": "O",
            "distance": 0.8,
            "min_allowed": 1.1,
        },
        "coordination": {"mean_coordination": 4.0, "all_sites_sane": True},
        "provisional_clash_ratio": 0.6,
    }


def _coordination_details():
    return {
        "neutrality": {"neutral_found": True, "elements": ["Mg", "O"]},
        "pauling": {"pauling_test": True, "electronegativities": [1.31, 3.44]},
        "geometry": {"clash_detected": False},
        "coordination": {
            "unphysical_coordination": True,
            "site_index": 0,
            "site_specie": "Mg",
            "coordination_number": 0,
        },
        "provisional_clash_ratio": 0.6,
    }


def _panel(schema="mobile-ion-displacement-diagnostic-panel-v2"):
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
                "base_seed": 29,
                "diagnostic_state": "GENERATED",
                "child_material_id": f"child-{parent_id}-{sigma}",
                "novelty_tag": "rediscovery",
                "p0_state": "PLAUSIBLE",
                "p0_neutrality_ok": True,
                "p0_pauling_ok": True,
                "p0_geometry_ok": True,
                "p0_details": _passing_details(),
            }
            if parent_id == "fixture:clash":
                row.update(p0_state="FAIL", p0_geometry_ok=False,
                           p0_details=_clash_details())
            elif parent_id == "fixture:coordination" and sigma >= 0.35:
                row.update(p0_state="FAIL", p0_geometry_ok=False,
                           p0_details=_coordination_details())
            elif parent_id == "fixture:both" and sigma == 0.40:
                details = _clash_details()
                details["coordination"] = _coordination_details()["coordination"]
                row.update(p0_state="FAIL", p0_geometry_ok=False,
                           p0_details=details)
            elif parent_id == "fixture:unspecified":
                row.update(p0_state="FAIL", p0_geometry_ok=False)
                if sigma == 0.30:
                    # Contradictory persisted result: both reported components
                    # pass although aggregate geometry says fail.
                    row["p0_details"] = _passing_details()
                elif sigma == 0.35:
                    row["p0_details"] = {"geometry": {}}
                else:
                    row["p0_details"] = {
                        "geometry": {"error": "geometry_clash_check_error"},
                        "provisional_clash_ratio": 0.6,
                    }
            elif parent_id == "fixture:non-geometry":
                row.update(
                    p0_state="FAIL",
                    p0_neutrality_ok=False,
                    p0_details={**_passing_details(),
                                "neutrality": {"neutral_found": False,
                                               "elements": ["Mg", "O"]}},
                )
            elif parent_id == "fixture:contradiction" and sigma == 0.35:
                # A malformed/inconsistent persisted row cannot be promoted
                # into a geometry failure when the aggregate Boolean passes.
                row["p0_details"] = _clash_details()
            elif parent_id == "fixture:blocked":
                row.update(
                    diagnostic_state="BLOCKED_BY_PARENT_P0",
                    child_material_id=None,
                    novelty_tag=None,
                    p0_state=None,
                    p0_neutrality_ok=None,
                    p0_pauling_ok=None,
                    p0_geometry_ok=None,
                    p0_details=None,
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
                    p0_details=None,
                )
            rows.append(row)
    return {
        "schema_version": schema,
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "metadata": {
            "operator_name": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
            "target_species": "Mg",
            "sigma_values_A_provisional": SIGMAS[:],
            "base_seeds": [29],
            "ordered_parent_ids": [parent[0] for parent in PARENTS],
            "ordered_cohort_identity": "synthetic-v2-cohort",
            "diagnostic_config_hash": "synthetic-v2-config",
        },
        "rows": rows,
    }


def _taxonomy(panel=None):
    from rudeus.generation.mobile_ion_geometry_taxonomy import (
        build_mobile_ion_geometry_failure_taxonomy,
    )

    return build_mobile_ion_geometry_failure_taxonomy(panel or _panel())


def _row_map(taxonomy):
    return {
        (row["parent_id"], row["sigma_A_provisional"]): row
        for row in taxonomy["rows"]
    }


def test_v2_categories_follow_explicit_p0_evidence_and_keep_supporting_values():
    panel = _panel()
    taxonomy = _taxonomy(panel)
    rows = _row_map(taxonomy)

    clash = rows[("fixture:clash", 0.30)]
    assert clash["geometry_failure_categories"] == ["GEOMETRY_FAIL_CLASH"]
    assert clash["geometry_failure_evidence"] == [{
        "category": "GEOMETRY_FAIL_CLASH",
        "evidence": {
            "geometry": panel["rows"][0]["p0_details"]["geometry"],
            "provisional_clash_ratio": 0.6,
        },
    }]

    coordination = rows[("fixture:coordination", 0.35)]
    assert coordination["geometry_failure_categories"] == ["GEOMETRY_FAIL_COORDINATION"]
    assert coordination["geometry_failure_evidence"][0]["evidence"]["coordination"] == (
        _coordination_details()["coordination"]
    )

    both = rows[("fixture:both", 0.40)]
    assert both["geometry_failure_categories"] == [
        "GEOMETRY_FAIL_CLASH", "GEOMETRY_FAIL_COORDINATION"
    ]
    assert [item["category"] for item in both["geometry_failure_evidence"]] == (
        both["geometry_failure_categories"]
    )
    source_both = next(
        row for row in panel["rows"]
        if row["parent_id"] == "fixture:both" and row["sigma_A_provisional"] == 0.40
    )
    assert both["p0_details"] == source_both["p0_details"]


def test_missing_malformed_and_contradictory_details_fall_back_safely():
    rows = _row_map(_taxonomy())
    for sigma in (0.30, 0.35, 0.40):
        item = rows[("fixture:unspecified", sigma)]
        assert item["geometry_failure_categories"] == ["GEOMETRY_FAIL_UNSPECIFIED"]
    assert rows[("fixture:unspecified", 0.30)]["evidence_consistency"] == "CONTRADICTORY"
    assert rows[("fixture:unspecified", 0.35)]["evidence_consistency"] == "INCOMPLETE"
    assert rows[("fixture:unspecified", 0.40)]["evidence_consistency"] == "INCOMPLETE"

    benign_conflict = rows[("fixture:contradiction", 0.35)]
    assert benign_conflict["evidence_category"] == "P0_PLAUSIBLE"
    assert benign_conflict["geometry_failure_categories"] == []
    assert benign_conflict["evidence_consistency"] == "CONTRADICTORY"


def test_provisional_clash_ratio_alone_never_creates_a_clash_category():
    panel = _panel()
    benign = next(
        row for row in panel["rows"]
        if row["parent_id"] == "fixture:plausible" and row["sigma_A_provisional"] == 0.30
    )
    benign["p0_details"]["provisional_clash_ratio"] = 12345.0
    classified = _row_map(_taxonomy(panel))[("fixture:plausible", 0.30)]
    assert classified["evidence_category"] == "P0_PLAUSIBLE"
    assert classified["geometry_failure_categories"] == []
    assert classified["p0_details"]["provisional_clash_ratio"] == 12345.0


def test_multilabel_counts_reconcile_by_unique_rows_and_category_occurrences():
    panel = _panel()
    taxonomy = _taxonomy(panel)
    summary = taxonomy["summary"]
    raw_generated = [row for row in panel["rows"] if row["diagnostic_state"] == "GENERATED"]
    raw_failures = [row for row in raw_generated if row["p0_geometry_ok"] is False]
    cohort = summary["cohort"]

    assert cohort["total_generated"] == len(raw_generated)
    assert cohort["total_geometry_fail_rows"] == len(raw_failures)
    assert cohort["rows_with_specific_cause"] + cohort["rows_unspecified"] == len(raw_failures)
    assert cohort["rows_with_specific_cause"] == 6
    assert cohort["rows_unspecified"] == 3
    assert cohort["geometry_cause_evidence_coverage"] == 6 / 9
    assert cohort["category_row_counts"]["GEOMETRY_FAIL_CLASH"] == 4
    assert cohort["category_row_counts"]["GEOMETRY_FAIL_COORDINATION"] == 3
    assert cohort["category_occurrence_counts"]["GEOMETRY_FAIL_CLASH"] == 4
    assert cohort["category_occurrence_counts"]["GEOMETRY_FAIL_COORDINATION"] == 3
    assert cohort["category_row_counts"]["GEOMETRY_FAIL_UNSPECIFIED"] == 3
    assert sum(cohort["category_occurrence_counts"].values()) == 10

    categorized_failure_ids = {
        (row["parent_id"], row["sigma_A_provisional"])
        for row in taxonomy["rows"]
        if row["diagnostic_state"] == "GENERATED"
        and row["p0_geometry_ok"] is False
        and row["geometry_failure_categories"]
    }
    raw_failure_ids = {
        (row["parent_id"], row["sigma_A_provisional"])
        for row in raw_failures
    }
    assert categorized_failure_ids == raw_failure_ids

    assert sum(parent["geometry_fail_row_count"] for parent in taxonomy["parents"]) == len(raw_failures)
    both = next(parent for parent in taxonomy["parents"] if parent["parent_id"] == "fixture:both")
    assert both["generated_observations"] == 3
    assert both["geometry_fail_row_count"] == 1
    assert both["category_row_counts"]["GEOMETRY_FAIL_CLASH"] == 1
    assert both["category_row_counts"]["GEOMETRY_FAIL_COORDINATION"] == 1
    assert both["category_occurrence_counts"]["GEOMETRY_FAIL_CLASH"] == 1
    assert both["category_occurrence_counts"]["GEOMETRY_FAIL_COORDINATION"] == 1
    assert both["fraction_of_generated_rows_with_category"]["GEOMETRY_FAIL_CLASH"] == 1 / 3
    assert both["fraction_of_geometry_fail_rows_with_category"]["GEOMETRY_FAIL_COORDINATION"] == 1.0

    for parent in taxonomy["parents"]:
        for sigma_row in parent["per_sigma"]:
            assert sum(sigma_row["category_row_counts"].values()) >= sigma_row["geometry_fail_row_count"]
            sigma_source = [
                row for row in panel["rows"]
                if row["parent_id"] == parent["parent_id"]
                and row["sigma_A_provisional"] == sigma_row["sigma_A_provisional"]
                and row["diagnostic_state"] == "GENERATED"
            ]
            assert sigma_row["fraction_of_generated_rows_with_category"]["GEOMETRY_FAIL_UNSPECIFIED"] == (
                sigma_row["category_row_counts"]["GEOMETRY_FAIL_UNSPECIFIED"] / len(sigma_source)
                if sigma_source else 0.0
            )
            assert sigma_row["fraction_of_geometry_fail_rows_with_category"]["GEOMETRY_FAIL_UNSPECIFIED"] == (
                sigma_row["category_row_counts"]["GEOMETRY_FAIL_UNSPECIFIED"] / sigma_row["geometry_fail_row_count"]
                if sigma_row["geometry_fail_row_count"] else 0.0
            )
            assert sigma_row["geometry_fail_row_count"] == sum(
                row["p0_geometry_ok"] is False
                for row in panel["rows"]
                if row["parent_id"] == parent["parent_id"]
                and row["sigma_A_provisional"] == sigma_row["sigma_A_provisional"]
                and row["diagnostic_state"] == "GENERATED"
            )


def test_sigma_transitions_context_summaries_and_zero_failure_semantics():
    taxonomy = _taxonomy()
    summary = taxonomy["summary"]
    assert [row["sigma_A_provisional"] for row in summary["sigma_transitions"]] == SIGMAS
    first = summary["first_parent_counts_by_category"]
    assert first["0.3"]["GEOMETRY_FAIL_CLASH"] == 1
    assert first["0.35"]["GEOMETRY_FAIL_COORDINATION"] == 1
    assert first["0.4"]["GEOMETRY_FAIL_CLASH"] == 1
    assert first["0.4"]["GEOMETRY_FAIL_COORDINATION"] == 1
    assert first["0.3"]["GEOMETRY_FAIL_UNSPECIFIED"] == 1

    for key in ("by_chemical_family", "by_target_site_count", "by_target_fraction_bin"):
        assert sum(item["generated_rows"] for item in summary[key].values()) == summary["total_generated"]
        assert sum(item["geometry_fail_rows"] for item in summary[key].values()) == summary["total_geometry_fail_rows"]
        for item in summary[key].values():
            assert sum(item["category_row_counts"].values()) >= item["geometry_fail_rows"]
            assert item["rows_unspecified"] == item["category_row_counts"]["GEOMETRY_FAIL_UNSPECIFIED"]
            expected_coverage = (
                (item["geometry_fail_rows"] - item["rows_unspecified"])
                / item["geometry_fail_rows"] if item["geometry_fail_rows"] else 0.0
            )
            assert item["geometry_cause_evidence_coverage"] == expected_coverage

    no_fail = _panel()
    for row in no_fail["rows"]:
        if row["diagnostic_state"] == "GENERATED":
            row["p0_geometry_ok"] = True
            row["p0_state"] = "PLAUSIBLE"
            row["p0_details"] = _passing_details()
    zero = _taxonomy(no_fail)["summary"]["cohort"]
    assert zero["total_geometry_fail_rows"] == 0
    assert zero["geometry_cause_evidence_coverage"] == 0.0


def test_v1_stays_unspecified_and_v2_output_is_ordered_observational_and_species_neutral():
    v1 = _panel("mobile-ion-displacement-diagnostic-panel-v1")
    v1["rows"] = [copy.deepcopy(v1["rows"][0])]
    v1["rows"][0].pop("p0_details")
    v1["metadata"]["ordered_parent_ids"] = ["fixture:clash"]
    old = _row_map(_taxonomy(v1))[("fixture:clash", 0.30)]
    assert old["geometry_failure_categories"] == ["GEOMETRY_FAIL_UNSPECIFIED"]

    panel = _panel()
    original = copy.deepcopy(panel)
    result = _taxonomy(panel)
    assert panel == original
    assert result["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert all(value is False for value in result["authorization"].values())
    assert result["source"]["target_species"] == "Mg"
    assert [row["parent_id"] for row in result["parents"]] == panel["metadata"]["ordered_parent_ids"]
    assert [row["sigma_A_provisional"] for row in result["summary"]["sigma_transitions"]] == SIGMAS
    permuted = copy.deepcopy(panel)
    permuted["rows"].reverse()
    assert result == _taxonomy(permuted)

    rows = _row_map(result)
    assert rows[("fixture:blocked", 0.30)]["evidence_category"] == "BLOCKED_BY_PARENT_P0"
    assert rows[("fixture:inapplicable", 0.30)]["evidence_category"] == "INAPPLICABLE"
    assert rows[("fixture:non-geometry", 0.30)]["evidence_category"] == "P0_FAIL_NON_GEOMETRY"
