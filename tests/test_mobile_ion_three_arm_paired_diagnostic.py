"""RED contract for an observational three-arm mobile-ion comparison.

The three proposal families remain distinct. These tests define paired
identity, lossless outcomes, denominators, and reconciliation only; they do
not define an operator winner or authorize activation.
"""

from types import SimpleNamespace

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

from rudeus.filters.p0 import check_geometry_clash
from rudeus.generation.generator import ParentRecord


CASES = {
    "all-clean": {"bounded": "ACCEPTED", "local": "ACCEPTED", "baseline_clear": True},
    "retry-local": {"bounded": "RETRY", "local": "ACCEPTED", "baseline_clear": False},
    "bounded-exhaust-local": {"bounded": "EXHAUSTED", "local": "ACCEPTED", "baseline_clear": False},
    "both-exhaust": {"bounded": "EXHAUSTED", "local": "EXHAUSTED", "baseline_clear": False},
    "local-exhaust": {"bounded": "ACCEPTED", "local": "EXHAUSTED", "baseline_clear": True},
}


def _parent(case_name, mobile_ion="Na"):
    # The distinct x coordinate provides a stable synthetic lookup key.
    x = 0.1 + 0.1 * list(CASES).index(case_name)
    structure = Structure(
        Lattice.cubic(30.0),
        [mobile_ion, "O"],
        [[x, 0.2, 0.2], [0.7, 0.7, 0.7]],
    )
    return ParentRecord(
        parent_id=f"fixture:{case_name}",
        source_dataset="fixture",
        source_ref=case_name,
        composition=str(structure.composition.reduced_formula),
        structure=structure,
        structure_sha256=f"fixture-{case_name}",
        conductivity=None,
        chemical_family=f"family-{case_name}",
        perturbable=True,
        provenance={"source": "three-arm-paired-design-test"},
    )


def _diagnostic_module():
    from rudeus.generation import mobile_ion_diagnostic

    return mobile_ion_diagnostic


