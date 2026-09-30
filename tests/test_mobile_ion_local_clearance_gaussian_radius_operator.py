"""RED mechanics contract for a separate Gaussian-radius local-clearance operator.

These synthetic tests specify proposal and provenance semantics only. They do
not establish novelty, scientific calibration, or scheduler eligibility.
"""

import numpy as np
import pytest
from pymatgen.core import Lattice, Structure

from rudeus.filters.p0 import check_geometry_clash, geometry_pair_clearance
from rudeus.generation.generator import op_mobile_ion_displace_v2


def _operator():
    from rudeus.generation.generator import (
        op_mobile_ion_local_clearance_gaussian_radius_v1,
    )

    return op_mobile_ion_local_clearance_gaussian_radius_v1


def _run(parent, rng, *, mobile_ion="Li", sigma=0.3, trials=4, identity="fixture-rng"):
    return _operator()(
        parent.copy(), rng, mobile_ion=mobile_ion,
        sigma_A_provisional=sigma, max_direction_trials=trials,
        operator_rng_identity=identity,
    )


def _open_parent(mobile_ion="Li", two_mobile=False):
    species = [mobile_ion, mobile_ion, "O"] if two_mobile else [mobile_ion, "O"]
    coords = (
        [[0.20, 0.20, 0.20], [0.70, 0.70, 0.70], [0.20, 0.70, 0.70]]
        if two_mobile else [[0.20, 0.20, 0.20], [0.70, 0.70, 0.70]]
    )
    return Structure(Lattice.cubic(20.0), species, coords)


def _minimum_image_magnitude(parent, child, index):
    return float(parent.lattice.get_distance_and_image(
        parent[index].frac_coords, child[index].frac_coords,
    )[0])


class _ScriptedRng:
    """Distinguish one Gaussian radius draw per site from direction draws."""

    def __init__(self, sigma, gaussian_vectors, directions):
        self.sigma = sigma
        self.gaussian_vectors = [np.asarray(x, dtype=float) for x in gaussian_vectors]
        self.directions = [np.asarray(x, dtype=float) for x in directions]
        self.gaussian_calls = 0
        self.direction_calls = 0

    def normal(self, loc=0.0, scale=1.0, size=None):
        assert loc == 0.0 and size == 3
        if scale == self.sigma:
            vector = self.gaussian_vectors[self.gaussian_calls]
            self.gaussian_calls += 1
            return vector.copy()
        assert scale == 1.0
        vector = self.directions[self.direction_calls]
        self.direction_calls += 1
        return vector.copy()


@pytest.mark.parametrize("mobile_ion", ["Li", "Na", "Mg"])
def test_gaussian_radius_acceptance_is_species_neutral_and_preserves_structure(mobile_ion):
    parent = _open_parent(mobile_ion, two_mobile=True)
    draws = [[0.1, 0.2, 0.3], [-0.2, 0.1, 0.2]]
    rng = _ScriptedRng(0.3, draws, [[1, 0, 0], [0, 1, 0]])

    child, metadata = _run(parent, rng, mobile_ion=mobile_ion)

    assert metadata["operator"] == "mobile-ion-local-clearance-gaussian-radius"
    assert metadata["operator_version"] == "mobile-ion-local-clearance-gaussian-radius-v1"
    assert metadata["proposal_status"] == "ACCEPTED"
    assert metadata["mobile_ion"] == mobile_ion
    assert metadata["sigma_A_provisional"] == 0.3
    assert metadata["operator_rng_identity"] == "fixture-rng"
    assert metadata["mobile_site_order"] == [0, 1]
    assert metadata["placement_mode"] == "SEQUENTIAL_SOURCE_ORDER"
    assert metadata["target_site_count"] == metadata["displaced_site_count"] == 2
    assert metadata["sampled_gaussian_components_A"] == draws
    assert metadata["sampled_radii_A"] == pytest.approx(
        [np.linalg.norm(draw) for draw in draws]
    )
    assert metadata["direction_trials_by_site"] == [1, 1]
    assert metadata["accepted_direction_trial_by_site"] == [1, 1]
    assert rng.gaussian_calls == 2
    assert child is not None and check_geometry_clash(child)[0] is True
    assert len(child) == len(parent)
    assert child.lattice == parent.lattice
    assert child.composition == parent.composition
    assert [site.species for site in child] == [site.species for site in parent]
    assert np.array_equal(child[2].coords, parent[2].coords)
    for index, radius, realized in zip(
        (0, 1), metadata["sampled_radii_A"],
        metadata["realized_displacement_magnitudes_A"],
    ):
        measured = _minimum_image_magnitude(parent, child, index)
        assert measured == pytest.approx(radius, abs=1e-10)
        assert realized == pytest.approx(measured, abs=1e-10)


