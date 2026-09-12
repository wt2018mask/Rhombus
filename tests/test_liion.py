"""Tests for rudeus.empirical.liion and rudeus.bench.liion_crosscheck (small fixtures)."""

from types import SimpleNamespace

import pandas as pd
import pytest

from rudeus.empirical import (
    LIION_RT_MAX_C,
    LIION_RT_MIN_C,
    LiIonDataset,
    LiIonIntegrityReport,
)
from rudeus.bench.liion_crosscheck import run_liion_sulfide_rt_crosscheck

COLUMNS = ["ID", "composition", "source", "temperature", "target",
           "log_target", "family", "ChemicalFamily"]


def _write_liion_csv(path, rows):
    pd.DataFrame(rows, columns=COLUMNS).to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def liion_csv(tmp_path):
    """6-row fixture: RT/non-RT x sulfide/oxide/null-family + one dropped row."""
    rows = [
        # sulfide RT, superionic (two temps of one composition: never averaged)
        [1, "Li10GeP2S12", "s", 25.0, 1e-2, -2.0, "x", "Sulphides"],
        [2, "Li10GeP2S12", "s", 30.0, 1.2e-2, -1.92, "x", "Sulphides"],
        # sulfide, hot (outside RT window)
        [3, "Li7P3S11", "s", 100.0, 5e-3, -2.30, "x", "Sulphides"],
        # oxide RT, non-superionic
        [4, "Li7La3Zr2O12", "s", 25.0, 1e-4, -4.0, "x", "Oxides"],
        # null family RT (retained, flagged)
        [5, "Li3InCl6", "s", 25.0, 1e-3, -3.0, "x", None],
        # non-finite target: dropped, never imputed
        [6, "LiX", "s", 25.0, float("nan"), float("nan"), "x", "Oxides"],
    ]
    return _write_liion_csv(tmp_path / "liion.csv", rows)


def test_liion_loader_counts_and_integrity(liion_csv):
    ds = LiIonDataset(liion_csv)
    assert isinstance(ds.integrity_report, LiIonIntegrityReport)
    assert ds.integrity_report.total_rows == 5  # NaN-target row dropped
    assert ds.integrity_report.rows_with_null_family == 1
    assert ds.integrity_report.n_rt_rows == 4
    assert ds.integrity_report.n_sulfide_rows == 3
    assert ds.integrity_report.n_sulfide_rt_rows == 2
    assert (LIION_RT_MIN_C, LIION_RT_MAX_C) == (18.0, 32.0)


def test_liion_rt_slices_keep_temperature_resolution(liion_csv):
    """Both same-composition RT rows survive: no averaging, no dedup."""
    ds = LiIonDataset(liion_csv)
    sulf_rt = ds.sulfide_rt_slice()
    assert len(sulf_rt) == 2
    assert sorted(sulf_rt["temperature"].tolist()) == [25.0, 30.0]
    assert len(ds.rt_slice()) == 4
    assert len(ds.filter(family="sulph")) == 3
    # known_family_only excludes the null-family row
    assert len(ds.filter(known_family_only=True)) == 4


def test_liion_missing_file_and_columns(tmp_path):
    with pytest.raises(FileNotFoundError):
        LiIonDataset(tmp_path / "nope.csv")
    bad = tmp_path / "bad.csv"
    pd.DataFrame([{"ID": 1, "composition": "LiX"}]).to_csv(bad, index=False)
    with pytest.raises(KeyError):
        LiIonDataset(str(bad))


def _make_stub_obelix(tmp_path):
    """OBELiX stub with two CIF-linked formulas; no real structures."""
    cif_dir = tmp_path / "cifs"
    cif_dir.mkdir()
    (cif_dir / "o1.cif").write_text("stub")
    (cif_dir / "o2.cif").write_text("stub")
    df = pd.DataFrame([
        {"ID": "o1", "Composition": "Li10GeP2S12"},
        {"ID": "o2", "Composition": "Li7P3S11"},
    ])
    return SimpleNamespace(df=df, test_df=df, cif_dir=cif_dir,
                           get_structure=lambda entry_id: None)


def test_crosscheck_reports_coverage_and_single_class_honestly(tmp_path):
    """Fixture slice: 2 RT sulfide rows, both superionic -> BVSE AUC undefined."""
    liion_path = _write_liion_csv(tmp_path / "li.csv", [
        [1, "Li10GeP2S12", "s", 25.0, 1e-2, -2.0, "x", "Sulphides"],
        [2, "Li10GeP2S12", "s", 30.0, 1.2e-2, -1.92, "x", "Sulphides"],
        [3, "Li7P3S11", "s", 100.0, 5e-3, -2.30, "x", "Sulphides"],  # hot: excluded
    ])
    res = run_liion_sulfide_rt_crosscheck(
        _make_stub_obelix(tmp_path), LiIonDataset(liion_path))
    assert res.n_rt_sulfide_rows == 2
    assert res.n_unique_compositions == 1  # temperature NOT averaged away
    assert res.n_bvse_matched == 2
    assert res.n_bvse_formulas == 1
    assert res.bvse_auc is None  # single class -> honestly undefined
    assert "INCONCLUSIVE" in res.readout


def test_crosscheck_two_class_subset(tmp_path):
    """Mixed-class slice: baseline AUC=1.0; constant BVSE fallback scores 0.5."""
    liion_path = _write_liion_csv(tmp_path / "li2.csv", [
        [1, "Li10GeP2S12", "s", 25.0, 1e-2, -2.0, "x", "Sulphides"],
        [2, "Li7P3S11", "s", 25.0, 1e-6, -6.0, "x", "Sulphides"],
        [3, "UnparseableMixture!?#", "s", 25.0, 1e-6, -6.0, "x", "Sulphides"],
    ])
    res = run_liion_sulfide_rt_crosscheck(
        _make_stub_obelix(tmp_path), LiIonDataset(liion_path))
    assert res.n_rt_sulfide_rows == 3
    assert res.baseline_auc == pytest.approx(1.0)
    assert res.n_bvse_matched == 2  # mixture notation row honestly unmatched
    assert res.bvse_auc == pytest.approx(0.5)
    # n=2 matched < 15: honestly INCONCLUSIVE, small-sample noise dominates
    assert "INCONCLUSIVE" in res.readout