def _install_synthetic_arms(monkeypatch, diagnostic, mobile_ion):
    parent_case_by_x = {
        round(parent.structure[0].coords[0] / 30.0, 6): case
        for case in CASES
        for parent in [_parent(case, mobile_ion)]
    }

    def case_for(structure):
        return parent_case_by_x[round(float(structure[0].coords[0] / 30.0), 6)]

    def make_proposal(structure, rng, sigma, clash):
        # Consume the same single proposal draw in baseline and bounded arms.
        draw = np.asarray(rng.normal(0.0, sigma, size=3), dtype=float)
        child = structure.copy()
        if clash:
            shift = child[1].coords - child[0].coords
        else:
            shift = draw
        child.translate_sites(0, shift, frac_coords=False)
        return child

    def baseline(structure, rng, *, mobile_ion, sigma_A_provisional,
                 operator_rng_identity=None):
        case = CASES[case_for(structure)]
        child = make_proposal(
            structure, rng, sigma_A_provisional, clash=not case["baseline_clear"]
        )
        return child, {
            "operator": "mobile-ion-displace",
            "operator_version": "mobile-ion-displace-v2",
            "operator_rng_identity": operator_rng_identity,
        }

    def bounded(structure, rng, *, mobile_ion, sigma_A_provisional,
                max_attempts, operator_rng_identity=None):
        case = CASES[case_for(structure)]
        outcome = case["bounded"]
        for attempt in range(1, max_attempts + 1):
            proposal = make_proposal(
                structure,
                rng,
                sigma_A_provisional,
                clash=(outcome == "EXHAUSTED" or (outcome == "RETRY" and attempt == 1)),
            )
            geometry_ok, _ = check_geometry_clash(proposal)
            if geometry_ok and outcome != "EXHAUSTED":
                return proposal, {
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

    def local(structure, rng, *, mobile_ion, sigma_A_provisional,
              max_direction_trials, operator_rng_identity=None):
        case = CASES[case_for(structure)]
        if case["local"] == "EXHAUSTED":
            for _ in range(max_direction_trials):
                rng.normal(size=3)
            return None, {
                "operator": "mobile-ion-local-clearance-displace",
                "operator_version": "mobile-ion-local-clearance-displace-v1",
                "proposal_status": "EXHAUSTED",
                "direction_trials_used": max_direction_trials,
                "direction_trials_by_site": [max_direction_trials],
                "realized_displacement_magnitudes_A": [],
                "operator_rng_identity": operator_rng_identity,
            }
        direction = np.asarray(rng.normal(size=3), dtype=float)
        direction /= np.linalg.norm(direction)
        child = structure.copy()
        child.translate_sites(
            0, direction * sigma_A_provisional, frac_coords=False
        )
        return child, {
            "operator": "mobile-ion-local-clearance-displace",
            "operator_version": "mobile-ion-local-clearance-displace-v1",
            "proposal_status": "ACCEPTED",
            "direction_trials_used": 1,
            "direction_trials_by_site": [1],
            "realized_displacement_magnitudes_A": [float(sigma_A_provisional)],
            "operator_rng_identity": operator_rng_identity,
        }

    monkeypatch.setattr(diagnostic, "op_mobile_ion_displace_v2", baseline, raising=False)
    monkeypatch.setattr(
        diagnostic, "op_mobile_ion_displace_clearance_v1", bounded, raising=False
    )
    monkeypatch.setattr(
        diagnostic, "op_mobile_ion_local_clearance_displace_v1", local, raising=False
    )


def _plausible_p0(_formula, *, structure):
    geometry_ok, details = check_geometry_clash(structure)
    return SimpleNamespace(
        neutrality_ok=True,
        pauling_ok=True,
        geometry_ok=geometry_ok,
        existence_state=SimpleNamespace(
            value="PLAUSIBLE" if geometry_ok is True else "FAIL"
        ),
        details={"geometry": details},
    )


def _run_panel(monkeypatch, parents, *, sigmas=(0.3,), seeds=(42,)):
    diagnostic = _diagnostic_module()
    _install_synthetic_arms(monkeypatch, diagnostic, "Na")
    monkeypatch.setattr(diagnostic, "evaluate_p0", _plausible_p0)
    monkeypatch.setattr(
        diagnostic,
        "classify_candidate_supply_v2_novelty",
        lambda *_args, **_kwargs: {
            "novelty_tag": "novel",
            "novelty_matched": None,
            "novelty_matcher_version": "novelty-matcher-v2-same-cell",
        },
    )
    return diagnostic.build_mobile_ion_three_arm_paired_diagnostic_panel(
        parents,
        mobile_ion="Na",
        sigma_values_A_provisional=list(sigmas),
        base_seeds=list(seeds),
        diagnostic_config_hash="three-arm-config-v1",
        clearance_max_attempts=3,
        local_clearance_max_direction_trials=5,
    )


def test_three_arm_panel_reconciles_outcomes_transitions_and_is_observational(monkeypatch):
    parents = [_parent(case) for case in CASES]
    original_parents = [parent.structure.as_dict() for parent in parents]
    panel = _run_panel(monkeypatch, parents)

    assert panel["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
    assert panel["authorization"] == {
        "scheduler_activation": False,
        "p1_eligibility": False,
        "downstream_scientific_claims": False,
        "operator_superiority": False,
        "automatic_promotion": False,
        "parent_exclusion": False,
        "chemistry_exclusion": False,
        "threshold_modification": False,
    }
    assert [row["parent_id"] for row in panel["rows"]] == [
        parent.parent_id for parent in parents
    ]
    assert [parent.structure.as_dict() for parent in parents] == original_parents
    assert panel["metadata"]["bounded_clearance_max_attempts"] == 3
    assert panel["metadata"]["local_clearance_max_direction_trials"] == 5
    assert panel["metadata"]["target_species"] == "Na"

    for row in panel["rows"]:
        assert row["pair_id"]
        assert row["sigma_A_provisional"] == 0.3
        assert row["base_seed"] == 42
        assert row["pair_rng_identity"]
        assert isinstance(row["pair_rng_seed"], int)
        assert row["baseline"]["operator_name"] == "mobile-ion-displace"
        assert row["baseline"]["operator_version"] == "mobile-ion-displace-v2"
        assert row["bounded_clearance"]["operator_name"] == "mobile-ion-displace-clearance"
        assert row["bounded_clearance"]["operator_version"] == "mobile-ion-displace-clearance-v1"
        assert row["local_clearance"]["operator_name"] == "mobile-ion-local-clearance-displace"
        assert row["local_clearance"]["operator_version"] == "mobile-ion-local-clearance-displace-v1"
        assert row["baseline"]["operator_rng_identity"] == row["pair_rng_identity"]
        assert row["bounded_clearance"]["operator_rng_identity"] == row["pair_rng_identity"]
        assert row["local_clearance"]["operator_rng_identity"] != row["pair_rng_identity"]
        assert row["local_clearance"]["operator_rng_identity"]

    by_parent = {row["parent_id"].split(":", 1)[1]: row for row in panel["rows"]}
    assert by_parent["all-clean"]["bounded_clearance"]["attempts_used"] == 1
    assert by_parent["all-clean"]["baseline"]["child_structure_dict"] == by_parent[
        "all-clean"
    ]["bounded_clearance"]["child_structure_dict"]
    assert by_parent["retry-local"]["bounded_clearance"]["attempts_used"] == 2
    assert by_parent["retry-local"]["bounded_clearance"]["proposal_status"] == "ACCEPTED"
    assert by_parent["bounded-exhaust-local"]["bounded_clearance"]["proposal_status"] == "EXHAUSTED"
    assert by_parent["both-exhaust"]["local_clearance"]["proposal_status"] == "EXHAUSTED"
    assert by_parent["local-exhaust"]["bounded_clearance"]["proposal_status"] == "ACCEPTED"
    assert by_parent["local-exhaust"]["local_clearance"]["proposal_status"] == "EXHAUSTED"

    for row in panel["rows"]:
        for arm_name in ("bounded_clearance", "local_clearance"):
            arm = row[arm_name]
            if arm["proposal_status"] == "EXHAUSTED":
                assert arm["generated"] is False
                assert arm["child_material_id"] is None
                assert arm["novelty_tag"] is None
                assert arm["p0_state"] is None
                assert arm["p0_geometry_ok"] is None
                assert arm["useful"] is None
        local = row["local_clearance"]
        if local["generated"]:
            assert local["realized_displacement_magnitudes_A"]
            assert all(value > 0.0 for value in local["realized_displacement_magnitudes_A"])
            assert local["p0_geometry_ok"] is True

    summary = panel["summary"]
    assert summary["requested_pairs"] == 5
    assert summary["baseline_generated"] == 5
    assert summary["bounded_accepted"] + summary["bounded_exhausted"] == 5
    assert summary["local_accepted"] + summary["local_exhausted"] == 5
    assert summary["baseline_bounded_generated_both"] == summary["bounded_accepted"]
    assert summary["baseline_local_generated_both"] == summary["local_accepted"]
    # Only all-clean and retry-local generate in all three arms; the other
    # fixtures each exhaust at least one non-baseline arm.
    assert summary["all_three_generated"] == 2
    assert sum(summary["baseline_to_bounded"]["geometry_transition_counts"].values()) == 5
    assert sum(summary["baseline_to_bounded"]["useful_transition_counts"].values()) == 5
    assert sum(summary["baseline_to_local"]["geometry_transition_counts"].values()) == 5
    assert sum(summary["baseline_to_local"]["useful_transition_counts"].values()) == 5
    assert sum(summary["bounded_local_status_cross_tab"].values()) == 5
    assert summary["bounded_local_status_cross_tab"] == {
        "ACCEPTED/ACCEPTED": 2,
        "ACCEPTED/EXHAUSTED": 1,
        "EXHAUSTED/ACCEPTED": 1,
        "EXHAUSTED/EXHAUSTED": 1,
    }
    assert summary["baseline_bounded_attempt1_exact_match_count"] == summary[
        "bounded_attempt1_accept_count"
    ]
    assert summary["bounded_attempt1_accept_count"] == 2
    assert not {
        "winner", "recommended_operator", "promotion_decision", "scalar_score"
    }.intersection(panel)


def test_three_arm_panel_has_deterministic_pair_streams_and_configurable_cartesian_product(
    monkeypatch,
):
    parents = [_parent("all-clean")]
    first = _run_panel(
        monkeypatch, parents, sigmas=(0.30, 0.35, 0.40), seeds=(42, 43)
    )
    second = _run_panel(
        monkeypatch, parents, sigmas=(0.30, 0.35, 0.40), seeds=(42, 43)
    )

    assert first == second
    assert len(first["rows"]) == 1 * 3 * 2
    assert [
        (row["parent_id"], row["sigma_A_provisional"], row["base_seed"])
        for row in first["rows"]
    ] == [
        (parents[0].parent_id, sigma, seed)
        for sigma in (0.30, 0.35, 0.40)
        for seed in (42, 43)
    ]
    for row in first["rows"]:
        assert row["baseline"]["operator_rng_seed"] == row["bounded_clearance"]["operator_rng_seed"]
        assert row["baseline"]["operator_rng_identity"] == row["bounded_clearance"]["operator_rng_identity"]
        assert row["local_clearance"]["operator_rng_seed"] != row["pair_rng_seed"]
        assert row["local_clearance"]["operator_rng_identity"] != row["pair_rng_identity"]
    assert first["metadata"]["ordered_parent_ids"] == [parents[0].parent_id]
    assert first["artifact_type"] == "OBSERVATIONAL_DIAGNOSTIC"