def test_gaussian_radius_replays_with_its_own_versioned_rng_provenance():
    parent = _open_parent("Na", two_mobile=True)
    kwargs = dict(mobile_ion="Na", sigma=0.35, trials=8, identity="parent-7-local-gaussian-v1")
    first, first_metadata = _run(parent, np.random.default_rng(177), **kwargs)
    repeated, repeated_metadata = _run(parent, np.random.default_rng(177), **kwargs)

    assert first is not None and repeated is not None
    assert first.as_dict() == repeated.as_dict()
    assert first_metadata == repeated_metadata
    assert first_metadata["operator_version"] == "mobile-ion-local-clearance-gaussian-radius-v1"
    assert first_metadata["operator_rng_identity"] == kwargs["identity"]
    assert first_metadata["sampled_gaussian_components_A"]
    assert "winner" not in first_metadata
    assert "promotion_decision" not in first_metadata


def test_gaussian_radius_matches_baseline_radial_source_not_final_direction():
    parent = _open_parent()
    sigma = 0.3
    seed = 917
    baseline, _ = op_mobile_ion_displace_v2(
        parent.copy(), np.random.default_rng(seed),
        mobile_ion="Li", sigma_A_provisional=sigma,
    )
    gaussian = np.random.default_rng(seed).normal(0.0, sigma, size=3)

    child, metadata = _run(parent, np.random.default_rng(seed), sigma=sigma)

    assert child is not None
    assert metadata["sampled_gaussian_components_A"][0] == pytest.approx(gaussian)
    assert metadata["sampled_radii_A"][0] == pytest.approx(np.linalg.norm(gaussian))
    assert metadata["sampled_radii_A"][0] == pytest.approx(
        _minimum_image_magnitude(parent, baseline, 0)
    )
    assert _minimum_image_magnitude(parent, child, 0) == pytest.approx(
        metadata["sampled_radii_A"][0], abs=1e-10
    )


def test_gaussian_radius_varies_and_replays_without_a_statistical_cutoff():
    parent = _open_parent()
    sigma = 0.3
    radii = []
    for seed in range(32):
        expected = np.random.default_rng(seed).normal(0.0, sigma, size=3)
        child, metadata = _run(
            parent, np.random.default_rng(seed), sigma=sigma, trials=1,
        )
        assert child is not None
        assert metadata["sampled_gaussian_components_A"][0] == pytest.approx(expected)
        radius = metadata["sampled_radii_A"][0]
        assert radius == pytest.approx(np.linalg.norm(expected))
        assert radius == pytest.approx(
            _minimum_image_magnitude(parent, child, 0), abs=1e-10
        )
        radii.append(radius)

    assert min(radii) < sigma < max(radii)
    assert len(set(radii)) == len(radii)


