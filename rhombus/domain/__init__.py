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
from .overlap import (
    WBMStreamingOverlapAuditor,
    WBMTargetIndexSummary,
    WBMTargetRecord,
    build_wbm_target_index,
    iter_wbm_initial_structure_jsonl,
)
from .membership import (
    MembershipIndexRecord,
    MembershipIndexSummary,
    build_membership_index,
    candidate_locators_for_near_duplicate,
    fingerprint_candidate_count,
)
from .salex import (
    SalexSourceIdentity,
    build_salex_membership_index,
    build_salex_membership_index_with_frozen_protocols,
    iter_salex_membership_records,
)
from .structure_protocols import (
    CANDIDATE_FINGERPRINT_PROTOCOL_ID,
    NEAR_DUPLICATE_PROTOCOL_ID,
    PROTOTYPE_GROUP_PROTOCOL_ID,
    STRICT_STRUCTURE_EQUIVALENCE_PROTOCOL_ID,
    as_pymatgen_structure,
    matbench_prototype_group,
    near_duplicate_structure,
    strict_structure_equivalent,
    structure_candidate_fingerprint_sha256,
)
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
    "structure_candidate_fingerprint_sha256",
    "strict_structure_equivalent",
    "near_duplicate_structure",
    "matbench_prototype_group",
    "as_pymatgen_structure",
    "STRICT_STRUCTURE_EQUIVALENCE_PROTOCOL_ID",
    "PROTOTYPE_GROUP_PROTOCOL_ID",
    "NEAR_DUPLICATE_PROTOCOL_ID",
    "CANDIDATE_FINGERPRINT_PROTOCOL_ID",
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
    "iter_wbm_initial_structure_jsonl",
    "build_wbm_target_index",
    "WBMTargetRecord",
    "WBMTargetIndexSummary",
    "WBMStreamingOverlapAuditor",
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
    "build_salex_membership_index_with_frozen_protocols",
    "candidate_locators_for_near_duplicate",
    "classify_coverage",
    "deterministic_wbm_sample",
    "fingerprint_candidate_count",
    "iter_salex_membership_records",
    "structural_distance",
    "summarize_exposure_audit",
    "verify_frozen_bytes",
]
