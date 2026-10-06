"""Shared-site assignment tests for cubic Al-LLZO."""
import pytest

from rudeus.science.known_material_shared_site_assignment import (
    deterministic_shared_site_assignment,
)


def test_cubic_llzo_li_al_assignments_are_disjoint_and_count_preserving():
    assignment = deterministic_shared_site_assignment(
        site_count=48, first_count=26, second_count=3, seed=0, namespace="Li1-Al1"
    )
    assert len(assignment.first_species_indices) == 26
    assert len(assignment.second_species_indices) == 3
    assert set(assignment.first_species_indices).isdisjoint(
        assignment.second_species_indices
    )


def test_shared_site_assignment_is_reproducible_and_seed_diverse():
    first = deterministic_shared_site_assignment(
        site_count=48, first_count=26, second_count=3, seed=4, namespace="Li1-Al1"
    )
    repeat = deterministic_shared_site_assignment(
        site_count=48, first_count=26, second_count=3, seed=4, namespace="Li1-Al1"
    )
    other = deterministic_shared_site_assignment(
        site_count=48, first_count=26, second_count=3, seed=5, namespace="Li1-Al1"
    )
    assert first == repeat
    assert first.assignment_hash != other.assignment_hash


def test_shared_site_assignment_rejects_overfill():
    with pytest.raises(ValueError, match="exceed available sites"):
        deterministic_shared_site_assignment(
            site_count=48, first_count=46, second_count=3, seed=0, namespace="Li1-Al1"
        )
