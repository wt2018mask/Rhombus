"""Lightweight tests for full ordered-parent G acquisition census."""

from types import SimpleNamespace

from rudeus.mlip.make_batches import all_ordered_parent_ids


def test_all_ordered_parent_ids_is_stable_and_ignores_conductivity():
    ordered = SimpleNamespace(is_ordered=True)
    disordered = SimpleNamespace(is_ordered=False)
    parents = [
        SimpleNamespace(parent_id="obelix:z", perturbable=True,
                        structure=ordered, conductivity=None),
        SimpleNamespace(parent_id="obelix:a", perturbable=True,
                        structure=ordered, conductivity=1e-9),
        SimpleNamespace(parent_id="obelix:b", perturbable=True,
                        structure=disordered, conductivity=1.0),
        SimpleNamespace(parent_id="obelix:c", perturbable=False,
                        structure=ordered, conductivity=1.0),
    ]

    assert all_ordered_parent_ids(parents) == ["obelix:a", "obelix:z"]
