"""Design contract for a raw-row-derived, observational parent atlas.

The synthetic Mg rows exercise analysis mechanics only; they do not establish
downstream calibration for Mg or any material family.
"""

from __future__ import annotations

import copy
import json

import pytest


SIGMAS = [0.2, 0.4]
SEEDS = [11, 12, 13]
PARENTS = [
    ("fixture:block", "alpha", 4, 1),
    ("fixture:none", "beta", 4, 0),
    ("fixture:never", "alpha", 6, 2),
    ("fixture:persistent", "beta", 8, 2),
    ("fixture:intermittent", "gamma", 8, 4),
    ("fixture:always-geometry-fail", "alpha", 10, 2),
    ("fixture:gain", "beta", 12, 3),
    ("fixture:fragile", "gamma", 12, 6),
]
SOURCE_SHA256 = "a" * 64


def _synthetic_panel():
    """Two ordered sigmas, three seeds, and one row per parent per run."""
    rows = []
    for sigma in SIGMAS:
        for seed in SEEDS:
            for parent_id, family, site_count, target_count in PARENTS:
                row = {
                    "parent_id": parent_id,
                    "parent_chemical_family": family,
                    "site_count": site_count,
                    "target_site_count": target_count,
                    "target_species": "Mg",
                    "sigma_A_provisional": sigma,
                    "base_seed": seed,
                    "diagnostic_state": "GENERATED",
                    "novelty_tag": "rediscovery",
                    "p0_state": "PLAUSIBLE",
                    "p0_geometry_ok": True,
                }
                if parent_id == "fixture:block":
                    row.update(diagnostic_state="BLOCKED_BY_PARENT_P0",
                               novelty_tag=None, p0_state=None,
                               p0_geometry_ok=None)
                elif parent_id == "fixture:none":
                    row.update(diagnostic_state="INAPPLICABLE",
                               novelty_tag=None, p0_state=None,
                               p0_geometry_ok=None)
                elif parent_id == "fixture:persistent":
                    row["novelty_tag"] = "novel"
                elif parent_id == "fixture:intermittent":
                    row["novelty_tag"] = "novel" if seed == 11 else "rediscovery"
                elif parent_id == "fixture:always-geometry-fail":
                    row.update(novelty_tag="novel", p0_state="FAIL",
                               p0_geometry_ok=False)
                elif parent_id == "fixture:gain":
                    row["novelty_tag"] = "novel" if sigma == 0.4 else "rediscovery"
                elif parent_id == "fixture:fragile":
                    row["novelty_tag"] = "novel"
                    if sigma == 0.4:
                        row.update(p0_state="FAIL", p0_geometry_ok=False)
                rows.append(row)

    def counts(run_rows):
        generated = [row for row in run_rows if row["diagnostic_state"] == "GENERATED"]
        return {
            "requested_parents": len(run_rows),
            "blocked_parents": sum(row["diagnostic_state"] == "BLOCKED_BY_PARENT_P0" for row in run_rows),
            "inapplicable_parents": sum(row["diagnostic_state"] == "INAPPLICABLE" for row in run_rows),
            "generated_children": len(generated),
            "novel": sum(row["novelty_tag"] == "novel" for row in generated),
            "rediscovery": sum(row["novelty_tag"] == "rediscovery" for row in generated),
            "p0_plausible": sum(row["p0_state"] == "PLAUSIBLE" for row in generated),
            "geometry_failures": sum(row["p0_geometry_ok"] is False for row in generated),
            "useful_diagnostic_yield": sum(
                row["novelty_tag"] == "novel" and row["p0_state"] == "PLAUSIBLE"
                for row in generated
            ),
        }

    runs = []
    for sigma in SIGMAS:
        for seed in SEEDS:
            run_rows = [
                row for row in rows
                if row["sigma_A_provisional"] == sigma and row["base_seed"] == seed
            ]
            runs.append({"sigma_A_provisional": sigma, "base_seed": seed,
                         "summary": counts(run_rows)})

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
            "target_species": "Mg",
            "sigma_values_A_provisional": SIGMAS[:],
            "base_seeds": SEEDS[:],
            "ordered_parent_ids": [parent[0] for parent in PARENTS],
            "ordered_cohort_identity": "synthetic-ordered-cohort-v1",
            "diagnostic_config_hash": "synthetic-config-v1",
            "persistent_useful_threshold": 0.75,
        },
        "runs": runs,
        "rows": rows,
        "summary": {**counts(rows), "persistent_useful_threshold": 0.75},
    }


