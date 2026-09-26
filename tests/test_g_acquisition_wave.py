import pytest
"""Tests for deterministic parent-diverse P1 wave selection."""

from rudeus.mlip.acquisition_wave import materialize_wave, select_parent_diverse_wave


def test_wave1_keeps_one_child_per_parent_and_defers_duplicates():
    rows = [
        {"batch_id": "a2", "parent_id": "p1", "structure_sha256": "2" * 64, "generation_operator": "substitute",
         "parent_chemical_family": "oxide"},
        {"batch_id": "a1", "parent_id": "p1", "structure_sha256": "1" * 64, "generation_operator": "displace",
         "parent_chemical_family": "oxide"},
        {"batch_id": "b1", "parent_id": "p2", "structure_sha256": "3" * 64, "generation_operator": "substitute",
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
        {"batch_id": "c1", "parent_id": "p3", "structure_sha256": "3" * 64, "generation_operator": "substitute",
         "parent_chemical_family": "oxide"},
        {"batch_id": "a1", "parent_id": "p1", "structure_sha256": "1" * 64, "generation_operator": "displace",
         "parent_chemical_family": "oxide"},
        {"batch_id": "b1", "parent_id": "p2", "structure_sha256": "2" * 64, "generation_operator": "substitute",
         "parent_chemical_family": "halide"},
    ]

    a = select_parent_diverse_wave(rows)
    b = select_parent_diverse_wave(list(reversed(rows)))
    assert a == b


def test_wave_manifest_binds_structure_hashes_and_materializes_exact_bytes(tmp_path):
    import json

    pending = tmp_path / "pending"
    pending.mkdir()
    rows = []
    for batch_id, parent_id, sha in [
        ("a1", "p1", "1" * 64),
        ("b1", "p2", "2" * 64),
    ]:
        payload = {
            "batch_id": batch_id,
            "parent_id": parent_id,
            "structure_sha256": sha,
            "generation_operator": "displace",
            "parent_chemical_family": "oxide",
        }
        (pending / f"{batch_id}.json").write_text(
            json.dumps(payload, sort_keys=True), encoding="utf-8")
        rows.append(payload)

    report = select_parent_diverse_wave(rows)
    assert len(report["wave1"]["cohort_identity_sha256"]) == 64
    assert report["wave1"]["bindings"] == [
        {"batch_id": "a1", "structure_sha256": "1" * 64},
        {"batch_id": "b1", "structure_sha256": "2" * 64},
    ]

    out = tmp_path / "wave1"
    written = materialize_wave(pending, report, out)
    assert len(written) == 2
    assert sorted(p.name for p in out.glob("*.json")) == ["a1.json", "b1.json"]
    assert (out / "a1.json").read_bytes() == (pending / "a1.json").read_bytes()


def test_materialize_wave_refuses_structure_binding_mismatch(tmp_path):
    import json

    pending = tmp_path / "pending"
    pending.mkdir()
    payload = {
        "batch_id": "a1",
        "parent_id": "p1",
        "structure_sha256": "1" * 64,
        "generation_operator": "displace",
        "parent_chemical_family": "oxide",
    }
    (pending / "a1.json").write_text(json.dumps(payload), encoding="utf-8")
    report = select_parent_diverse_wave([payload])
    report["wave1"]["bindings"][0]["structure_sha256"] = "9" * 64

    with pytest.raises(ValueError, match="source structure_sha256 mismatch"):
        materialize_wave(pending, report, tmp_path / "wave1")
