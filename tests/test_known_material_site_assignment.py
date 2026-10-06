"""Deterministic site-assignment generator tests."""
from rudeus.science.known_material_site_assignment import deterministic_site_assignment


def test_site_assignment_is_reproducible_and_count_preserving():
    first = deterministic_site_assignment(
        site_count=48, occupied_count=26, seed=7, namespace="Li1"
    )
    second = deterministic_site_assignment(
        site_count=48, occupied_count=26, seed=7, namespace="Li1"
    )
    assert first == second
    assert len(first.occupied_site_indices) == 26
    assert len(set(first.occupied_site_indices)) == 26


def test_site_assignment_changes_with_seed():
    assignments = tuple(
        deterministic_site_assignment(
            site_count=48, occupied_count=26, seed=seed, namespace="Li1"
        )
        for seed in range(4)
    )
    assert len({item.assignment_hash for item in assignments}) == 4
    assert len({item.occupied_site_indices for item in assignments}) == 4


def test_site_assignment_namespace_separates_sublattices():
    li = deterministic_site_assignment(
        site_count=48, occupied_count=26, seed=3, namespace="Li1"
    )
    al = deterministic_site_assignment(
        site_count=48, occupied_count=3, seed=3, namespace="Al1"
    )
    assert li.assignment_hash != al.assignment_hash
