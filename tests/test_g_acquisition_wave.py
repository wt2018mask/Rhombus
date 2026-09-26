"""Tests for deterministic parent-diverse P1 wave selection."""

from rudeus.mlip.acquisition_wave import select_parent_diverse_wave


def test_wave1_keeps_one_child_per_parent_and_defers_duplicates():
    rows = [
        {"batch_id": "a2", "parent_id": "p1", "generation_operator": "substitute",
         "parent_chemical_family": "oxide"},
        {"batch_id": "a1", "parent_id": "p1", "generation_operator": "displace",
         "parent_chemical_family": "oxide"},
        {"batch_id": "b1", "parent_id": "p2", "generation_operator": "substitute",
         "parent_chemical_family": "sulfide"},
    ]

    report = select_parent_diverse_wave(rows)

    assert report["purpose"] == "execution_scheduling_only"
    assert report["scientific_verdict_changed"] is False
    assert report["wave1"]["n_batches"] == 2
    assert report["wave1"]["n_unique_parents"] == 2
    assert set(report["wave1"]["batch_ids"]) == {"a1", "b1"}
    assert report["deferred"]["batch_ids"] == ["a2"]


def test_wave_selection_is_deterministic_under_input_permutation():
    rows = [
        {"batch_id": "c1", "parent_id": "p3", "generation_operator": "substitute",
         "parent_chemical_family": "oxide"},
        {"batch_id": "a1", "parent_id": "p1", "generation_operator": "displace",
         "parent_chemical_family": "oxide"},
        {"batch_id": "b1", "parent_id": "p2", "generation_operator": "substitute",
         "parent_chemical_family": "halide"},
    ]

    a = select_parent_diverse_wave(rows)
    b = select_parent_diverse_wave(list(reversed(rows)))
    assert a == b
