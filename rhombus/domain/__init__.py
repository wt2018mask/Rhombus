"""Rhombus 2.0 domain-map primitives."""

from .applicability import (
    ApplicabilityAssessment,
    ModelElementDomain,
    assess_element_coverage,
)
from .calibration import CalibratedApplicability, DistanceCalibration, classify_coverage
from .coverage import ReferenceCoverage, ReferenceStructure, assess_reference_coverage
from .descriptors import CompositionDescriptor
from .distance import StructuralDescriptor, StructuralDistance, structural_distance

__all__ = [
    "ApplicabilityAssessment",
    "CalibratedApplicability",
    "CompositionDescriptor",
    "DistanceCalibration",
    "ModelElementDomain",
    "ReferenceCoverage",
    "ReferenceStructure",
    "StructuralDescriptor",
    "StructuralDistance",
    "assess_element_coverage",
    "assess_reference_coverage",
    "classify_coverage",
    "structural_distance",
]
