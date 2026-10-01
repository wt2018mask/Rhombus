"""RED contract for a Gaussian-source baseline/bounded/local diagnostic.

All three arms use per-Cartesian-component Gaussian sigma at their radial
source. Their final proposal mechanics and their effort units remain distinct.
These fixtures establish observational accounting, not operator superiority.
"""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

from rudeus.filters.p0 import check_geometry_clash
from rudeus.generation.generator import ParentRecord


# baseline geometry clear?, bounded outcome, local outcome, baseline/bounded/local novelty
CASES = {
    "all-rediscovery": (True, "FIRST", "ACCEPTED", "rediscovery", "rediscovery", "rediscovery"),
    "bounded-novel": (True, "FIRST", "ACCEPTED", "novel", "novel", "rediscovery"),
    "local-novel": (True, "FIRST", "ACCEPTED", "rediscovery", "rediscovery", "novel"),
    "baseline-clash": (False, "RETRY", "ACCEPTED", "novel", "novel", "novel"),
    "bounded-exhaust": (False, "EXHAUSTED", "ACCEPTED", "novel", None, "novel"),
    "local-exhaust": (True, "FIRST", "EXHAUSTED", "rediscovery", "rediscovery", None),
    "both-exhaust": (False, "EXHAUSTED", "EXHAUSTED", "novel", None, None),
}


def _parent(case, species="Na"):
    marker = list(CASES).index(case)
    structure = Structure(
        Lattice.cubic(20), [species, species, "O"],
        [[0.999, 0.5, 0.5], [0.45, 0.4, 0.4], [0.7, 0.80 + marker * 0.01, 0.8]],
    )
    return ParentRecord(
        parent_id=f"fixture:{case}", source_dataset="fixture", source_ref=case,
        composition=str(structure.composition.reduced_formula),
        structure=structure, structure_sha256=f"fixture-{case}",
        conductivity=None, chemical_family="synthetic", perturbable=True,
        provenance={"source": "gaussian-three-arm-design-test"},
    )


def _minimum_image(parent, child, index):
    return float(parent.lattice.get_distance_and_image(
        parent[index].frac_coords, child[index].frac_coords,
    )[0])


