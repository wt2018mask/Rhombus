"""Known-material B5 P1 entry gate derived from material-level P0 semantics.

This module plans eligibility only. It does not create remote tasks or execute P1.
The gate is fail-closed: only material-level P0 PLAUSIBLE may proceed; FAIL is
terminal for P1 planning, and INDETERMINATE is explicitly held.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from rudeus.science.contracts import Record
from rudeus.science.known_material_b5_p0_material_semantics import (
    B5P0MaterialAssessment,
    MaterialP0Disposition,
)


B5_P1_ENTRY_GATE_VERSION = "known-material-b5-p1-entry-gate-v1"


class P1EntryDisposition(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    BLOCKED_P0_FAIL = "BLOCKED_P0_FAIL"
    HELD_P0_INDETERMINATE = "HELD_P0_INDETERMINATE"


@dataclass(frozen=True, kw_only=True)
class B5P1EntryDecision(Record):
    gate_version: str
    material_key: str
    p0_material_assessment_hash: str
    p0_disposition: str
    p1_entry_disposition: str
    p1_execution_authorized: bool
    reason: str
    qualification_evidence_authorized: bool = False
    production_search_authorized: bool = False

    def validate(self):
        super().validate()
        if self.gate_version != B5_P1_ENTRY_GATE_VERSION:
            raise ValueError("unsupported B5 P1 entry gate version")
        MaterialP0Disposition(self.p0_disposition)
        disposition = P1EntryDisposition(self.p1_entry_disposition)
        expected = disposition == P1EntryDisposition.ELIGIBLE
        if self.p1_execution_authorized is not expected:
            raise ValueError("P1 authorization disagrees with entry disposition")
        if self.qualification_evidence_authorized or self.production_search_authorized:
            raise ValueError("DEV P1 entry gate authorizes no qualification or production")


def decide_p1_entry(assessment: B5P0MaterialAssessment) -> B5P1EntryDecision:
    disposition = MaterialP0Disposition(assessment.disposition)
    if disposition == MaterialP0Disposition.PLAUSIBLE:
        entry = P1EntryDisposition.ELIGIBLE
        reason = "material-level P0 is PLAUSIBLE under representation-aware semantics"
    elif disposition == MaterialP0Disposition.FAIL:
        entry = P1EntryDisposition.BLOCKED_P0_FAIL
        reason = "material-level P0 contains an applicable scientific failure"
    else:
        entry = P1EntryDisposition.HELD_P0_INDETERMINATE
        reason = "material-level P0 remains indeterminate; unsupported or unresolved evidence cannot be promoted to P1 eligibility"

    result = B5P1EntryDecision(
        gate_version=B5_P1_ENTRY_GATE_VERSION,
        material_key=assessment.material_key,
        p0_material_assessment_hash=assessment.content_hash,
        p0_disposition=assessment.disposition,
        p1_entry_disposition=entry.value,
        p1_execution_authorized=entry == P1EntryDisposition.ELIGIBLE,
        reason=reason,
        qualification_evidence_authorized=False,
        production_search_authorized=False,
    )
    result.validate()
    return result


def build_p1_entry_decisions(
    assessments: Sequence[B5P0MaterialAssessment],
) -> tuple[B5P1EntryDecision, ...]:
    items = tuple(sorted(assessments, key=lambda item: item.material_key))
    if len({item.material_key for item in items}) != len(items):
        raise ValueError("P1 entry gate requires one material assessment per material")
    return tuple(decide_p1_entry(item) for item in items)