def test_gaussian_radius_retries_host_avoidance_without_resampling_radius(monkeypatch):
    from rudeus.generation import generator
    from rudeus.filters import p0

    parent = Structure(
        Lattice.cubic(12.0), ["Li", "O"],
        [[0.50, 0.50, 0.50], [0.62, 0.50, 0.50]],
    )
    toward_host = parent.copy()
    toward_host.translate_sites(0, [0.8, 0, 0], frac_coords=False)
    assert check_geometry_clash(parent)[0] is True
    assert geometry_pair_clearance(toward_host, 0, 1)[2] < 0
    rng = _ScriptedRng(0.8, [[0.8, 0, 0]], [[1, 0, 0], [-1, 0, 0]])
    checked_radii = []
    existing_clearance = generator.geometry_pair_clearance

    def track_clearance(structure, site_i, site_j, *args, **kwargs):
        moved = _minimum_image_magnitude(parent, structure, 0)
        if moved > 0:
            checked_radii.append(moved)
        return existing_clearance(structure, site_i, site_j, *args, **kwargs)

    monkeypatch.setattr(generator, "geometry_pair_clearance", track_clearance)
    monkeypatch.setattr(p0, "geometry_pair_clearance", track_clearance)

    child, metadata = _run(parent, rng, sigma=0.8, trials=3)

    assert child is not None and metadata["proposal_status"] == "ACCEPTED"
    assert check_geometry_clash(child)[0] is True
    assert rng.gaussian_calls == 1
    assert metadata["sampled_radii_A"] == pytest.approx([0.8])
    assert 1 < metadata["accepted_direction_trial_by_site"][0] <= 3
    assert metadata["direction_trials_by_site"] == metadata["accepted_direction_trial_by_site"]
    assert len(checked_radii) >= 2
    assert checked_radii == pytest.approx([0.8] * len(checked_radii), abs=1e-10)
    assert _minimum_image_magnitude(parent, child, 0) == pytest.approx(0.8)
    assert metadata["realized_displacement_magnitudes_A"] == pytest.approx([0.8])
    assert metadata["local_clearance_evidence"][0]["mobile_site_index"] == 0
    assert metadata["local_clearance_evidence"][0]["margin_A"] >= 0


def test_gaussian_radius_sequential_placement_exposes_earlier_mobile_move():
    parent = Structure(
        Lattice.cubic(20.0), ["Li", "Li", "O"],
        [[8, 10, 10], [11, 10, 10], [10, 18, 10]],
        coords_are_cartesian=True,
    )
    after_first = parent.copy()
    after_first.translate_sites(0, [0.8, 0, 0], frac_coords=False)
    second_toward_first = after_first.copy()
    second_toward_first.translate_sites(1, [-0.8, 0, 0], frac_coords=False)
    second_toward_original_first = parent.copy()
    second_toward_original_first.translate_sites(1, [-0.8, 0, 0], frac_coords=False)
    assert check_geometry_clash(parent)[0] is True
    assert check_geometry_clash(after_first)[0] is True
    assert geometry_pair_clearance(second_toward_first, 0, 1)[2] < 0
    assert geometry_pair_clearance(second_toward_original_first, 0, 1)[2] > 0
    rng = _ScriptedRng(
        0.8, [[0.8, 0, 0], [-0.8, 0, 0]],
        [[1, 0, 0], [-1, 0, 0], [1, 0, 0]],
    )

    child, metadata = _run(parent, rng, sigma=0.8, trials=3)

    assert child is not None and check_geometry_clash(child)[0] is True
    assert rng.gaussian_calls == 2
    assert metadata["mobile_site_order"] == [0, 1]
    assert metadata["accepted_direction_trial_by_site"][0] == 1
    assert metadata["accepted_direction_trial_by_site"][1] > 1
    assert metadata["sampled_radii_A"] == pytest.approx([0.8, 0.8])
    for index in (0, 1):
        assert _minimum_image_magnitude(parent, child, index) == pytest.approx(
            metadata["sampled_radii_A"][index], abs=1e-10
        )


