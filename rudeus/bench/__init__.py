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
