"""Empirical data loaders, validation anchors, and normalization ([E] stage).

RESPONSIBILITIES:
- Ingestion and normalization of empirical experimental and computational datasets.
- Loader for the OBELiX dataset (github.com/NRC-Mila/OBELiX).
- Loader for the LiIon (~820-entry) temperature-resolved conductivity dataset.

CRITICAL INVARIANTS & HARD CONSTRAINTS:
1. OBELiX Leakage-Aware Split:
   The empirical anchor is the OBELiX dataset using its officially published leakage-aware
   grouped train/test split. This split must NEVER be re-shuffled, re-partitioned, or
   re-generated locally. Doing so invalidates all empirical benchmarking.

2. LiIon Dataset Isolation:
   The LiIon dataset is a separate supplementary benchmark source. It must NEVER be merged
   into OBELiX rows. Its temperature-resolved conductivities must NEVER have temperature
   averaged away (Arrhenius slope / activation barrier must remain temperature-resolved).
"""
