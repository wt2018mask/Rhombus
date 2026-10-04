"""Lightweight tests for full ordered-parent G acquisition census."""

from pathlib import Path
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


def test_prepare_batches_persists_diversity_metadata(tmp_path, monkeypatch):
    import json
    from rudeus.mlip import make_batches as mb

    ordered = SimpleNamespace(is_ordered=True)
    parent = SimpleNamespace(
        parent_id="obelix:a",
        perturbable=True,
        structure=ordered,
        conductivity=1.23e-4,
        chemical_family="oxide",
    )
    kid = SimpleNamespace(
        material_id="g1-test",
        formula="Li2O",
        structure_dict={"sites": [{"label": "Li"}]},
        existence_state=SimpleNamespace(value="PLAUSIBLE"),
        metadata={
            "novelty_tag": "novel",
            "operators": [{"operator": "vacancy"}],
            "family": "G1",
        },
    )

    monkeypatch.setattr(mb, "retrieve_obelix_parents", lambda _: [parent])
    monkeypatch.setattr(mb, "generate_children", lambda *a, **k: [kid])

    out = tmp_path / "pending"
    written = mb.prepare_batches("config.yaml", ["obelix:a"], str(out))
    assert len(written) == 1

    payload = json.loads((out / Path(written[0]).name).read_text(encoding="utf-8"))
    assert payload["generation_operator"] == "vacancy"
    assert payload["generation_family"] == "G1"
    assert payload["parent_chemical_family"] == "oxide"
    assert payload["parent_published_conductivity_S_per_cm"] == 1.23e-4