def _atlas(panel):
    # This standalone analysis module intentionally does not exist in RED.
    from rudeus.generation.mobile_ion_parent_atlas import (
        build_mobile_ion_parent_diagnostic_atlas,
    )

    return build_mobile_ion_parent_diagnostic_atlas(
        panel, source_artifact_sha256=SOURCE_SHA256
    )


def _parents_by_id(atlas):
    return {record["parent_id"]: record for record in atlas["parents"]}


def test_parent_atlas_is_observational_and_preserves_source_order_and_identity():
    panel = _synthetic_panel()
    original = copy.deepcopy(panel)
    atlas = _atlas(panel)

    assert panel == original
    assert atlas["schema_version"] == "mobile-ion-parent-diagnostic-atlas-v1"
    assert atlas["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert atlas["authorization"] == {
        "scheduler_activation": False,
        "p1_eligibility": False,
        "downstream_scientific_superiority_claim": False,
    }
    assert atlas["activation_authorized"] is False
    assert atlas["p1_eligibility_authorized"] is False
    assert atlas["downstream_scientific_claims_authorized"] is False
    assert atlas["source"] == {
        "diagnostic_artifact_sha256": SOURCE_SHA256,
        "schema_version": panel["schema_version"],
        **panel["metadata"],
    }
    assert [record["parent_id"] for record in atlas["parents"]] == [
        parent[0] for parent in PARENTS
    ]
    assert [item["sigma_A_provisional"] for item in atlas["parents"][0]["per_sigma"]] == SIGMAS
    assert atlas["parents"][0]["per_sigma"][0]["ordered_seeds"] == SEEDS
    assert list(atlas["summaries"]["by_chemical_family"]) == [
        "alpha", "beta", "gamma"
    ]


def test_parent_atlas_counts_frequencies_and_independent_behavioral_flags():
    records = _parents_by_id(_atlas(_synthetic_panel()))

    blocked = records["fixture:block"]
    assert (blocked["generated_observations"], blocked["blocked_observations"],
            blocked["inapplicable_observations"]) == (0, 6, 0)
    assert blocked["target_fraction"] == 0.25
    assert blocked["behavioral_flags"]["NO_GENERATED_EVIDENCE"] is True
    inapplicable = records["fixture:none"]
    assert (inapplicable["generated_observations"],
            inapplicable["inapplicable_observations"]) == (0, 6)
    assert inapplicable["target_site_count"] == 0
    assert inapplicable["target_fraction"] == 0.0

    expected = {
        "fixture:never": (0, 0, 0, 6),
        "fixture:persistent": (6, 6, 0, 6),
        "fixture:intermittent": (2, 2, 0, 6),
        "fixture:always-geometry-fail": (6, 0, 6, 0),
        "fixture:gain": (3, 3, 0, 6),
        "fixture:fragile": (6, 3, 3, 3),
    }
    for parent_id, (novel, useful, geometry_fail, plausible) in expected.items():
        record = records[parent_id]
        assert record["generated_observations"] == 6
        assert (record["novel_count"], record["useful_count"],
                record["geometry_fail_count"], record["p0_plausible_count"]) == (
                    novel, useful, geometry_fail, plausible
                )
        for name, count in (
            ("novel", novel), ("useful", useful),
            ("geometry_fail", geometry_fail), ("p0_plausible", plausible),
        ):
            assert record[f"{name}_frequency"] == pytest.approx(count / 6)

    for record in records.values():
        for name in ("novel", "useful", "geometry_fail", "p0_plausible"):
            assert 0.0 <= record[f"{name}_frequency"] <= 1.0
            if record["generated_observations"] == 0:
                assert record[f"{name}_frequency"] == 0.0

    # Independent flags: NO_GENERATED iff generated=0; NEVER_NOVEL iff
    # generated>0 and novel=0; PERSISTENT_USEFUL iff a sigma with generated
    # evidence reaches the stored 0.75 threshold; INTERMITTENT_USEFUL iff
    # useful>0 but no sigma reaches it; geometry flags use generated rows only.
    flag_names = (
        "NO_GENERATED_EVIDENCE", "NEVER_NOVEL", "PERSISTENT_USEFUL",
        "INTERMITTENT_USEFUL", "ALWAYS_GEOMETRY_FAIL", "GEOMETRY_FRAGILE",
    )
    expected_true_flags = {
        "fixture:block": {"NO_GENERATED_EVIDENCE"},
        "fixture:none": {"NO_GENERATED_EVIDENCE"},
        "fixture:never": {"NEVER_NOVEL"},
        "fixture:persistent": {"PERSISTENT_USEFUL"},
        "fixture:intermittent": {"INTERMITTENT_USEFUL"},
        "fixture:always-geometry-fail": {"ALWAYS_GEOMETRY_FAIL"},
        "fixture:gain": {"PERSISTENT_USEFUL"},
        "fixture:fragile": {"PERSISTENT_USEFUL", "GEOMETRY_FRAGILE"},
    }
    for parent_id, record in records.items():
        for flag in flag_names:
            assert record["behavioral_flags"][flag] is (flag in expected_true_flags[parent_id])