def _install_fixture_arms(monkeypatch, diagnostic):
    def case_for(structure):
        marker = round((float(structure[2].frac_coords[1]) - 0.80) / 0.01)
        return list(CASES)[marker]

    def proposal(structure, rng, sigma, *, clash, novelty):
        # The same complete Gaussian proposal is drawn in baseline and bounded.
        shifts = [rng.normal(0.0, sigma, size=3) for _ in (0, 1)]
        child = structure.copy()
        for index, shift in enumerate(shifts):
            child.translate_sites(index, shift, frac_coords=False)
        if clash:
            child.translate_sites(
                0, child[2].coords - child[0].coords, frac_coords=False
            )
        child.add_site_property("fixture_novelty", [novelty] * len(child))
        return child

    def baseline(structure, rng, *, mobile_ion, sigma_A_provisional,
                 operator_rng_identity=None):
        assert mobile_ion == "Na" and operator_rng_identity
        case = CASES[case_for(structure)]
        child = proposal(
            structure, rng, sigma_A_provisional,
            clash=not case[0], novelty=case[3],
        )
        return child, {
            "operator": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "operator_rng_identity": operator_rng_identity,
        }

    def bounded(structure, rng, *, mobile_ion, sigma_A_provisional,
                max_attempts, operator_rng_identity=None):
        assert mobile_ion == "Na" and max_attempts == 3
        case = CASES[case_for(structure)]
        for attempt in range(1, max_attempts + 1):
            clash = case[1] == "EXHAUSTED" or (case[1] == "RETRY" and attempt == 1)
            child = proposal(
                structure, rng, sigma_A_provisional,
                clash=clash, novelty=case[4] if not clash else case[3],
            )
            if not clash:
                return child, {
                    "operator": "mobile-ion-displace-clearance",
                    "operator_version": "mobile-ion-displace-clearance-v1",
                    "proposal_status": "ACCEPTED",
                    "attempts_used": attempt,
                    "rejected_clash_attempts": attempt - 1,
                    "operator_rng_identity": operator_rng_identity,
                }
        return None, {
            "operator": "mobile-ion-displace-clearance",
            "operator_version": "mobile-ion-displace-clearance-v1",
            "proposal_status": "EXHAUSTED",
            "attempts_used": max_attempts,
            "rejected_clash_attempts": max_attempts,
            "operator_rng_identity": operator_rng_identity,
        }

    def gaussian_local(structure, rng, *, mobile_ion, sigma_A_provisional,
                       max_direction_trials, operator_rng_identity=None):
        assert mobile_ion == "Na" and max_direction_trials == 5
        case = CASES[case_for(structure)]
        sources, radii, shifts = [], [], []
        targets = (0,) if case[2] == "EXHAUSTED" else (0, 1)
        for _ in targets:
            source = np.asarray(rng.normal(0.0, sigma_A_provisional, size=3))
            direction = np.asarray(rng.normal(size=3))
            radius = float(np.linalg.norm(source))
            sources.append(source.tolist())
            radii.append(radius)
            shifts.append(direction * radius / np.linalg.norm(direction))
        metadata = {
            "operator": "mobile-ion-local-clearance-gaussian-radius",
            "operator_version": "mobile-ion-local-clearance-gaussian-radius-v1",
            "proposal_status": case[2],
            "operator_rng_identity": operator_rng_identity,
            "mobile_ion": mobile_ion,
            "sigma_A_provisional": sigma_A_provisional,
            "max_direction_trials": max_direction_trials,
            "sampled_gaussian_components_A": sources,
            "sampled_radii_A": radii,
            "direction_trials_by_site": [5] if case[2] == "EXHAUSTED" else [1, 1],
            "realized_displacement_magnitudes_A": [],
        }
        if case[2] == "EXHAUSTED":
            metadata["failure_reason"] = "NO_VALID_PROPOSAL_WITHIN_BUDGET"
            return None, metadata
        child = structure.copy()
        for index, shift in enumerate(shifts):
            child.translate_sites(index, shift, frac_coords=False)
        child.add_site_property("fixture_novelty", [case[5]] * len(child))
        metadata["realized_displacement_magnitudes_A"] = [
            _minimum_image(structure, child, index) for index in (0, 1)
        ]
        return child, metadata

    monkeypatch.setattr(diagnostic, "op_mobile_ion_displace_v2", baseline)
    monkeypatch.setattr(diagnostic, "op_mobile_ion_displace_clearance_v1", bounded)
    monkeypatch.setattr(
        diagnostic, "op_mobile_ion_local_clearance_gaussian_radius_v1",
        gaussian_local, raising=False,
    )


def _panel(monkeypatch, cases=tuple(CASES), sigmas=(0.30,), seeds=(42,)):
    from rudeus.generation import mobile_ion_diagnostic as diagnostic

    _install_fixture_arms(monkeypatch, diagnostic)
    calls = []

    def novelty(parent, child, *, operator_name, matcher=None):
        assert operator_name == "displace"  # Existing same-cell v2 path.
        assert parent.composition == child.composition and parent.lattice == child.lattice
        calls.append((parent.as_dict(), child.as_dict()))
        tag = child[0].properties["fixture_novelty"]
        return {
            "novelty_tag": tag,
            "novelty_matched": "parent" if tag == "rediscovery" else None,
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
        }

    def p0(formula, *, structure):
        assert formula == str(structure.composition.reduced_formula)
        geometry_ok, details = check_geometry_clash(structure)
        return SimpleNamespace(
            neutrality_ok=True, pauling_ok=True, geometry_ok=geometry_ok,
            existence_state=SimpleNamespace(value="PLAUSIBLE" if geometry_ok else "FAIL"),
            details={"geometry": details},
        )

    monkeypatch.setattr(diagnostic, "classify_candidate_supply_v2_novelty", novelty)
    monkeypatch.setattr(diagnostic, "evaluate_p0", p0)
    parents = [_parent(case) for case in cases]
    before = [parent.structure.as_dict() for parent in parents]
    panel = diagnostic.build_mobile_ion_gaussian_semantics_three_arm_diagnostic_panel(
        parents,
        mobile_ion="Na",
        sigma_values_A_provisional=list(sigmas),
        base_seeds=list(seeds),
        diagnostic_config_hash="synthetic-gaussian-three-arm-v1",
        clearance_max_attempts=3,
        gaussian_local_max_direction_trials=5,
    )
    assert [parent.structure.as_dict() for parent in parents] == before
    return panel, parents, calls


