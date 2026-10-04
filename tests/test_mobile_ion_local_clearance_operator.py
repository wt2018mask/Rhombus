"""RED design contract for an experimental local-clearance proposal family.

These tests specify mechanics only.  The provisional default search budget is
not calibrated, and passing tests would not authorize scheduler activation or
downstream scientific claims.
"""

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

from rudeus.filters.p0 import check_geometry_clash
from rudeus.generation.generator import op_mobile_ion_displace_v2


PROVISIONAL_DEFAULT_MAX_DIRECTION_TRIALS = 16


def _open_structure(mobile_ion):
    return Structure(
        Lattice.cubic(20.0),
        [mobile_ion, mobile_ion, "O"],
        [[0.20, 0.20, 0.20], [0.70, 0.70, 0.70], [0.20, 0.70, 0.70]],
    )


def _run_local_clearance(
    structure,
    *,
    mobile_ion,
    seed,
    sigma=0.4,
    max_direction_trials=None,
    operator_rng_identity="fixture-rng-v1",
):
    from rudeus.generation.generator import (
        op_mobile_ion_local_clearance_displace_v1,
    )

    kwargs = {
        "mobile_ion": mobile_ion,
        "sigma_A_provisional": sigma,
        "operator_rng_identity": operator_rng_identity,
    }
    if max_direction_trials is not None:
        kwargs["max_direction_trials"] = max_direction_trials
    return op_mobile_ion_local_clearance_displace_v1(
        structure.copy(), np.random.default_rng(seed), **kwargs
    )


@pytest.mark.parametrize("mobile_ion", ["Li", "Na", "Mg"])
def test_local_clearance_operator_is_species_neutral_and_preserves_invariants(
    mobile_ion,
):
    parent = _open_structure(mobile_ion)
    assert check_geometry_clash(parent)[0] is True

    child, metadata = _run_local_clearance(
        parent, mobile_ion=mobile_ion, seed=2026, sigma=0.4
    )

    assert metadata["proposal_status"] == "ACCEPTED"
    assert child is not None
    assert check_geometry_clash(child)[0] is True
    assert child.lattice == parent.lattice
    assert child.composition == parent.composition

    target_indices = [
        i for i, site in enumerate(parent) if mobile_ion in site.species
    ]
    host_indices = [i for i in range(len(parent)) if i not in target_indices]
    assert [child[i].species for i in host_indices] == [
        parent[i].species for i in host_indices
    ]
    assert np.array_equal(child.cart_coords[host_indices], parent.cart_coords[host_indices])
    assert metadata["mobile_site_order"] == target_indices
    assert metadata["target_site_count"] == len(target_indices)
    assert metadata["displaced_site_count"] == len(target_indices)
    assert metadata["operator"] == "mobile-ion-local-clearance-displace"
    assert metadata["operator_version"] == "mobile-ion-local-clearance-displace-v1"
    assert metadata["mobile_ion"] == mobile_ion
    assert metadata["sigma_A_provisional"] == 0.4
    assert metadata["operator_rng_identity"] == "fixture-rng-v1"

    # Record actual movement so a later experiment can detect scale collapse;
    # this design test deliberately defines no minimum-distance threshold.
    realized = metadata["realized_displacement_magnitudes_A"]
    measured = [
        float(np.linalg.norm(child[i].coords - parent[i].coords))
        for i in target_indices
    ]
    assert len(realized) == len(target_indices)
    assert np.allclose(realized, measured, rtol=0.0, atol=1e-12)
    assert metadata["realized_displacement_summary_A"]["count"] == len(target_indices)
    assert any(distance > 0.0 for distance in realized)

    # This compact per-site evidence is deterministic and based on the same
    # local distance/minimum-clearance semantics used by P0; it is not a score.
    local_evidence = metadata["local_clearance_evidence"]
    assert [item["mobile_site_index"] for item in local_evidence] == target_indices
    assert all(
        {"limiting_neighbor_index", "distance_A", "min_allowed_A", "margin_A"}
        <= set(item)
        for item in local_evidence
    )


def test_local_clearance_operator_uses_bounded_provisional_default_budget():
    parent = _open_structure("Li")
    _, metadata = _run_local_clearance(parent, mobile_ion="Li", seed=91)

    assert metadata["max_direction_trials"] == PROVISIONAL_DEFAULT_MAX_DIRECTION_TRIALS
    assert 1 <= metadata["direction_trials_used"] <= metadata["max_direction_trials"]
    assert metadata["proposal_status"] == "ACCEPTED"


def test_local_clearance_operator_is_deterministic_and_uses_source_site_order():
    parent = _open_structure("Na")
    first, first_metadata = _run_local_clearance(
        parent,
        mobile_ion="Na",
        seed=177,
        sigma=0.35,
        max_direction_trials=24,
        operator_rng_identity="parent-42-local-v1",
    )
    repeated, repeated_metadata = _run_local_clearance(
        parent,
        mobile_ion="Na",
        seed=177,
        sigma=0.35,
        max_direction_trials=24,
        operator_rng_identity="parent-42-local-v1",
    )

    assert first_metadata["proposal_status"] == repeated_metadata["proposal_status"] == "ACCEPTED"
    assert first.as_dict() == repeated.as_dict()
    assert first_metadata == repeated_metadata
    assert first_metadata["mobile_site_order"] == [0, 1]
    assert first_metadata["operator_rng_identity"] == "parent-42-local-v1"
    assert "winner" not in first_metadata
    assert "promotion_decision" not in first_metadata


