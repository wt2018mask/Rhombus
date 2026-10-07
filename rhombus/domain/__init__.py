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
from .empirical import CalibrationReadiness, ErrorDistanceObservation, assess_calibration_readiness
from .membership import (
    MembershipIndexRecord,
    MembershipIndexSummary,
    build_membership_index,
    candidate_locators_for_near_duplicate,
    exact_membership_count,
)
from .salex import SalexSourceIdentity, build_salex_membership_index, iter_salex_membership_records
from .wbm import WBMSourceContract, WBMSamplingRecord, deterministic_wbm_sample
from .wbm_audit import (
    ExposureAuditInputReadiness,
    ExposureAuditSummary,
    ExposureAuditTarget,
    ExposureComparisonProtocol,
    FrozenRemoteFile,
    MaterialExposureRecord,
    TrainingAuditBasis,
    TrainingExposureReference,
    TrainingSnapshotResolution,
    assess_exposure_audit_input_readiness,
    summarize_exposure_audit,
    verify_frozen_bytes,
)

__all__ = [
    "ApplicabilityAssessment",
    "CalibratedApplicability",
    "CompositionDescriptor",
    "DistanceCalibration",
    "CalibrationReadiness",
    "ErrorDistanceObservation",
    "ModelElementDomain",
    "MembershipIndexRecord",
    "MembershipIndexSummary",
    "ReferenceCoverage",
    "SalexSourceIdentity",
    "ReferenceStructure",
    "StructuralDescriptor",
    "StructuralDistance",
    "WBMSourceContract",
    "ExposureAuditInputReadiness",
    "ExposureAuditSummary",
    "ExposureAuditTarget",
    "ExposureComparisonProtocol",
    "FrozenRemoteFile",
    "MaterialExposureRecord",
    "TrainingAuditBasis",
    "TrainingExposureReference",
    "TrainingSnapshotResolution",
    "WBMSamplingRecord",
    "assess_calibration_readiness",
    "assess_exposure_audit_input_readiness",
    "assess_element_coverage",
    "assess_reference_coverage",
    "build_membership_index",
    "build_salex_membership_index",
    "candidate_locators_for_near_duplicate",
    "classify_coverage",
    "deterministic_wbm_sample",
    "exact_membership_count",
    "iter_salex_membership_records",
    "structural_distance",
    "summarize_exposure_audit",
    "verify_frozen_bytes",
]
