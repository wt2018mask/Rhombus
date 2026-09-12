"""Candidate generation module ([G] stage).

RESPONSIBILITIES:
- G1 Generation: Parent crystal structure retrieval from known fast-ion conductors
  followed by local structural perturbations (e.g. interstitial insertion, vacancy creation,
  lattice strain/rattling).
- G2 Generation: Stoichiometric and isovalent/aliovalent chemical substitutions guided
  by ionic radii and chemical compatibility (e.g. SMACT, Pauling rules).

CONSTRAINTS & DESIGN NOTES:
- Free compute comes from preemptible environments (Kaggle/Colab). Generation runs in
  stateless, deterministic, hash-based batches so any generator can be resumed without locks.
- Active learning loops (e.g. MatterGen, BoTorch Bayesian optimization) are explicitly
  DEFERRED until empirical calibration benchmarks pass their verification gates.
"""

from rudeus.generation.generator import (
    ParentRecord,
    retrieve_obelix_parents,
    retrieve_liion_parents,
    structure_sha256,
    op_displace,
    op_strain,
    op_vacancy,
    op_interstitial,
    op_substitute,
    generate_children,
    operator_family,
    G2_OPERATORS,
    OPERATORS,
)
from rudeus.generation.audit import audit_candidates, format_audit

__all__ = [
    "ParentRecord",
    "retrieve_obelix_parents",
    "retrieve_liion_parents",
    "structure_sha256",
    "op_displace",
    "op_strain",
    "op_vacancy",
    "op_interstitial",
    "op_substitute",
    "generate_children",
    "operator_family",
    "G2_OPERATORS",
    "OPERATORS",
    "audit_candidates",
    "format_audit",
]
