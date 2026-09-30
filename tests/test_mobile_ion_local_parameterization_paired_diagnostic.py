"""RED contract for an observational fixed- vs Gaussian-radius local panel.

The arms share parent/sigma/seed pair identity, not raw RNG draws or a
scientific scale calibration. Synthetic outcomes exercise reconciliation only.
"""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

from rudeus.filters.p0 import check_geometry_clash
from rudeus.generation.generator import ParentRecord


# The first four cases cover every both-generated novelty/useful cross-tab cell.
# The final three cover the remaining generation-status cells.
CASES = {
    "both-rediscovery": ("ACCEPTED", "ACCEPTED", "rediscovery", "rediscovery"),
    "fixed-rediscovery": ("ACCEPTED", "ACCEPTED", "rediscovery", "novel"),
    "gaussian-rediscovery": ("ACCEPTED", "ACCEPTED", "novel", "rediscovery"),
    "both-novel": ("ACCEPTED", "ACCEPTED", "novel", "novel"),
    "fixed-only": ("ACCEPTED", "EXHAUSTED", "rediscovery", None),
    "gaussian-only": ("EXHAUSTED", "ACCEPTED", None, "novel"),
    "neither": ("EXHAUSTED", "EXHAUSTED", None, None),
}
FIXED_VERSION = "mobile-ion-local-clearance-displace-v1"
GAUSSIAN_VERSION = "mobile-ion-local-clearance-gaussian-radius-v1"


def _parent(case, species="Na"):
    # First mobile site crosses the x boundary in accepted synthetic proposals.
    # Host y distinguishes cases without relying on panel row position.
    marker = list(CASES).index(case)
    structure = Structure(
        Lattice.cubic(20), [species, species, "O"],
        [[0.999, 0.5, 0.5], [0.45, 0.5, 0.5], [0.7, 0.80 + marker * 0.01, 0.8]],
    )
    return ParentRecord(
        parent_id=f"fixture:{case}", source_dataset="fixture", source_ref=case,
        composition=str(structure.composition.reduced_formula),
        structure=structure, structure_sha256=f"fixture-{case}",
        conductivity=None, chemical_family="synthetic", perturbable=True,
        provenance={"source": "local-parameterization-design-test"},
    )


def _minimum_image(parent, child, site):
    return float(parent.lattice.get_distance_and_image(
        parent[site].frac_coords, child[site].frac_coords,
    )[0])


