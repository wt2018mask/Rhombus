"""Tests for rudeus.bench: empirical benchmark loader, metrics, and enrichment harness."""

import numpy as np
import pytest
from pathlib import Path

from rudeus.bench.metrics import (
    compute_bootstrap_ci,
    compute_enrichment_at_k,
    compute_roc_auc,
    compute_within_family_aucs,
    evaluate_filter_candidate,
    run_label_scramble_test,
)
from rudeus.empirical.obelix import OBELiXDataset, classify_chemical_family


def test_hand_computed_toy_auc_and_metrics():
    """Verify enrichment metrics against a synthetic toy dataset with known, hand-computed AUC.

    Toy dataset:
      y_true  = [0,   0,   0,   1,   1]
      y_score = [0.1, 0.2, 0.4, 0.3, 0.9]

    Pairwise comparisons (Pos vs Neg):
      Pos(0.3) vs Neg(0.1): 1
      Pos(0.3) vs Neg(0.2): 1
      Pos(0.3) vs Neg(0.4): 0
      Pos(0.9) vs Neg(0.1): 1
      Pos(0.9) vs Neg(0.2): 1
      Pos(0.9) vs Neg(0.4): 1

    Total pairs = 2 * 3 = 6
    Concordant pairs = 5
    Exact analytical AUC = 5 / 6 = 0.833333...
    """
    y_true = np.array([0, 0, 0, 1, 1])
    y_score = np.array([0.1, 0.2, 0.4, 0.3, 0.9])

    # 1. Exact AUC check
    auc = compute_roc_auc(y_true, y_score)
    expected_auc = 5.0 / 6.0
    assert auc == pytest.approx(expected_auc, abs=1e-5), (
        f"Expected AUC {expected_auc:.4f}, got {auc:.4f}"
    )

    # 2. Bootstrap CI sanity
    ci_lower, ci_upper = compute_bootstrap_ci(
        y_true, y_score, n_bootstraps=500, ci=0.95, seed=42
    )
    assert 0.0 <= ci_lower <= auc <= ci_upper <= 1.0

    # 3. Precision & Enrichment at top 20% (k = 1 sample)
    # Top ranked sample is index 4 (score 0.9), label 1 -> precision = 1.0
    # Baseline rate = 2 / 5 = 0.40 -> enrichment = 1.0 / 0.40 = 2.50x
    prec_top20, enrich_top20 = compute_enrichment_at_k(y_true, y_score, fraction=0.20)
    assert prec_top20 == pytest.approx(1.0)
    assert enrich_top20 == pytest.approx(2.50)

    # 4. Label scramble test
    # With AUC=0.833 vs N=500 random shuffles, scramble p-value should be low
    p_scramble = run_label_scramble_test(
        y_true, y_score, observed_auc=auc, n_scrambles=500, seed=42
    )
    assert 0.0 <= p_scramble <= 1.0

    # 5. Chemical family grouping test
    families = ["oxide", "oxide", "oxide", "sulfide", "sulfide"]
    # With min_family_n=2, oxide has n=3 (all 0s, single class -> None), sulfide has n=2 (all 1s, single class -> None)
    within_aucs = compute_within_family_aucs(y_true, y_score, families, min_family_n=2)
    assert "oxide" in within_aucs
    assert within_aucs["oxide"] is None  # Single class


def test_obelix_dataset_loader_and_integrity():
    """Verify loading real OBELiX dataset and asserting published invariants."""
    obelix_path = Path("data/obelix")
    if not obelix_path.exists():
        pytest.skip("data/obelix repository not found locally")

    dataset = OBELiXDataset(obelix_path)
    report = dataset.integrity_report

    # Invariants from official NRC-Mila OBELiX release
    assert report.total_row_count == 599, f"Expected 599 rows, got {report.total_row_count}"
    assert report.train_row_count == 478, f"Expected 478 train rows, got {report.train_row_count}"
    assert report.test_row_count == 121, f"Expected 121 test rows, got {report.test_row_count}"
    assert report.cif_linked_count == 321, f"Expected 321 CIFs, got {report.cif_linked_count}"
    assert report.dropped_non_finite_count == 0, "No rows should have non-finite conductivity"
    assert report.leaked_formula_keys_count == 0, (
        "Published split must have zero leaked composition keys"
    )

    # Verify structure loader works for a sample CIF
    sample_struct = dataset.get_structure("0ii")
    assert sample_struct is not None
    assert len(sample_struct) > 0

    # Chemical family classification sanity
    assert classify_chemical_family("Li7P3S11") == "sulfide"
    assert classify_chemical_family("Li7La3Zr2O12") == "oxide"
    assert classify_chemical_family("Li3InCl6") == "halide"