def test_gaussian_radius_runs_existing_whole_child_geometry_check(monkeypatch):
    from rudeus.generation import generator

    parent = _open_parent()
    checked = []
    existing_check = generator.check_geometry_clash

    def track(structure, *args, **kwargs):
        verdict = existing_check(structure, *args, **kwargs)
        checked.append((structure.as_dict(), verdict[0]))
        return verdict

    monkeypatch.setattr(generator, "check_geometry_clash", track)
    child, metadata = _run(parent, np.random.default_rng(29))

    assert child is not None and metadata["proposal_status"] == "ACCEPTED"
    assert (child.as_dict(), True) in checked


def test_gaussian_radius_exhaustion_retains_radius_without_material_verdict():
    lattice = Lattice.cubic(20.0)
    center = np.array([10.0, 10.0, 10.0])
    probe = Structure(
        lattice, ["Li", "O"], [center, center + [1, 0, 0]],
        coords_are_cartesian=True,
    )
    minimum = check_geometry_clash(probe)[1]["min_allowed"]
    offsets = np.eye(3).tolist() + (-np.eye(3)).tolist()
    cage = Structure(
        lattice, ["Li"] + ["O"] * 6,
        [center] + [center + minimum * np.asarray(v) for v in offsets],
        coords_are_cartesian=True,
    )
    assert check_geometry_clash(cage)[0] is True
    rng = _ScriptedRng(0.4, [[0.4, 0, 0]], offsets)

    child, metadata = _run(cage, rng, sigma=0.4, trials=4)

    assert child is None
    assert metadata["proposal_status"] == "EXHAUSTED"
    assert metadata["failure_reason"] == "NO_VALID_PROPOSAL_WITHIN_BUDGET"
    assert rng.gaussian_calls == 1
    assert metadata["sampled_gaussian_components_A"] == [[0.4, 0, 0]]
    assert metadata["sampled_radii_A"] == pytest.approx([0.4])
    assert metadata["direction_trials_by_site"] == [4]
    assert metadata["accepted_direction_trial_by_site"] == [None]
    assert metadata["realized_displacement_magnitudes_A"] == []
    assert "existence_state" not in metadata
    assert "p0_state" not in metadata


def test_gaussian_radius_exact_zero_draw_exhausts_without_resampling():
    rng = _ScriptedRng(0.3, [[0, 0, 0]], [])

    child, metadata = _run(_open_parent(), rng, trials=3)

    assert child is None
    assert metadata["proposal_status"] == "EXHAUSTED"
    assert metadata["failure_reason"] == "ZERO_GAUSSIAN_RADIUS"
    assert metadata["sampled_gaussian_components_A"] == [[0, 0, 0]]
    assert metadata["sampled_radii_A"] == pytest.approx([0.0])
    assert rng.gaussian_calls == 1
    assert rng.direction_calls == 0
    assert "p0_state" not in metadata


def test_gaussian_radius_minimum_image_provenance_across_cell_boundary():
    parent = Structure(
        Lattice.cubic(10.0), ["Li", "O"],
        [[0.99, 0.50, 0.50], [0.50, 0.50, 0.50]],
    )
    rng = _ScriptedRng(0.3, [[0.3, 0, 0]], [[1, 0, 0]])

    child, metadata = _run(parent, rng, sigma=0.3, trials=1)

    assert child is not None and metadata["proposal_status"] == "ACCEPTED"
    assert check_geometry_clash(child)[0] is True
    measured = _minimum_image_magnitude(parent, child, 0)
    assert measured == pytest.approx(0.3, abs=1e-10)
    assert metadata["sampled_radii_A"] == pytest.approx([0.3])
    assert metadata["realized_displacement_magnitudes_A"] == pytest.approx([measured])
    assert child[0].frac_coords[0] % 1.0 == pytest.approx(0.02, abs=1e-10)


def test_gaussian_radius_requires_configured_species_without_consuming_rng():
    rng = _ScriptedRng(0.3, [], [])

    with pytest.raises(ValueError, match="no sites matching mobile_ion='Na'"):
        _run(_open_parent("Li"), rng, mobile_ion="Na")

    assert rng.gaussian_calls == rng.direction_calls == 0