def _install_synthetic_operators(monkeypatch, diagnostic):
    def case_for(structure):
        marker = round((float(structure[2].frac_coords[1]) - 0.80) / 0.01)
        return list(CASES)[marker]

    def arm(structure, rng, *, mobile_ion, sigma_A_provisional,
            max_direction_trials, operator_rng_identity, gaussian):
        case = case_for(structure)
        status, novelty = (CASES[case][1], CASES[case][3]) if gaussian else (
            CASES[case][0], CASES[case][2]
        )
        assert mobile_ion == "Na"
        assert max_direction_trials == (5 if gaussian else 4)
        assert operator_rng_identity
        sources = []
        radii = []
        for _ in ((0,) if status == "EXHAUSTED" else (0, 1)):
            if gaussian:
                source = np.asarray(rng.normal(0.0, sigma_A_provisional, size=3))
                radius = float(np.linalg.norm(source))
                sources.append(source.tolist())
            else:
                radius = float(sigma_A_provisional)
            radii.append(radius)
            rng.normal(size=3)  # Independent direction draw per target site.
        if gaussian:
            name, version = "mobile-ion-local-clearance-gaussian-radius", GAUSSIAN_VERSION
        else:
            name, version = "mobile-ion-local-clearance-displace", FIXED_VERSION
        params = {
            "operator": name, "operator_version": version,
            "proposal_status": status, "operator_rng_identity": operator_rng_identity,
            "mobile_ion": mobile_ion, "sigma_A_provisional": sigma_A_provisional,
            "max_direction_trials": max_direction_trials,
            "direction_trials_by_site": [max_direction_trials]
            if status == "EXHAUSTED" else [1, 1],
            "accepted_direction_trial_by_site": [None]
            if status == "EXHAUSTED" else [1, 1],
            "sampled_gaussian_components_A": sources if gaussian else None,
            "sampled_radii_A": radii if gaussian else None,
            "realized_displacement_magnitudes_A": [],
            "local_clearance_evidence": [],
        }
        if status == "EXHAUSTED":
            params["failure_reason"] = "NO_VALID_PROPOSAL_WITHIN_BUDGET"
            return None, params
        # Deliberately mutate the supplied operator input: the panel must pass
        # independent source copies to the two arms and retain its parent.
        original = structure.copy()
        child = structure
        child.translate_sites(0, [radii[0], 0, 0], frac_coords=False)
        child.translate_sites(1, [0, radii[1], 0], frac_coords=False)
        child.add_site_property("fixture_novelty", [novelty] * len(child))
        # Deliberately retain the old fixed-radius wrapped-Cartesian defect in
        # operator provenance. New diagnostic-derived metrics must not use it.
        params["realized_displacement_magnitudes_A"] = [
            float(np.linalg.norm(child[0].coords - original[0].coords))
            if not gaussian else _minimum_image(original, child, 0),
            _minimum_image(original, child, 1),
        ]
        return child, params

    def fixed(structure, rng, *, mobile_ion, sigma_A_provisional,
              max_direction_trials, operator_rng_identity=None):
        return arm(
            structure, rng, mobile_ion=mobile_ion,
            sigma_A_provisional=sigma_A_provisional,
            max_direction_trials=max_direction_trials,
            operator_rng_identity=operator_rng_identity, gaussian=False,
        )

    def gaussian(structure, rng, *, mobile_ion, sigma_A_provisional,
                 max_direction_trials, operator_rng_identity=None):
        return arm(
            structure, rng, mobile_ion=mobile_ion,
            sigma_A_provisional=sigma_A_provisional,
            max_direction_trials=max_direction_trials,
            operator_rng_identity=operator_rng_identity, gaussian=True,
        )

    monkeypatch.setattr(diagnostic, "op_mobile_ion_local_clearance_displace_v1", fixed)
    monkeypatch.setattr(
        diagnostic, "op_mobile_ion_local_clearance_gaussian_radius_v1",
        gaussian, raising=False,
    )


def _run(monkeypatch, cases=tuple(CASES), sigmas=(0.3,), seeds=(42,)):
    from rudeus.generation import mobile_ion_diagnostic as diagnostic

    _install_synthetic_operators(monkeypatch, diagnostic)
    calls = []

    def novelty(parent, child, *, operator_name, matcher=None):
        # The existing classifier's same-cell path is selected by "displace".
        assert operator_name == "displace"
        assert parent.composition == child.composition
        assert parent.lattice == child.lattice
        calls.append((parent.as_dict(), child.as_dict()))
        tag = child[0].properties["fixture_novelty"]
        return {
            "novelty_tag": tag,
            "novelty_matched": "parent" if tag == "rediscovery" else None,
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
        }

    def p0(formula, *, structure):
        assert formula == str(structure.composition.reduced_formula)
        geometry_ok, geometry_details = check_geometry_clash(structure)
        return SimpleNamespace(
            neutrality_ok=True, pauling_ok=True, geometry_ok=geometry_ok,
            existence_state=SimpleNamespace(value="PLAUSIBLE" if geometry_ok else "FAIL"),
            details={"geometry": geometry_details},
        )

    monkeypatch.setattr(diagnostic, "classify_candidate_supply_v2_novelty", novelty)
    monkeypatch.setattr(diagnostic, "evaluate_p0", p0)
    parents = [_parent(case) for case in cases]
    before = [parent.structure.as_dict() for parent in parents]
    panel = diagnostic.build_mobile_ion_local_parameterization_paired_diagnostic_panel(
        parents,
        mobile_ion="Na",
        sigma_values_A_provisional=list(sigmas),
        base_seeds=list(seeds),
        diagnostic_config_hash="synthetic-local-parameterization-v1",
        fixed_radius_max_direction_trials=4,
        gaussian_radius_max_direction_trials=5,
    )
    assert [parent.structure.as_dict() for parent in parents] == before
    return panel, parents, calls


