"""Immutable binding of real B5 DEV P1 evidence to a retained Actions artifact."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from rudeus.science.contracts import Record, require_hash


B5_P1_REAL_EVIDENCE_VERSION = "known-material-b5-p1-real-evidence-v1"


@dataclass(frozen=True, kw_only=True)
class B5P1RealResultBinding(Record):
    batch_id: str
    material_key: str
    component_label: str
    p1_verdict: str
    converged: bool
    input_structure_sha256: str
    relaxed_structure_sha256: str

    def validate(self):
        super().validate()
        if len(self.batch_id) != 16 or any(c not in "0123456789abcdef" for c in self.batch_id):
            raise ValueError("invalid P1 batch id")
        if self.p1_verdict != "KEEP_FOR_P2" or self.converged is not True:
            raise ValueError("canonical B5 P1 retained binding contains non-survivor")
        require_hash(self.input_structure_sha256)
        require_hash(self.relaxed_structure_sha256)


@dataclass(frozen=True, kw_only=True)
class B5P1RealEvidenceBinding(Record):
    evidence_version: str
    workflow_run_id: int
    workflow_run_number: int
    workflow_head_sha: str
    workflow_conclusion: str
    artifact_id: int
    artifact_name: str
    artifact_zip_sha256: str
    source_execution_plan_hash: str
    results: tuple[B5P1RealResultBinding, ...]
    result_count: int
    operational_error_count: int
    qualification_evidence_authorized: bool = False
    held_out_execution_authorized: bool = False
    production_search_authorized: bool = False

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["results"] = tuple(B5P1RealResultBinding.from_dict(x) for x in value["results"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.evidence_version != B5_P1_REAL_EVIDENCE_VERSION:
            raise ValueError("unsupported B5 P1 real-evidence version")
        if self.workflow_run_id <= 0 or self.workflow_run_number <= 0 or self.artifact_id <= 0:
            raise ValueError("invalid GitHub Actions identity")
        if (
            len(self.workflow_head_sha) not in (40, 64)
            or any(ch not in "0123456789abcdef" for ch in self.workflow_head_sha)
        ):
            raise ValueError("invalid Git commit SHA binding")
        require_hash(self.artifact_zip_sha256)
        require_hash(self.source_execution_plan_hash)
        if self.workflow_conclusion != "success":
            raise ValueError("real P1 evidence must bind successful workflow")
        if not self.artifact_name:
            raise ValueError("real P1 evidence requires artifact name")
        if self.result_count != len(self.results) or self.result_count != 3:
            raise ValueError("canonical B5 P1 real evidence must contain exactly three results")
        if self.operational_error_count != 0:
            raise ValueError("canonical B5 P1 real evidence contains operational errors")
        identities = tuple((x.material_key, x.component_label) for x in self.results)
        if identities != tuple(sorted(identities)) or len(set(identities)) != len(identities):
            raise ValueError("real P1 results must be unique and canonically sorted")
        if any((
            self.qualification_evidence_authorized,
            self.held_out_execution_authorized,
            self.production_search_authorized,
        )):
            raise ValueError("DEV P1 evidence authorizes no qualification or production")


def build_p2_authorization_rows(binding: B5P1RealEvidenceBinding) -> tuple[dict, ...]:
    """Minimal exact cohort binding consumed by the existing P2 authorization check."""
    return tuple(
        {
            "batch_id": row.batch_id,
            "relaxed_structure_sha256": row.relaxed_structure_sha256,
        }
        for row in binding.results
    )