def test_parent_atlas_sigma_seed_sensitivity_and_observed_transitions():
    records = _parents_by_id(_atlas(_synthetic_panel()))
    gain = records["fixture:gain"]
    fragile = records["fixture:fragile"]
    intermittent = records["fixture:intermittent"]
    persistent = records["fixture:persistent"]
    never = records["fixture:never"]

    assert gain["useful_frequency_by_sigma"] == [0.0, 1.0]
    assert gain["geometry_fail_frequency_by_sigma"] == [0.0, 0.0]
    assert fragile["useful_frequency_by_sigma"] == [1.0, 0.0]
    assert fragile["geometry_fail_frequency_by_sigma"] == [0.0, 1.0]
    assert persistent["useful_frequency_by_sigma"] == [1.0, 1.0]
    assert never["useful_frequency_by_sigma"] == [0.0, 0.0]
    assert never["geometry_fail_frequency_by_sigma"] == [0.0, 0.0]

    for record in records.values():
        assert [item["sigma_A_provisional"] for item in record["per_sigma"]] == SIGMAS
        for item in record["per_sigma"]:
            generated = item["generated_count"]
            assert generated == (0 if record["generated_observations"] == 0 else len(SEEDS))
            assert item["ordered_seeds"] == SEEDS
            assert len(item["useful_by_seed"]) == len(SEEDS)
            assert item["useful_seed_count"] == sum(value is True for value in item["useful_by_seed"])
            assert item["useful_seed_fraction"] == pytest.approx(
                item["useful_seed_count"] / generated if generated else 0.0
            )
            for name in ("novel", "useful", "geometry_fail", "p0_plausible"):
                assert item[f"{name}_frequency"] == pytest.approx(
                    item[f"{name}_count"] / generated if generated else 0.0
                )
    assert records["fixture:block"]["per_sigma"][0]["useful_by_seed"] == [None] * 3
    assert records["fixture:none"]["per_sigma"][1]["useful_by_seed"] == [None] * 3
    assert intermittent["per_sigma"][0]["useful_by_seed"] == [True, False, False]
    assert intermittent["per_sigma"][0]["useful_seed_count"] == 1
    assert intermittent["useful_seed_variability"] is True
    assert persistent["useful_seed_variability"] is False

    assert gain["first_novel_sigma"] == 0.4
    assert gain["first_useful_sigma"] == 0.4
    assert gain["first_geometry_fail_sigma"] is None
    assert fragile["first_novel_sigma"] == 0.2
    assert fragile["first_useful_sigma"] == 0.2
    assert fragile["first_geometry_fail_sigma"] == 0.4
    assert never["first_novel_sigma"] is None
    assert records["fixture:block"]["first_useful_sigma"] is None