def test_local_parameterization_pair_identity_rng_and_observational_boundary(monkeypatch):
    panel, parents, calls = _run(monkeypatch, cases=("both-novel", "fixed-only"),
                                sigmas=(0.3, 0.4), seeds=(42, 43))
    assert panel["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert panel["schema_version"] == "mobile-ion-local-parameterization-paired-diagnostic-v1"
    for key in (
        "scheduler_activation", "p1_eligibility", "downstream_scientific_claims",
        "operator_superiority", "automatic_promotion", "sigma_selection",
        "parent_exclusion", "chemistry_exclusion", "threshold_modification",
    ):
        assert panel["authorization"][key] is False
    assert not ({"winner", "recommended_operator", "best_operator", "score", "promotion"}
                & set(panel))
    assert panel["metadata"]["ordered_parent_ids"] == [p.parent_id for p in parents]
    assert panel["metadata"]["target_species"] == "Na"
    assert panel["metadata"]["fixed_radius_max_direction_trials"] == 4
    assert panel["metadata"]["gaussian_radius_max_direction_trials"] == 5
    assert len(panel["rows"]) == 2 * 2 * 2
    assert [(r["parent_id"], r["sigma_A_provisional"], r["base_seed"])
            for r in panel["rows"]] == [
                (parent.parent_id, sigma, seed)
                for parent in parents for sigma in (0.3, 0.4) for seed in (42, 43)
            ]
    assert len({row["pair_id"] for row in panel["rows"]}) == len(panel["rows"])
    assert len(calls) == sum(
        arm["generated"] for row in panel["rows"]
        for arm in (row["fixed_radius"], row["gaussian_radius"])
    )
    for row in panel["rows"]:
        fixed, gaussian = row["fixed_radius"], row["gaussian_radius"]
        assert row["target_species"] == "Na"
        assert row["diagnostic_config_hash"] == "synthetic-local-parameterization-v1"
        assert fixed["operator_version"] == FIXED_VERSION
        assert gaussian["operator_version"] == GAUSSIAN_VERSION
        assert fixed["operator_rng_identity"] != gaussian["operator_rng_identity"]
        assert all(arm["operator_rng_identity"] and isinstance(arm["operator_rng_seed"], int)
                   for arm in (fixed, gaussian))
        assert fixed["operator_rng_identity"] != row["pair_id"]
        assert gaussian["operator_rng_identity"] != row["pair_id"]


def test_local_parameterization_status_novelty_useful_crosstabs_reconcile(monkeypatch):
    panel, _, calls = _run(monkeypatch)
    rows, summary = panel["rows"], panel["summary"]
    assert len(rows) == summary["requested_pairs"] == 7
    assert summary["fixed_accepted"] == 5
    assert summary["fixed_exhausted"] == 2
    assert summary["gaussian_accepted"] == 5
    assert summary["gaussian_exhausted"] == 2
    assert summary["both_generated"] == 4
    assert summary["fixed_only_generated"] == 1
    assert summary["gaussian_only_generated"] == 1
    assert summary["neither_generated"] == 1
    assert summary["status_cross_tab"] == {
        "ACCEPTED_TO_ACCEPTED": 4,
        "ACCEPTED_TO_EXHAUSTED": 1,
        "EXHAUSTED_TO_ACCEPTED": 1,
        "EXHAUSTED_TO_EXHAUSTED": 1,
    }
    assert summary["novelty_cross_tab"] == {
        "NOVEL_TO_NOVEL": 1,
        "NOVEL_TO_REDISCOVERY": 1,
        "REDISCOVERY_TO_NOVEL": 1,
        "REDISCOVERY_TO_REDISCOVERY": 1,
    }
    assert summary["useful_cross_tab"] == {
        "TRUE_TO_TRUE": 1,
        "TRUE_TO_FALSE": 1,
        "FALSE_TO_TRUE": 1,
        "FALSE_TO_FALSE": 1,
    }
    assert summary["novelty_cross_tab_denominator"] == 4
    assert summary["useful_cross_tab_denominator"] == 4
    assert len(calls) == 10  # Accepted children only: 5 fixed + 5 Gaussian.
    for row in rows:
        for arm in (row["fixed_radius"], row["gaussian_radius"]):
            if arm["proposal_status"] == "EXHAUSTED":
                assert arm["generated"] is False
                for field in (
                    "child_material_id", "child_structure_dict", "novelty_tag",
                    "novelty_matcher_version", "p0_state", "p0_geometry_ok", "useful",
                ):
                    assert arm[field] is None
            else:
                assert arm["proposal_status"] == "ACCEPTED"
                assert arm["generated"] is True
                assert arm["child_material_id"] and arm["child_structure_dict"]
                assert arm["novelty_matcher_version"] == "novelty-matcher-v2-same-cell"
                assert arm["same_cell_mode"] is True
                assert arm["skip_structure_reduction"] is True
                assert arm["p0_state"] == "PLAUSIBLE"
                assert arm["p0_geometry_ok"] is True
                assert arm["useful"] is (arm["novelty_tag"] == "novel")


def test_local_parameterization_arm_denominators_are_explicit(monkeypatch):
    panel, _, _ = _run(monkeypatch)
    summary = panel["summary"]
    for arm_name, novel, useful in (
        ("fixed_radius", 2, 2), ("gaussian_radius", 3, 3),
    ):
        arm = summary["arms"][arm_name]
        assert arm["generated"] == arm["accepted"] == 5
        assert arm["exhausted"] == 2
        assert arm["geometry_fail"] == 0
        assert arm["novel"] == novel
        assert arm["rediscovery"] == 5 - novel
        assert arm["p0_plausible"] == 5
        assert arm["useful"] == useful
        assert arm["novel_per_requested"] == pytest.approx(novel / 7)
        assert arm["novel_per_generated"] == pytest.approx(novel / 5)
        assert arm["useful_per_requested"] == pytest.approx(useful / 7)
        assert arm["useful_per_generated"] == pytest.approx(useful / 5)
    assert summary["fixed_accepted"] + summary["fixed_exhausted"] == 7
    assert summary["gaussian_accepted"] + summary["gaussian_exhausted"] == 7
    assert sum(summary["status_cross_tab"].values()) == 7
    assert sum(summary["novelty_cross_tab"].values()) == 4
    assert sum(summary["useful_cross_tab"].values()) == 4


def test_local_parameterization_recomputes_minimum_image_displacement(monkeypatch):
    panel, parents, _ = _run(monkeypatch, cases=("both-rediscovery",))
    row = panel["rows"][0]
    parent = parents[0].structure
    fixed, gaussian = row["fixed_radius"], row["gaussian_radius"]
    fixed_child = Structure.from_dict(fixed["child_structure_dict"])
    gaussian_child = Structure.from_dict(gaussian["child_structure_dict"])
    assert fixed["operator_provenance"]["realized_displacement_magnitudes_A"][0] > 19
    assert fixed["derived_mobile_displacements_A"][0] == pytest.approx(
        _minimum_image(parent, fixed_child, 0)
    )
    assert fixed["derived_mobile_displacements_A"][0] == pytest.approx(0.3)
    assert gaussian["derived_mobile_displacements_A"][0] == pytest.approx(
        _minimum_image(parent, gaussian_child, 0)
    )
    assert gaussian["sampled_radii_A"][0] == pytest.approx(
        gaussian["derived_mobile_displacements_A"][0]
    )
    for arm in (fixed, gaussian):
        assert arm["direction_trials_by_site"] == [1, 1]
        assert arm["structural_change"]["mobile_displacement_rms_A"] == pytest.approx(
            np.sqrt(np.mean(np.square(arm["derived_mobile_displacements_A"])))
        )
        assert arm["structural_change"]["mobile_mobile_pair_distance_changes_abs_A"]
        assert arm["structural_change"]["nearest_host_distance_changes_A"]
    assert gaussian["sampled_gaussian_components_A"]
    assert gaussian["sampled_radii_A"]


def test_local_parameterization_displacement_summaries_are_descriptive(monkeypatch):
    panel, _, _ = _run(monkeypatch, cases=("both-rediscovery",),
                       sigmas=(0.3, 0.4), seeds=(42, 43))
    summary = panel["summary"]["displacement"]
    for arm_name in ("fixed_radius", "gaussian_radius"):
        for sigma, bucket in ((None, summary[arm_name]["global"]), *[
            (value, summary[arm_name]["by_sigma"][str(value)]) for value in (0.3, 0.4)
        ]):
            rows = panel["rows"] if sigma is None else [
                row for row in panel["rows"] if row["sigma_A_provisional"] == sigma
            ]
            magnitudes = [
                value for row in rows
                for value in row[arm_name]["derived_mobile_displacements_A"]
            ]
            assert bucket["mobile_site_count"] == len(magnitudes)
            assert bucket["min_A"] == pytest.approx(min(magnitudes))
            assert bucket["median_A"] == pytest.approx(np.median(magnitudes))
            assert bucket["mean_A"] == pytest.approx(np.mean(magnitudes))
            assert bucket["rms_A"] == pytest.approx(np.sqrt(np.mean(np.square(magnitudes))))
            assert bucket["max_A"] == pytest.approx(max(magnitudes))
            ratios = [
                value / row["sigma_A_provisional"] for row in rows
                for value in row[arm_name]["derived_mobile_displacements_A"]
            ]
            assert bucket["mean_over_sigma"] == pytest.approx(np.mean(ratios))
            assert bucket["rms_over_sigma"] == pytest.approx(
                np.sqrt(np.mean(np.square(ratios)))
            )
            if arm_name == "gaussian_radius":
                radii = [value for row in rows
                         for value in row[arm_name]["sampled_radii_A"]]
                assert bucket["sampled_radius"]["mean_A"] == pytest.approx(np.mean(radii))
                assert bucket["realized_minus_sampled_radius"]["max_abs_A"] == pytest.approx(0)
    for arm_name in ("fixed_radius", "gaussian_radius"):
        assert panel["summary"]["structural_change"][arm_name]["global"]
        assert set(panel["summary"]["structural_change"][arm_name]["by_sigma"]) == {
            "0.3", "0.4"
        }
        assert panel["summary"]["effort"][arm_name]["direction_trials_by_site"]


def test_local_parameterization_replay_and_order_preserve_pair_treatment(monkeypatch):
    first, _, _ = _run(monkeypatch, cases=("both-novel", "both-rediscovery"),
                       sigmas=(0.3, 0.4), seeds=(42, 43))
    repeated, _, _ = _run(monkeypatch, cases=("both-novel", "both-rediscovery"),
                          sigmas=(0.3, 0.4), seeds=(42, 43))
    reordered, _, _ = _run(monkeypatch, cases=("both-rediscovery", "both-novel"),
                           sigmas=(0.3, 0.4), seeds=(42, 43))
    assert json.dumps(first, sort_keys=True) == json.dumps(repeated, sort_keys=True)
    assert [r["parent_id"] for r in reordered["rows"]][:4] == [
        "fixture:both-rediscovery"
    ] * 4
    by_key = lambda panel: {
        (r["parent_id"], r["sigma_A_provisional"], r["base_seed"]): r
        for r in panel["rows"]
    }
    for key, row in by_key(first).items():
        other = by_key(reordered)[key]
        assert row["pair_id"] == other["pair_id"]
        for arm_name in ("fixed_radius", "gaussian_radius"):
            assert row[arm_name]["operator_rng_identity"] == other[arm_name][
                "operator_rng_identity"
            ]
            assert row[arm_name]["operator_rng_seed"] == other[arm_name][
                "operator_rng_seed"
            ]
            assert row[arm_name]["child_structure_dict"] == other[arm_name][
                "child_structure_dict"
            ]


def test_local_parameterization_design_supports_future_pilot_identity_grid(monkeypatch):
    # This is API shape only: no real OBELiX parents or expensive workload.
    panel, _, _ = _run(monkeypatch, cases=("both-novel",),
                       sigmas=(0.30, 0.35, 0.40), seeds=(42, 43))
    assert len(panel["rows"]) == 1 * 3 * 2
    assert panel["metadata"]["sigma_values_A_provisional"] == [0.30, 0.35, 0.40]
    assert panel["metadata"]["base_seeds"] == [42, 43]
    assert {row["base_seed"] for row in panel["rows"]} == {42, 43}