def test_gaussian_three_arm_pair_rng_sigma_contract_and_replay(monkeypatch):
    first, parents, calls = _panel(
        monkeypatch, cases=("all-rediscovery", "bounded-novel"),
        sigmas=(0.30, 0.35, 0.40), seeds=(42, 43),
    )
    repeated, _, _ = _panel(
        monkeypatch, cases=("all-rediscovery", "bounded-novel"),
        sigmas=(0.30, 0.35, 0.40), seeds=(42, 43),
    )
    assert json.dumps(first, sort_keys=True) == json.dumps(repeated, sort_keys=True)
    assert first["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert first["schema_version"] == "mobile-ion-gaussian-semantics-three-arm-diagnostic-v1"
    assert first["metadata"]["sigma_A_provisional_semantics"] == (
        "PER_CARTESIAN_COMPONENT_GAUSSIAN_STDDEV"
    )
    assert first["metadata"]["arm_mechanics"] == {
        "baseline": "GAUSSIAN_VECTOR_FINAL",
        "bounded_clearance": "REPEATED_COMPLETE_GAUSSIAN_PROPOSALS",
        "gaussian_local_clearance": "GAUSSIAN_RADIUS_LOCAL_DIRECTION_SEARCH",
    }
    assert first["metadata"]["target_species"] == "Na"
    assert first["metadata"]["clearance_max_attempts"] == 3
    assert first["metadata"]["gaussian_local_max_direction_trials"] == 5
    assert first["metadata"]["ordered_parent_ids"] == [p.parent_id for p in parents]
    assert len(first["rows"]) == 2 * 3 * 2
    assert [(r["parent_id"], r["sigma_A_provisional"], r["base_seed"])
            for r in first["rows"]] == [
                (p.parent_id, sigma, seed)
                for p in parents for sigma in (0.30, 0.35, 0.40) for seed in (42, 43)
            ]
    assert len({row["pair_id"] for row in first["rows"]}) == 12
    assert len(calls) == 36  # Three generated arms per pair.
    for row in first["rows"]:
        baseline, bounded, local = (
            row["baseline"], row["bounded_clearance"], row["gaussian_local_clearance"]
        )
        assert row["target_species"] == "Na"
        assert row["diagnostic_config_hash"] == "synthetic-gaussian-three-arm-v1"
        assert baseline["operator_version"] == "mobile-ion-displace-v2"
        assert bounded["operator_version"] == "mobile-ion-displace-clearance-v1"
        assert local["operator_version"] == "mobile-ion-local-clearance-gaussian-radius-v1"
        assert baseline["operator_rng_identity"] == bounded["operator_rng_identity"] == row[
            "pair_rng_identity"
        ]
        assert baseline["operator_rng_seed"] == bounded["operator_rng_seed"] == row[
            "pair_rng_seed"
        ]
        assert local["operator_rng_identity"] != row["pair_rng_identity"]
        assert local["operator_rng_seed"] != row["pair_rng_seed"]
        assert all(isinstance(arm["operator_rng_seed"], int)
                   for arm in (baseline, bounded, local))
        assert bounded["attempts_used"] == 1
        assert baseline["child_structure_dict"] == bounded["child_structure_dict"]


def test_gaussian_three_arm_exhaustion_first_proposal_and_denominators(monkeypatch):
    panel, _, calls = _panel(monkeypatch)
    by_case = {row["parent_id"].split(":", 1)[1]: row for row in panel["rows"]}
    summary = panel["summary"]
    assert len(calls) == 7 + 5 + 5  # Baseline always; exhausted arms not evaluated.
    assert summary["requested_pairs"] == 7
    assert summary["baseline_generated"] == 7
    assert (summary["bounded_accepted"], summary["bounded_exhausted"]) == (5, 2)
    assert (summary["gaussian_local_accepted"], summary["gaussian_local_exhausted"]) == (5, 2)
    assert summary["baseline_bounded_generated_both"] == 5
    assert summary["baseline_gaussian_local_generated_both"] == 5
    assert summary["bounded_gaussian_local_generated_both"] == 4
    assert summary["all_three_generated"] == 4
    assert summary["bounded_attempt1_accept_count"] == 4
    assert summary["baseline_bounded_attempt1_exact_match_count"] == 4
    assert by_case["baseline-clash"]["baseline"]["p0_geometry_ok"] is False
    assert by_case["baseline-clash"]["bounded_clearance"]["attempts_used"] == 2
    assert by_case["baseline-clash"]["bounded_clearance"]["rejected_clash_attempts"] == 1
    for row in panel["rows"]:
        for name in ("bounded_clearance", "gaussian_local_clearance"):
            arm = row[name]
            if arm["proposal_status"] == "EXHAUSTED":
                assert arm["generated"] is False
                for key in (
                    "child_material_id", "child_structure_dict", "novelty_tag",
                    "novelty_matcher_version", "p0_state", "p0_geometry_ok", "useful",
                ):
                    assert arm[key] is None
            else:
                assert arm["proposal_status"] == "ACCEPTED" and arm["generated"] is True
                assert arm["child_structure_dict"] and arm["child_material_id"]
                assert arm["novelty_matcher_version"] == "novelty-matcher-v2-same-cell"
                assert arm["same_cell_mode"] is True
                assert arm["skip_structure_reduction"] is True
                assert arm["p0_state"] == "PLAUSIBLE"
                assert arm["useful"] is (arm["novelty_tag"] == "novel")


def test_gaussian_three_arm_transitions_and_cross_tabs_are_descriptive(monkeypatch):
    panel, _, _ = _panel(monkeypatch)
    summary = panel["summary"]
    assert summary["baseline_to_bounded"]["geometry_transition_counts"] == {
        "PASS_TO_PASS": 4, "FAIL_TO_PASS": 1, "FAIL_TO_EXHAUSTED": 2,
    }
    assert summary["baseline_to_bounded"]["useful_transition_counts"] == {
        "FALSE_TO_FALSE": 3, "TRUE_TO_TRUE": 1,
        "FALSE_TO_TRUE": 1, "FALSE_TO_NOT_EVALUATED": 2,
    }
    assert summary["baseline_to_gaussian_local"]["geometry_transition_counts"] == {
        "PASS_TO_PASS": 3, "FAIL_TO_PASS": 2,
        "PASS_TO_EXHAUSTED": 1, "FAIL_TO_EXHAUSTED": 1,
    }
    assert summary["baseline_to_gaussian_local"]["useful_transition_counts"] == {
        "FALSE_TO_FALSE": 1, "TRUE_TO_FALSE": 1,
        "FALSE_TO_TRUE": 3, "FALSE_TO_NOT_EVALUATED": 2,
    }
    assert summary["bounded_gaussian_local_status_cross_tab"] == {
        "ACCEPTED/ACCEPTED": 4,
        "ACCEPTED/EXHAUSTED": 1,
        "EXHAUSTED/ACCEPTED": 1,
        "EXHAUSTED/EXHAUSTED": 1,
    }
    assert summary["bounded_gaussian_local_novelty_cross_tab"] == {
        "NOVEL/NOVEL": 1,
        "NOVEL/REDISCOVERY": 1,
        "REDISCOVERY/NOVEL": 1,
        "REDISCOVERY/REDISCOVERY": 1,
    }
    assert summary["bounded_gaussian_local_useful_cross_tab"] == {
        "TRUE/TRUE": 1, "TRUE/FALSE": 1,
        "FALSE/TRUE": 1, "FALSE/FALSE": 1,
    }
    assert summary["bounded_gaussian_local_cross_tab_denominator"] == 4
    assert sum(summary["bounded_gaussian_local_status_cross_tab"].values()) == 7
    assert sum(summary["bounded_gaussian_local_novelty_cross_tab"].values()) == 4
    assert sum(summary["bounded_gaussian_local_useful_cross_tab"].values()) == 4
    for target in ("baseline_to_bounded", "baseline_to_gaussian_local"):
        assert sum(summary[target]["geometry_transition_counts"].values()) == 7
        assert sum(summary[target]["useful_transition_counts"].values()) == 7
    assert not ({"winner", "recommended_operator", "best_operator", "score", "promotion"}
                & set(panel))


def test_gaussian_three_arm_arm_summaries_have_explicit_denominators(monkeypatch):
    panel, _, _ = _panel(monkeypatch)
    for name, generated, exhausted, novel, plausible, useful in (
        ("baseline", 7, 0, 4, 4, 1),
        ("bounded_clearance", 5, 2, 2, 5, 2),
        ("gaussian_local_clearance", 5, 2, 3, 5, 3),
    ):
        arm = panel["summary"]["arms"][name]
        assert arm["requested_pairs"] == 7
        assert arm["generated"] == generated
        assert arm["exhausted"] == exhausted
        assert arm["geometry_fail"] == generated - plausible
        assert arm["novel"] == novel
        assert arm["rediscovery"] == generated - novel
        assert arm["p0_plausible"] == plausible
        assert arm["useful"] == useful
        assert arm["novel_per_requested"] == pytest.approx(novel / 7)
        assert arm["useful_per_requested"] == pytest.approx(useful / 7)
        assert arm["useful_per_generated"] == pytest.approx(useful / generated)


def test_gaussian_three_arm_periodic_displacement_structure_and_radius(monkeypatch):
    panel, parents, _ = _panel(monkeypatch, cases=("all-rediscovery",),
                               sigmas=(0.30, 0.40), seeds=(42, 43))
    parent = parents[0].structure
    for row in panel["rows"]:
        for name in ("baseline", "bounded_clearance", "gaussian_local_clearance"):
            arm = row[name]
            child = Structure.from_dict(arm["child_structure_dict"])
            derived = arm["derived_mobile_displacements_A"]
            assert len(derived) == 2
            for index, magnitude in enumerate(derived):
                assert magnitude == pytest.approx(_minimum_image(parent, child, index))
            assert arm["structural_change"]["mobile_displacement_rms_A"] == pytest.approx(
                np.sqrt(np.mean(np.square(derived)))
            )
            assert arm["structural_change"]["mobile_mobile_pair_distance_changes_abs_A"]
            assert arm["structural_change"]["nearest_host_distance_changes_A"]
        local = row["gaussian_local_clearance"]
        assert len(local["sampled_gaussian_components_A"]) == 2
        assert len(local["sampled_radii_A"]) == 2
        for sampled, realized in zip(
            local["sampled_radii_A"], local["derived_mobile_displacements_A"]
        ):
            assert realized == pytest.approx(sampled, abs=1e-10)
    for name in ("baseline", "bounded_clearance", "gaussian_local_clearance"):
        for sigma, bucket in panel["summary"]["displacement"][name]["by_sigma"].items():
            subset = [r[name] for r in panel["rows"] if str(r["sigma_A_provisional"]) == sigma]
            values = [value for arm in subset for value in arm["derived_mobile_displacements_A"]]
            assert bucket["mobile_site_count"] == len(values)
            assert bucket["min_A"] == pytest.approx(min(values))
            assert bucket["median_A"] == pytest.approx(np.median(values))
            assert bucket["mean_A"] == pytest.approx(np.mean(values))
            assert bucket["rms_A"] == pytest.approx(np.sqrt(np.mean(np.square(values))))
            assert bucket["max_A"] == pytest.approx(max(values))
            assert bucket["mean_over_sigma"] == pytest.approx(np.mean(values) / float(sigma))
            assert bucket["rms_over_sigma"] == pytest.approx(
                np.sqrt(np.mean(np.square(values))) / float(sigma)
            )
    assert panel["summary"]["displacement"]["gaussian_local_clearance"]["global"][
        "realized_minus_sampled_radius"
    ]["max_abs_A"] == pytest.approx(0, abs=1e-10)


def test_gaussian_three_arm_boundary_crossing_uses_minimum_image(monkeypatch):
    from rudeus.generation import mobile_ion_diagnostic as diagnostic

    _install_fixture_arms(monkeypatch, diagnostic)

    def force_positive_boundary_move(structure, rng, *, mobile_ion,
                                     sigma_A_provisional, operator_rng_identity=None):
        # Diagnostic measurement fixture: the first Na wraps across x=1.
        child = structure.copy()
        child.translate_sites(0, [0.3, 0, 0], frac_coords=False)
        child.translate_sites(1, [0, 0.3, 0], frac_coords=False)
        child.add_site_property("fixture_novelty", ["rediscovery"] * len(child))
        return child, {"operator": "mobile-ion-displace",
                       "operator_version": "mobile-ion-displace-v2",
                       "operator_rng_identity": operator_rng_identity}

    def bounded_first(structure, rng, *, mobile_ion, sigma_A_provisional,
                      max_attempts, operator_rng_identity=None):
        child, _ = force_positive_boundary_move(
            structure, rng, mobile_ion=mobile_ion,
            sigma_A_provisional=sigma_A_provisional,
            operator_rng_identity=operator_rng_identity,
        )
        return child, {"operator": "mobile-ion-displace-clearance",
                       "operator_version": "mobile-ion-displace-clearance-v1",
                       "proposal_status": "ACCEPTED", "attempts_used": 1,
                       "rejected_clash_attempts": 0,
                       "operator_rng_identity": operator_rng_identity}

    def local_boundary(structure, rng, *, mobile_ion, sigma_A_provisional,
                       max_direction_trials, operator_rng_identity=None):
        child, _ = force_positive_boundary_move(
            structure, rng, mobile_ion=mobile_ion,
            sigma_A_provisional=sigma_A_provisional,
            operator_rng_identity=operator_rng_identity,
        )
        return child, {"operator": "mobile-ion-local-clearance-gaussian-radius",
                       "operator_version": "mobile-ion-local-clearance-gaussian-radius-v1",
                       "proposal_status": "ACCEPTED", "operator_rng_identity": operator_rng_identity,
                       "sampled_gaussian_components_A": [[0.3, 0, 0], [0, 0.3, 0]],
                       "sampled_radii_A": [0.3, 0.3],
                       "direction_trials_by_site": [1, 1],
                       "realized_displacement_magnitudes_A": [0.3, 0.3]}

    monkeypatch.setattr(diagnostic, "op_mobile_ion_displace_v2", force_positive_boundary_move)
    monkeypatch.setattr(diagnostic, "op_mobile_ion_displace_clearance_v1", bounded_first)
    monkeypatch.setattr(
        diagnostic, "op_mobile_ion_local_clearance_gaussian_radius_v1",
        local_boundary, raising=False,
    )
    monkeypatch.setattr(
        diagnostic, "classify_candidate_supply_v2_novelty",
        lambda *_args, **_kwargs: {
            "novelty_tag": "rediscovery", "novelty_matched": "parent",
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
        },
    )
    monkeypatch.setattr(
        diagnostic, "evaluate_p0",
        lambda _formula, *, structure: SimpleNamespace(
            neutrality_ok=True, pauling_ok=True, geometry_ok=True,
            existence_state=SimpleNamespace(value="PLAUSIBLE"), details={"geometry": {}},
        ),
    )
    parent = _parent("all-rediscovery")
    panel = diagnostic.build_mobile_ion_gaussian_semantics_three_arm_diagnostic_panel(
        [parent], mobile_ion="Na", sigma_values_A_provisional=[0.3], base_seeds=[42],
        diagnostic_config_hash="periodic-fixture", clearance_max_attempts=3,
        gaussian_local_max_direction_trials=5,
    )
    for name in ("baseline", "bounded_clearance", "gaussian_local_clearance"):
        arm = panel["rows"][0][name]
        child = Structure.from_dict(arm["child_structure_dict"])
        assert child[0].frac_coords[0] % 1 == pytest.approx(0.014, abs=1e-10)
        assert arm["derived_mobile_displacements_A"][0] == pytest.approx(0.3, abs=1e-10)
        assert arm["derived_mobile_displacements_A"][0] == pytest.approx(
            _minimum_image(parent.structure, child, 0), abs=1e-10
        )


def test_gaussian_three_arm_effort_units_and_authorization(monkeypatch):
    panel, _, _ = _panel(monkeypatch)
    assert panel["authorization"] == {
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
    }
    assert panel["summary"]["bounded_effort"]["attempts_used_distribution"] == {
        "1": 4, "2": 1, "3": 2,
    }
    assert panel["summary"]["bounded_effort"]["rejected_clash_attempts_distribution"] == {
        "0": 4, "1": 1, "3": 2,
    }
    local_effort = panel["summary"]["gaussian_local_effort"]
    assert local_effort["per_site_direction_trial_distribution"] == {"1": 10, "5": 2}
    assert local_effort["total_direction_trials"] == 20
    assert local_effort["row_total_direction_trials_distribution"] == {
        "2": 5, "5": 2,
    }
    assert panel["metadata"]["effort_units"] == {
        "bounded_clearance": "COMPLETE_GAUSSIAN_PROPOSAL_ATTEMPTS",
        "gaussian_local_clearance": "PER_SITE_DIRECTION_TRIALS",
    }
