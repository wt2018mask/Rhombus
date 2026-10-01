"""RED design contract for an observational candidate-supply-v2 tournament.

Only synthetic parents and monkeypatched CPU operators are used here.  These
tests specify reporting and validation semantics; they do not rank arms or
authorize activation.
"""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

from rudeus.filters.p0 import check_geometry_clash
from rudeus.generation.generator import ParentRecord, structure_sha256
from rudeus.generation import mobile_ion_diagnostic as diagnostic


BASELINE = "BASELINE_GAUSSIAN"
BOUNDED = "BOUNDED_GAUSSIAN_A8"
D4 = "GAUSSIAN_LOCAL_D4"
D8 = "GAUSSIAN_LOCAL_D8"
D16 = "GAUSSIAN_LOCAL_D16"
ARMS = (BASELINE, BOUNDED, D4, D8, D16)


def _parent(parent_id, case, *, species="Na", family="fixture-family"):
    structure = Structure(
        Lattice.cubic(12),
        [species, species, "O"],
        [[0.99, 0.5, 0.5], [0.45, 0.5, 0.5], [0.70, 0.75, 0.75]],
    )
    structure.add_site_property("fixture_case", [case] * len(structure))
    return ParentRecord(
        parent_id=parent_id,
        source_dataset="synthetic",
        source_ref=parent_id,
        composition=str(structure.composition.reduced_formula),
        structure=structure,
        structure_sha256=structure_sha256(structure),
        conductivity=None,
        chemical_family=family,
        perturbable=True,
        provenance={"fixture": "candidate-supply-v2-tournament"},
    )


