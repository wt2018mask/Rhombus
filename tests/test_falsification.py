"""Tests for rudeus.bench.falsification (negative-control gate, small fixtures)."""

from types import SimpleNamespace

import pandas as pd
import pytest

from rudeus.bench.falsification import (
    NEGATIVE_CONTROL_IDS,
    run_all_falsification_gates,
    run_falsification_gate,
)


def _make_stub_dataset(tmp_path, neg_ids, n_positives=3):
    """Duck-typed OBELiXDataset stub: CIF files + df/test_df with ID/Composition."""
    cif_dir = tmp_path / "cifs"
    cif_dir.mkdir()
    for entry_id in neg_ids:
        (cif_dir / f"{entry_id}.cif").write_text("stub")
    neg_rows = [
        {"ID": entry_id, "Composition": "Li7P3S11", "Ionic conductivity (S cm-1)": 1e-9}
        for entry_id in neg_ids
    ]
    pos_rows = [
        {"ID": f"pos{i}", "Composition": "Li7La3Zr2O12", "Ionic conductivity (S cm-1)": 1e-2}
        for i in range(n_positives)
    ]
    df = pd.DataFrame(neg_rows + pos_rows)
    test_df = pd.DataFrame(pos_rows)
    return SimpleNamespace(df=df, test_df=test_df, cif_dir=cif_dir,
                           get_structure=lambda entry_id: None)


def test_negative_control_id_count():
    """The 46 gathered negative controls must all be present."""
    assert len(NEGATIVE_CONTROL_IDS) == 46
    assert len(set(NEGATIVE_CONTROL_IDS)) == 46  # no duplicates


def test_gate_fails_when_negatives_rank_high(tmp_path):
    """Scorer ranking insulators at the top must FAIL the gate."""
    stub = _make_stub_dataset(tmp_path, NEGATIVE_CONTROL_IDS[:4], n_positives=3)

    def neg_high(row, dataset):
        return 1.0 if row.get("is_negative_control", False) else 0.0

    res = run_falsification_gate("test_high", neg_high, stub)
    assert res.n_negatives_loaded == 4
    assert res.n_negatives_scored == 4
    assert res.fraction_neg_top20 == pytest.approx(0.5)  # 2 of 4 in top-20% of 7
    assert res.gate_result == "FAIL"
    assert "test_high" in res.rationale


def test_gate_passes_when_negatives_rank_low(tmp_path):
    """Scorer burying insulators at the bottom must PASS the gate."""
    stub = _make_stub_dataset(tmp_path, NEGATIVE_CONTROL_IDS[:4], n_positives=3)

    def neg_low(row, dataset):
        return 0.0 if row.get("is_negative_control", False) else 1.0

    res = run_falsification_gate("test_low", neg_low, stub)
    assert res.fraction_neg_top10 == pytest.approx(0.0)
    assert res.fraction_neg_top20 == pytest.approx(0.0)
    assert res.gate_result == "PASS"


def test_gate_fails_when_no_controls_loadable(tmp_path):
    """Empty negative set fails closed (never silently passes)."""
    stub = _make_stub_dataset(tmp_path, [], n_positives=3)
    res = run_falsification_gate("test_empty", lambda row, ds: 0.0, stub)
    assert res.n_negatives_loaded == 0
    assert res.gate_result == "FAIL"


def test_run_all_default_scorers(tmp_path):
    """Default run covers both required scorers without touching real BVSE."""
    stub = _make_stub_dataset(tmp_path, NEGATIVE_CONTROL_IDS[:4], n_positives=3)
    results = run_all_falsification_gates(stub)
    assert set(results) == {"composition_baseline", "f2_bvse_probation"}
    for res in results.values():
        assert res.gate_result in ("PASS", "FAIL")
        assert 0.0 <= res.fraction_neg_top20 <= 1.0
