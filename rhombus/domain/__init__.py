"""Rhombus 2.0 domain-map primitives."""

from .applicability import (
    ApplicabilityAssessment,
    ModelElementDomain,
    assess_element_coverage,
)
from .descriptors import CompositionDescriptor
from .distance import StructuralDescriptor, StructuralDistance, structural_distance

__all__ = [
    "ApplicabilityAssessment",
    "CompositionDescriptor",
    "ModelElementDomain",
    "StructuralDescriptor",
    "StructuralDistance",
    "assess_element_coverage",
    "structural_distance",
]