def _install_synthetic_path(monkeypatch, *, break_prefix=False):
    calls = []

    def novelty(parent, child, *, operator_name, matcher=None):
        assert operator_name == "displace"
        tag = child[0].properties["fixture_novelty"]
        return {
            "novelty_tag": tag,
            "novelty_matched": "parent" if tag == "rediscovery" else None,
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
        }

    def p0(formula, *, structure):
        assert formula == str(structure.composition.reduced_formula)
        case = structure[0].properties["fixture_case"]
        blocked_parent = case == "blocked" and "fixture_operator" not in structure[0].properties
        if blocked_parent:
            return SimpleNamespace(
                neutrality_ok=False,
                pauling_ok=True,
                geometry_ok=True,
                existence_state=SimpleNamespace(value="FAIL"),
                details={"fixture": "parent-neutrality-block"},
            )
        geometry_ok, geometry_details = check_geometry_clash(structure)
        if "fixture_geometry_fail" in structure[0].properties:
            geometry_ok = not structure[0].properties["fixture_geometry_fail"]
        return SimpleNamespace(
            neutrality_ok=True,
            pauling_ok=True,
            geometry_ok=geometry_ok,
            existence_state=SimpleNamespace(
                value="PLAUSIBLE" if geometry_ok else "FAIL"
            ),
            details={"geometry": geometry_details},
        )

    def make_child(structure, arm, rng, sigma):
        child = structure.copy()
        # Exercise periodic minimum-image displacement at the cell boundary.
        child.translate_sites(0, [0.24, 0.0, 0.0], frac_coords=False)
        if arm.startswith("GAUSSIAN_LOCAL_"):
            child.translate_sites(1, [0.0, 0.24, 0.0], frac_coords=False)
        # Record proposal family, not arm budget: accepted prefix structures
        # and bounded attempt one must be byte-for-byte comparable.
        family = "gaussian-local" if arm.startswith("GAUSSIAN_LOCAL_") else "gaussian"
        child.add_site_property("fixture_operator", [family] * len(child))
        case = structure[0].properties["fixture_case"]
        novelty_tag = "rediscovery" if case == "novelty-split" and arm == BOUNDED else "novel"
        child.add_site_property("fixture_novelty", [novelty_tag] * len(child))
        geometry_fail = case == "baseline-geometry-fail" and arm == BASELINE
        child.add_site_property("fixture_geometry_fail", [geometry_fail] * len(child))
        return child, novelty_tag

    def baseline(structure, rng, *, mobile_ion, sigma_A_provisional,
                 operator_rng_identity=None):
        calls.append((BASELINE, structure[0].properties["fixture_case"]))
        child, _ = make_child(structure, BASELINE, rng, sigma_A_provisional)
        if structure[0].properties["fixture_case"] == "baseline-geometry-fail":
            child.translate_sites(0, structure[2].coords - child[0].coords,
                                  frac_coords=False)
        return child, {
            "operator": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "operator_rng_identity": operator_rng_identity,
        }

    def bounded(structure, rng, *, mobile_ion, sigma_A_provisional,
                max_attempts, operator_rng_identity=None):
        case = structure[0].properties["fixture_case"]
        calls.append((BOUNDED, case))
        if case == "bounded-exhaust":
            return None, {
                "operator": "mobile-ion-displace-clearance",
                "operator_version": "mobile-ion-displace-clearance-v1",
                "proposal_status": "EXHAUSTED",
                "attempts_used": max_attempts,
                "rejected_clash_attempts": max_attempts,
                "operator_rng_identity": operator_rng_identity,
            }
        child, _ = make_child(structure, BOUNDED, rng, sigma_A_provisional)
        retry = case in {"baseline-geometry-fail", "novelty-split"}
        return child, {
            "operator": "mobile-ion-displace-clearance",
            "operator_version": "mobile-ion-displace-clearance-v1",
            "proposal_status": "ACCEPTED",
            "attempts_used": 2 if retry else 1,
            "rejected_clash_attempts": 1 if retry else 0,
            "operator_rng_identity": operator_rng_identity,
        }

    def gaussian_local(structure, rng, *, mobile_ion, sigma_A_provisional,
                       max_direction_trials, operator_rng_identity=None):
        case = structure[0].properties["fixture_case"]
        arm = f"GAUSSIAN_LOCAL_D{max_direction_trials}"
        calls.append((arm, case))
        if case == "local-budget-prefix" and max_direction_trials == 4:
            return None, {
                "operator": "mobile-ion-local-clearance-gaussian-radius",
                "operator_version": "mobile-ion-local-clearance-gaussian-radius-v1",
                "proposal_status": "EXHAUSTED",
                "max_direction_trials": max_direction_trials,
                "direction_trials_by_site": [max_direction_trials],
                "accepted_direction_trial_by_site": [None],
                "operator_rng_identity": operator_rng_identity,
            }
        child, _ = make_child(structure, arm, rng, sigma_A_provisional)
        # Deliberately identical structure across D4/D8/D16 when accepted.
        if break_prefix and case == "prefix-defect" and max_direction_trials > 4:
            child.add_site_property("fixture_budget_defect", [max_direction_trials] * len(child))
        # The synthetic accepted structure moves the first mobile site 0.24 A.
        radius = 0.24
        direction_trials = 2 if case == "local-budget-prefix" else 1
        return child, {
            "operator": "mobile-ion-local-clearance-gaussian-radius",
            "operator_version": "mobile-ion-local-clearance-gaussian-radius-v1",
            "proposal_status": "ACCEPTED",
            "max_direction_trials": max_direction_trials,
            "direction_trials_by_site": [direction_trials, 1],
            "accepted_direction_trial_by_site": [direction_trials, 1],
            "sampled_radii_A": [radius, radius],
            "realized_displacement_magnitudes_A": [radius, radius],
            "operator_rng_identity": operator_rng_identity,
        }

    monkeypatch.setattr(diagnostic, "evaluate_p0", p0)
    monkeypatch.setattr(diagnostic, "classify_candidate_supply_v2_novelty", novelty)
    monkeypatch.setattr(diagnostic, "op_mobile_ion_displace_v2", baseline)
    monkeypatch.setattr(diagnostic, "op_mobile_ion_displace_clearance_v1", bounded)
    monkeypatch.setattr(
        diagnostic, "op_mobile_ion_local_clearance_gaussian_radius_v1", gaussian_local
    )
    return calls


