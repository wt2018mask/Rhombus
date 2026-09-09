"""Empirical benchmark and filter-enrichment evaluation harness ([BENCH] stage).

RESPONSIBILITIES:
- Benchmark execution and evaluation on the OBELiX published leakage-aware train/test split.
- Supplementary validation on the temperature-resolved LiIon conductivity dataset.
- Filter enrichment evaluation: Quantifying the precision/recall trade-offs and enrichment ratios
  of P0, F2 (BVSE), F3 (MSD + alpha_2), and MLIP stages.
- Calibration gate: Determines whether provisional numeric thresholds can graduate to calibrated
  status, and gates the activation of future active-learning loops (MatterGen / BoTorch).

CONSTRAINTS:
- The OBELiX official split must remain immutable.
- Thresholds evaluated here are logged with quantitative performance metrics before any graduation.
"""

from rudeus.bench.metrics import (
    MetricEvaluationResult,
    compute_roc_auc,
    compute_bootstrap_ci,
    compute_enrichment_at_k,
    run_label_scramble_test,
    compute_within_family_aucs,
    evaluate_filter_candidate,
)
from rudeus.bench.harness import (
    BenchmarkHarness,
    composition_baseline_scorer,
    f2_bvse_probation_scorer,
)

__all__ = [
    "MetricEvaluationResult",
    "compute_roc_auc",
    "compute_bootstrap_ci",
    "compute_enrichment_at_k",
    "run_label_scramble_test",
    "compute_within_family_aucs",
    "evaluate_filter_candidate",
    "BenchmarkHarness",
    "composition_baseline_scorer",
    "f2_bvse_probation_scorer",
]
