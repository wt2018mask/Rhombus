"""Rhombus 2.0 domain-map primitives."""

from .applicability import (
    ApplicabilityAssessment,
    ModelElementDomain,
    assess_element_coverage,
)
from .descriptors import CompositionDescriptor

__all__ = [
    "ApplicabilityAssessment",
    "CompositionDescriptor",
    "ModelElementDomain",
    "assess_element_coverage",
]
