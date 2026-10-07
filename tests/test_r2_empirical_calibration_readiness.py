from __future__ import annotations

from rhombus.domain import ErrorDistanceObservation, assess_calibration_readiness


def _obs(
    i: int,
    *,
    material: str,
    group: str,
    source: str,
    membership: str = "RESOLVED_NOT_IN_TRAINING",
) -> ErrorDistanceObservation:
    return ErrorDistanceObservation(
        observation_id=f"obs:{i}",
        material_id=material,
        group_id=group,
        structural_distance=0.01 * i,
        error_value=0.02 * i,
        error_metric="force_mae_ev_per_a",
        reference_source_id=source,
        model_checkpoint_sha256="a" * 64,
        training_membership=membership,
    )


def test_calibration_readiness_requires_independent_size_and_groups() -> None:
    rows = (
        _obs(1, material="m1", group="g1", source="s1"),
        _obs(2, material="m2", group="g1", source="s2"),
    )
    result = assess_calibration_readiness(rows)

    assert result.ready is False
    assert result.observation_count == 2
    assert result.material_count == 2
    assert result.group_count == 1
    assert any("observations" in blocker for blocker in result.blockers)
    assert any("materials" in blocker for blocker in result.blockers)
    assert any("groups" in blocker for blocker in result.blockers)


def test_unresolved_training_membership_blocks_generalization_calibration() -> None:
    rows = tuple(
        _obs(
            i,
            material=f"m{i}",
            group=f"g{(i % 3) + 1}",
            source=f"s{(i % 2) + 1}",
            membership=(
                "UNRESOLVED_EXACT_MEMBERSHIP"
                if i == 1
                else "RESOLVED_NOT_IN_TRAINING"
            ),
        )
        for i in range(1, 13)
    )
    result = assess_calibration_readiness(rows)

    assert result.ready is False
    assert any("training membership" in blocker for blocker in result.blockers)


def test_ready_dataset_requires_consistent_metric_checkpoint_and_source_diversity() -> None:
    rows = tuple(
        _obs(
            i,
            material=f"m{i}",
            group=f"g{(i % 3) + 1}",
            source=f"s{(i % 2) + 1}",
        )
        for i in range(1, 13)
    )
    result = assess_calibration_readiness(rows)

    assert result.ready is True
    assert result.blockers == ()