def test_parent_atlas_family_size_target_and_fraction_summaries_reconcile():
    atlas = _atlas(_synthetic_panel())
    summaries = atlas["summaries"]
    families = summaries["by_chemical_family"]
    assert families["alpha"] == {
        "parent_count": 3, "generated_parent_count": 2,
        "never_useful_parent_count": 3, "ever_useful_parent_count": 0,
        "persistent_useful_parent_count": 0,
        "geometry_fragile_parent_count": 0,
        "always_geometry_fail_parent_count": 1,
    }
    assert families["beta"] == {
        "parent_count": 3, "generated_parent_count": 2,
        "never_useful_parent_count": 1, "ever_useful_parent_count": 2,
        "persistent_useful_parent_count": 2,
        "geometry_fragile_parent_count": 0,
        "always_geometry_fail_parent_count": 0,
    }
    assert families["gamma"] == {
        "parent_count": 2, "generated_parent_count": 2,
        "never_useful_parent_count": 0, "ever_useful_parent_count": 2,
        "persistent_useful_parent_count": 1,
        "geometry_fragile_parent_count": 1,
        "always_geometry_fail_parent_count": 0,
    }
    assert summaries["by_site_count"]["8"]["parent_count"] == 2
    assert summaries["by_target_site_count"]["2"]["parent_count"] == 3
    # These are descriptive bins for cohort inspection, not scientific cutoffs.
    assert summaries["target_fraction_bin_edges"] == [0.0, 0.25, 0.5, 1.0]
    assert summaries["by_target_fraction_bin"]["0"]["parent_count"] == 1
    assert summaries["by_target_fraction_bin"]["(0,0.25]"]["parent_count"] == 4
    assert summaries["by_target_fraction_bin"]["(0.25,0.5]"]["parent_count"] == 3
    for axis in ("by_chemical_family", "by_site_count",
                 "by_target_site_count", "by_target_fraction_bin"):
        assert sum(item["parent_count"] for item in summaries[axis].values()) == len(PARENTS)


def test_parent_atlas_raw_row_reconciliation_and_concentration_ties():
    panel = _synthetic_panel()
    atlas = _atlas(panel)
    parents = atlas["parents"]
    generated = [row for row in panel["rows"] if row["diagnostic_state"] == "GENERATED"]
    expected_totals = {
        "generated_observations": len(generated),
        "novel_count": sum(row["novelty_tag"] == "novel" for row in generated),
        "useful_count": sum(row["novelty_tag"] == "novel" and row["p0_state"] == "PLAUSIBLE" for row in generated),
        "geometry_fail_count": sum(row["p0_geometry_ok"] is False for row in generated),
        "p0_plausible_count": sum(row["p0_state"] == "PLAUSIBLE" for row in generated),
    }
    assert expected_totals == {
        "generated_observations": 36, "novel_count": 23,
        "useful_count": 14, "geometry_fail_count": 9,
        "p0_plausible_count": 27,
    }
    for field, total in expected_totals.items():
        assert sum(parent[field] for parent in parents) == total

    useful = atlas["summaries"]["concentration"]["useful"]
    assert useful["observations_count"] == 14
    assert useful["parents_for_50_percent"] == 2
    assert useful["parents_for_80_percent"] == 3
    assert useful["max_single_parent_share"] == pytest.approx(6 / 14)
    assert useful["parent_counts_descending"][:4] == [
        {"parent_id": "fixture:persistent", "count": 6},
        {"parent_id": "fixture:fragile", "count": 3},
        {"parent_id": "fixture:gain", "count": 3},
        {"parent_id": "fixture:intermittent", "count": 2},
    ]
    geometry = atlas["summaries"]["concentration"]["geometry_fail"]
    assert geometry["observations_count"] == 9
    assert geometry["parents_for_50_percent"] == 1
    assert geometry["parents_for_80_percent"] == 2
    assert geometry["max_single_parent_share"] == pytest.approx(6 / 9)


def test_parent_atlas_zero_yield_concentration_is_explicit():
    panel = _synthetic_panel()
    for row in panel["rows"]:
        if row["diagnostic_state"] == "GENERATED":
            row["novelty_tag"] = "rediscovery"
    # The stored panel summary is intentionally stale: raw rows are authoritative.
    atlas = _atlas(panel)
    useful = atlas["summaries"]["concentration"]["useful"]
    assert useful["observations_count"] == 0
    assert useful["parents_for_50_percent"] == 0
    assert useful["parents_for_80_percent"] == 0
    assert useful["max_single_parent_share"] == 0.0


def test_parent_atlas_repeated_and_row_reordered_inputs_are_deterministic():
    panel = _synthetic_panel()
    first = _atlas(panel)
    repeated = _atlas(copy.deepcopy(panel))
    reordered_rows = copy.deepcopy(panel)
    reordered_rows["rows"].reverse()
    from_reordered_rows = _atlas(reordered_rows)

    assert first == repeated == from_reordered_rows
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        repeated, sort_keys=True, separators=(",", ":")
    )
    assert [parent["parent_id"] for parent in first["parents"]] == [
        item[0] for item in PARENTS
    ]