def test_local_clearance_steers_away_from_a_host_collision_and_checks_whole_child(
    monkeypatch,
):
    from rudeus.generation import generator

    parent = Structure(
        Lattice.cubic(12.0),
        ["Li", "O"],
        [[0.50, 0.50, 0.50], [0.62, 0.50, 0.50]],
    )
    assert check_geometry_clash(parent)[0] is True

    # The same seed/scale in the existing isotropic proposal points into the
    # host and clashes.  A different available direction exists for this site.
    naive, _ = op_mobile_ion_displace_v2(
        parent.copy(),
        np.random.default_rng(17),
        mobile_ion="Li",
        sigma_A_provisional=0.8,
    )
    assert check_geometry_clash(naive)[0] is False

    observed_checks = []
    existing_check = generator.check_geometry_clash

    def track_existing_p0_check(structure, *args, **kwargs):
        result = existing_check(structure, *args, **kwargs)
        observed_checks.append((structure.as_dict(), result[0]))
        return result

    monkeypatch.setattr(generator, "check_geometry_clash", track_existing_p0_check)
    child, metadata = _run_local_clearance(
        parent,
        mobile_ion="Li",
        seed=17,
        sigma=0.8,
        max_direction_trials=32,
    )

    assert metadata["proposal_status"] == "ACCEPTED"
    assert child is not None
    assert check_geometry_clash(child)[0] is True
    assert any(
        checked_structure == child.as_dict() and verdict is True
        for checked_structure, verdict in observed_checks
    )
    assert not np.array_equal(child.cart_coords[0], parent.cart_coords[0])
    assert np.array_equal(child.cart_coords[1], parent.cart_coords[1])


def test_local_clearance_sequential_source_order_handles_mobile_mobile_clashes():
    parent = Structure(
        Lattice.cubic(12.0),
        ["Li", "Li", "O"],
        [[0.42, 0.50, 0.50], [0.58, 0.50, 0.50], [0.50, 0.75, 0.50]],
    )
    assert check_geometry_clash(parent)[0] is True

    naive, _ = op_mobile_ion_displace_v2(
        parent.copy(),
        np.random.default_rng(1),
        mobile_ion="Li",
        sigma_A_provisional=0.8,
    )
    naive_ok, naive_details = check_geometry_clash(naive)
    assert naive_ok is False
    assert (naive_details["atom_i"], naive_details["atom_j"]) == ("Li", "Li")

    child, metadata = _run_local_clearance(
        parent,
        mobile_ion="Li",
        seed=1,
        sigma=0.8,
        max_direction_trials=64,
    )

    assert metadata["proposal_status"] == "ACCEPTED"
    assert check_geometry_clash(child)[0] is True
    assert metadata["mobile_site_order"] == [0, 1]
    assert metadata["target_site_count"] == 2
    assert metadata["displaced_site_count"] == 2
    assert all(
        not np.array_equal(child.cart_coords[i], parent.cart_coords[i])
        for i in (0, 1)
    )
    # Contract choice: source-order sequential placement.  Each accepted move
    # must be part of the local geometry seen when the next mobile site is set.
    assert metadata["placement_mode"] == "SEQUENTIAL_SOURCE_ORDER"


def test_local_clearance_exhaustion_returns_no_child_or_material_verdict():
    # Build a six-neighbor cage at the clearance returned by the existing P0
    # checker.  No new radius table or chemistry-specific cutoff is introduced.
    lattice = Lattice.cubic(20.0)
    center = np.array([10.0, 10.0, 10.0])
    probe = Structure(
        lattice,
        ["Li", "O"],
        [center, center + [1.0, 0.0, 0.0]],
        coords_are_cartesian=True,
    )
    _, clash = check_geometry_clash(probe)
    radius = clash["min_allowed"]
    offsets = [
        [radius, 0.0, 0.0], [-radius, 0.0, 0.0],
        [0.0, radius, 0.0], [0.0, -radius, 0.0],
        [0.0, 0.0, radius], [0.0, 0.0, -radius],
    ]
    cage = Structure(
        lattice,
        ["Li"] + ["O"] * 6,
        [center] + [center + offset for offset in offsets],
        coords_are_cartesian=True,
    )
    assert check_geometry_clash(cage)[0] is True

    child, metadata = _run_local_clearance(
        cage,
        mobile_ion="Li",
        seed=404,
        sigma=0.4,
        max_direction_trials=16,
    )

    assert child is None
    assert metadata["proposal_status"] == "EXHAUSTED"
    assert metadata["failure_reason"] == "NO_VALID_PROPOSAL_WITHIN_BUDGET"
    assert metadata["direction_trials_used"] == 16
    assert metadata["displaced_site_count"] == 0
    assert metadata["realized_displacement_magnitudes_A"] == []
    assert "existence_state" not in metadata
    assert "p0_state" not in metadata
    assert "novelty_tag" not in metadata
