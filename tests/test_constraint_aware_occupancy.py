from rudeus.science.constraint_aware_occupancy import (
    available_pair_count,
    endpoint_block_mask,
    merge_block_masks,
    pair_constrained_selection,
)


def test_pair_constrained_selection_is_deterministic_and_capacity_preserving():
    pairs = ((0, 1), (2, 3), (4, 5))
    result_a = pair_constrained_selection(
        incompatible_pairs=pairs,
        allowed_indices=(0, 1, 2, 4, 5),
        occupied_count=2,
        seed=7,
        namespace="test",
    )
    result_b = pair_constrained_selection(
        incompatible_pairs=pairs,
        allowed_indices=(0, 1, 2, 4, 5),
        occupied_count=2,
        seed=7,
        namespace="test",
    )
    assert result_a == result_b
    assert len(result_a.occupied_indices) == 2
    selected = set(result_a.occupied_indices)
    assert all(not ({a, b} <= selected) for a, b in pairs)


def test_block_masks_capture_cross_pool_pair_closure():
    pairs = ((0, 1), (2, 3), (4, 5))
    left = endpoint_block_mask((0, 2))
    right = endpoint_block_mask((1,))
    assert available_pair_count(blocked_mask=left, incompatible_pairs=pairs) == 3
    merged = merge_block_masks((left, right))
    assert available_pair_count(blocked_mask=merged, incompatible_pairs=pairs) == 2