def _build(monkeypatch, parents, *, sigmas=(0.30,), seeds=(42,), mobile_ion="Na",
           break_prefix=False):
    calls = _install_synthetic_path(monkeypatch, break_prefix=break_prefix)
    builder = getattr(
        diagnostic, "build_candidate_supply_v2_operator_tournament_panel", None
    )
    assert callable(builder), (
        "missing observational tournament API: "
        "build_candidate_supply_v2_operator_tournament_panel"
    )
    panel = builder(
        parents,
        mobile_ion=mobile_ion,
        sigma_values_A_provisional=list(sigmas),
        base_seeds=list(seeds),
        diagnostic_config_hash="synthetic-operator-tournament-v1",
        bounded_max_attempts=8,
        gaussian_local_direction_budgets=[4, 8, 16],
    )
    return panel, calls


def _arm_rows(panel, arm_id):
    return [row["arms"][arm_id] for row in panel["rows"]]


def test_tournament_keeps_blocked_and_inapplicable_pairs_explicit(monkeypatch):
    parents = [
        _parent("fixture:blocked", "blocked"),
        _parent("fixture:no-target", "all-generate", species="Li"),
        _parent("fixture:all", "all-generate"),
    ]
    panel, calls = _build(monkeypatch, parents, mobile_ion="Na")

    assert panel["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert panel["metadata"]["ordered_parent_ids"] == [p.parent_id for p in parents]
    assert panel["metadata"]["mobile_ion"] == "Na"
    assert panel["metadata"]["diagnostic_config_hash"] == "synthetic-operator-tournament-v1"
    assert panel["metadata"]["sigma_values_A_provisional"] == [0.30]
    assert panel["metadata"]["base_seeds"] == [42]
    assert panel["metadata"]["configurations"] == list(ARMS)
    assert [(r["parent_id"], r["sigma_A_provisional"], r["base_seed"])
            for r in panel["rows"]] == [(p.parent_id, 0.30, 42) for p in parents]

    for arm_id in ARMS:
        assert panel["rows"][0]["arms"][arm_id]["status"] == "BLOCKED_BY_PARENT_P0"
        assert panel["rows"][1]["arms"][arm_id]["status"] == "INAPPLICABLE"
        for row in panel["rows"][:2]:
            arm = row["arms"][arm_id]
            assert arm["child_material_id"] is None
            assert arm["novelty_tag"] is None
            assert arm["p0_state"] is None
            assert arm["useful"] is None
    assert calls == [(arm, "all-generate") for arm in ARMS]
    # Neither blocked nor inapplicable parents invoke operators.
    summary = panel["summary"]["arms"]
    for arm_id in ARMS:
        counts = summary[arm_id]
        assert (counts["requested"], counts["blocked"], counts["inapplicable"],
                counts["attempted"], counts["generated"], counts["exhausted"]) == (
                    3, 1, 1, 1, 1, 0
                )

    authorization = panel["authorization"]
    assert all(value is False for value in authorization.values())
    forbidden = {"winner", "best_operator", "recommended_budget", "recommended_sigma",
                 "scalar_tournament_score"}
    assert not (forbidden & set(panel))


def test_tournament_arm_denominators_transitions_and_failure_topology(monkeypatch):
    parents = [
        _parent("fixture:baseline-clash", "baseline-geometry-fail"),
        _parent("fixture:bounded-exhaust", "bounded-exhaust"),
        _parent("fixture:novelty-split", "novelty-split"),
        _parent("fixture:baseline-only", "all-generate"),
    ]
    panel, _ = _build(monkeypatch, parents)
    assert len(panel["rows"]) == len(parents)
    assert panel["rows"][0]["arms"][BASELINE]["geometry_ok"] is False
    assert panel["rows"][0]["arms"][BOUNDED]["status"] == "ACCEPTED"
    assert panel["rows"][1]["arms"][BOUNDED]["status"] == "EXHAUSTED"
    assert panel["rows"][1]["arms"][D16]["status"] == "ACCEPTED"
    assert panel["rows"][2]["arms"][BASELINE]["novelty_tag"] == "novel"
    assert panel["rows"][2]["arms"][BOUNDED]["novelty_tag"] == "rediscovery"
    assert panel["rows"][2]["arms"][BASELINE]["useful"] is True
    assert panel["rows"][2]["arms"][BOUNDED]["useful"] is False

    for arm_id in ARMS:
        summary = panel["summary"]["arms"][arm_id]
        assert summary["requested"] == 4
        assert summary["blocked"] == summary["inapplicable"] == 0
        assert summary["attempted"] == summary["generated"] + summary["exhausted"]
        assert summary["generated_over_attempted"] == pytest.approx(
            summary["generated"] / summary["attempted"]
        )
        assert summary["novel_over_attempted"] == pytest.approx(
            summary["novel"] / summary["attempted"]
        )
        assert summary["novel_over_generated"] == pytest.approx(
            summary["novel"] / summary["generated"]
        )
        assert summary["useful_over_attempted"] == pytest.approx(
            summary["useful"] / summary["attempted"]
        )
        assert summary["useful_over_generated"] == pytest.approx(
            summary["useful"] / summary["generated"]
        )
    assert panel["summary"]["paired_transitions"][f"{BASELINE}_TO_{BOUNDED}"]
    assert panel["summary"]["paired_transitions"][f"{BOUNDED}_TO_{D4}"]
    # Transition labels are descriptive states, never evaluative rankings.
    serialized = str(panel["summary"]["paired_transitions"]).lower()
    assert all(word not in serialized for word in ("winner", "improved", "worse"))


def test_tournament_gaussian_budget_prefix_and_response_curve(monkeypatch):
    parents = [
        _parent("fixture:local-budget-prefix", "local-budget-prefix"),
        _parent("fixture:local-already-accepted", "all-generate"),
    ]
    panel, _ = _build(monkeypatch, parents, sigmas=(0.30, 0.35), seeds=(42, 43))
    assert panel["metadata"]["gaussian_local_direction_budgets"] == [4, 8, 16]
    assert len(panel["rows"]) == 2 * 2 * 2
    for row in panel["rows"]:
        d4, d8, d16 = (row["arms"][arm] for arm in (D4, D8, D16))
        assert d4["operator_rng_identity"] == d8["operator_rng_identity"] == d16[
            "operator_rng_identity"
        ]
        assert d4["operator_rng_seed"] == d8["operator_rng_seed"] == d16[
            "operator_rng_seed"
        ]
        assert d4["operator_rng_identity"]
        if d4["status"] == "ACCEPTED":
            for field in (
                "child_structure_dict", "sampled_radii_A",
                "accepted_direction_trial_indices", "realized_radii_A",
                "novelty_tag", "p0_state", "useful",
            ):
                assert d4[field] == d8[field] == d16[field]
        if d8["status"] == "ACCEPTED":
            for field in (
                "child_structure_dict", "sampled_radii_A",
                "accepted_direction_trial_indices", "realized_radii_A",
                "novelty_tag", "p0_state", "useful",
            ):
                assert d8[field] == d16[field]
    assert all(
        panel["summary"]["prefix_audit"][transition]["mismatches"] == 0
        and panel["summary"]["prefix_audit"][transition]["accepted_to_exhausted"] == 0
        for transition in ("D4_TO_D8", "D8_TO_D16")
    )
    curve = panel["summary"]["gaussian_local_budget_response"]
    assert curve["D4_TO_D8"]["newly_accepted"] == 2 * 2
    assert curve["D8_TO_D16"]["newly_accepted"] == 0
    assert "optimum" not in str(curve).lower()


def test_tournament_diversity_periodic_metrics_and_deterministic_replay(monkeypatch):
    parents = [
        _parent("fixture:parent-a", "all-generate", family="oxide"),
        _parent("fixture:parent-b", "novelty-split", family="sulfide"),
    ]
    first, _ = _build(monkeypatch, parents, sigmas=(0.30,), seeds=(42, 43))
    second, _ = _build(monkeypatch, parents, sigmas=(0.30,), seeds=(42, 43))
    assert first == second
    assert first["rows"] == second["rows"]
    assert first["metadata"]["ordered_parent_ids"] == [p.parent_id for p in parents]
    for arm_id in ARMS:
        diversity = first["summary"]["diversity"][arm_id]
        assert "useful_parent_coverage" in diversity
        assert "useful_observations_by_parent" in diversity
        assert "maximum_parent_share" in diversity
        assert "parents_for_50_percent_useful" in diversity
        assert "parents_for_80_percent_useful" in diversity
        assert "parent_rediscovery_count" in diversity
        assert "within_arm_sibling_duplicate_pairs" in diversity
        assert "family_coverage" in diversity
        concentration = first["summary"]["concentration"][arm_id]
        for metric in ("novel", "useful", "exhausted", "geometry_fail"):
            assert metric in concentration
            assert "maximum_parent_share" in concentration[metric]
            assert "parents_for_50_percent" in concentration[metric]
            assert "parents_for_80_percent" in concentration[metric]
        displacement = first["summary"]["minimum_image_displacement"][arm_id]
        for metric in ("global", "by_sigma", "by_parent", "by_family"):
            assert metric in displacement
        for value in [displacement["global"], *displacement["by_sigma"].values()]:
            for key in ("mobile_site_count", "min_A", "median_A", "mean_A", "rms_A",
                        "max_A", "mean_over_sigma", "rms_over_sigma"):
                assert key in value
        structural = first["summary"]["structural_change"][arm_id]
        assert "mobile_displacement_rms_A" in structural
        assert "mobile_mobile_pair_distance_changes_A" in structural
        assert "nearest_host_distance_changes_A" in structural
        assert "combined_score" not in structural
    assert first["metadata"]["novelty_matcher_version"] == "novelty-matcher-v2-same-cell"
    # The first mobile site crosses the periodic boundary; distance is the short image.
    generated = first["rows"][0]["arms"][BASELINE]
    assert generated["minimum_image_mobile_displacements_A"][0] == pytest.approx(0.24)


def test_tournament_fails_closed_on_prefix_integrity_violation(monkeypatch):
    parents = [_parent("fixture:prefix-defect", "prefix-defect")]
    builder = getattr(
        diagnostic, "build_candidate_supply_v2_operator_tournament_panel", None
    )
    assert callable(builder), "missing candidate-supply-v2 tournament API"
    _install_synthetic_path(monkeypatch, break_prefix=True)
    with pytest.raises((ValueError, RuntimeError), match="(?i)source.*hash|identity"):
        builder(
            [replace(parents[0], structure_sha256="wrong-source-hash")],
            mobile_ion="Na", sigma_values_A_provisional=[0.30], base_seeds=[42],
            diagnostic_config_hash="synthetic-operator-tournament-v1",
            bounded_max_attempts=8, gaussian_local_direction_budgets=[4, 8, 16],
        )
    with pytest.raises((ValueError, RuntimeError), match="(?i)prefix|identity|mismatch"):
        builder(
            parents,
            mobile_ion="Na",
            sigma_values_A_provisional=[0.30],
            base_seeds=[42],
            diagnostic_config_hash="synthetic-operator-tournament-v1",
            bounded_max_attempts=8,
            gaussian_local_direction_budgets=[4, 8, 16],
        )
