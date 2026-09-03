"""Rudeus: $0-budget solid-state electrolyte discovery pipeline (codename Rhombus).

Core package containing:
- empirical: OBELiX & LiIon benchmark loaders and normalizers ([E] stage)
- generation: Candidate generation via parent retrieval, perturbation, and substitution ([G] stage)
- filters: Static filters (P0), BVSE screening (F2, probationary), and diffusive regime validation (F3)
- mlip: Machine learning interatomic potential relaxation, stability, and transport screening (P1-P3)
- bench: Empirical benchmark suite and filter-enrichment evaluation harness
- schema: Tri-state lifecycle state machine and append-only evidence log
"""

__version__ = "0.1.0"
