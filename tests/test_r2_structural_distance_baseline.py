from __future__ import annotations

import pytest

from rhombus.domain import (
    CompositionDescriptor,
    StructuralDescriptor,
    structural_distance,
)


def _descriptor(
    composition: dict[int, int],
    lengths: tuple[float, float, float],
    angles: tuple[float, float, float],
    volume_per_atom: float,
) -> StructuralDescriptor:
    return StructuralDescriptor(
        composition=CompositionDescriptor.from_count_mapping(composition),
        cell_lengths=lengths,
        cell_angles_deg=angles,
        volume_per_atom=volume_per_atom,
    )


def test_structural_distance_is_zero_for_identical_descriptor() -> None:
    row = _descriptor({3: 1, 13: 1, 8: 2}, (5.0, 5.0, 5.0), (90.0, 90.0, 90.0), 12.5)
    result = structural_distance(row, row)

    assert result.combined_distance == pytest.approx(0.0)
    assert result.composition_distance == pytest.approx(0.0)


def test_structural_distance_is_symmetric_and_sensitive_to_composition() -> None:
    left = _descriptor({3: 1, 13: 1, 8: 2}, (5.0, 5.0, 5.0), (90.0, 90.0, 90.0), 12.5)
    right = _descriptor({3: 2, 8: 1}, (5.5, 5.0, 4.8), (92.0, 90.0, 88.0), 13.0)

    lr = structural_distance(left, right)
    rl = structural_distance(right, left)

    assert lr.combined_distance == pytest.approx(rl.combined_distance)
    assert lr.composition_distance > 0
    assert lr.lattice_length_distance > 0
    assert lr.lattice_angle_distance > 0
    assert lr.volume_per_atom_distance > 0


def test_structural_distance_weights_are_explicit_and_fail_closed() -> None:
    left = _descriptor({3: 1, 8: 1}, (5.0, 5.0, 5.0), (90.0, 90.0, 90.0), 10.0)
    right = _descriptor({3: 1, 8: 1}, (6.0, 5.0, 5.0), (90.0, 90.0, 90.0), 10.0)

    only_lengths = structural_distance(
        left,
        right,
        weights={
            "composition": 0.0,
            "cell_lengths": 1.0,
            "cell_angles": 0.0,
            "volume_per_atom": 0.0,
        },
    )
    assert only_lengths.combined_distance == pytest.approx(
        only_lengths.lattice_length_distance
    )

    with pytest.raises(ValueError, match="unknown structural distance weight"):
        structural_distance(left, right, weights={"mystery": 1.0})

    with pytest.raises(ValueError, match="at least one"):
        structural_distance(
            left,
            right,
            weights={
                "composition": 0.0,
                "cell_lengths": 0.0,
                "cell_angles": 0.0,
                "volume_per_atom": 0.0,
            },
        )


def test_distance_is_not_itself_an_ood_classifier() -> None:
    left = _descriptor({3: 1, 8: 1}, (5.0, 5.0, 5.0), (90.0, 90.0, 90.0), 10.0)
    right = _descriptor({3: 1, 8: 1}, (5.1, 5.0, 5.0), (90.0, 90.0, 90.0), 10.0)

    result = structural_distance(left, right)

    assert result.combined_distance >= 0
    assert not hasattr(result, "domain_status")
