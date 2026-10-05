"""B2 sample-size / split-feasibility assessment.

This module defines a minimum pre-split feasibility rule for the blind benchmark.
It does not create B6 qualification thresholds or claim statistical power that the
current evidence cannot support.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Mapping

from rudeus.science.contracts import Record
from rudeus.science.known_material_benchmark import TruthClass
from rudeus.science.known_material_b2_coverage import (
    TruthBundleAvailability,
    MaterialCoverageRecord,
)


SAMPLE_SIZE_ASSESSMENT_VERSION = "known-material-sample-size-assessment-v1"


class SampleSizeAssessmentState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"


@dataclass(frozen=True, kw_only=True)
class SampleSizeAssessment(Record):
    assessment_version: str
    state: str
    minimum_scoreable_per_role_pre_split: Mapping[str, int]
    observed_scoreable_per_role: Mapping[str, int]
    required_additional_scoreable_per_role: Mapping[str, int]
    rationale: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    interpretation_constraints: tuple[str, ...]

    def validate(self):
        super().validate()
        if self.assessment_version != SAMPLE_SIZE_ASSESSMENT_VERSION:
            raise ValueError("unsupported sample-size assessment version")
        SampleSizeAssessmentState(self.state)
        required_roles = {
            TruthClass.POSITIVE.value,
            TruthClass.NEGATIVE.value,
            TruthClass.BORDERLINE.value,
        }
        if set(self.minimum_scoreable_per_role_pre_split) != required_roles:
            raise ValueError("sample-size rule must cover positive/negative/borderline roles")
        if set(self.observed_scoreable_per_role) != required_roles:
            raise ValueError("sample-size observation must cover positive/negative/borderline roles")
        if set(self.required_additional_scoreable_per_role) != required_roles:
            raise ValueError("sample-size deficit must cover positive/negative/borderline roles")
        if any(v < 2 for v in self.minimum_scoreable_per_role_pre_split.values()):
            raise ValueError("each role needs at least one DEV and one HELD_OUT slot")
        if any(v < 0 for v in self.observed_scoreable_per_role.values()):
            raise ValueError("observed scoreable counts cannot be negative")
        if any(v < 0 for v in self.required_additional_scoreable_per_role.values()):
            raise ValueError("sample-size deficits cannot be negative")
        expected_deficit = {
            role: max(
                0,
                self.minimum_scoreable_per_role_pre_split[role]
                - self.observed_scoreable_per_role[role],
            )
            for role in required_roles
        }
        if dict(self.required_additional_scoreable_per_role) != expected_deficit:
            raise ValueError("sample-size deficit does not match rule and observations")
        should_satisfy = all(v == 0 for v in expected_deficit.values())
        if should_satisfy != (self.state == SampleSizeAssessmentState.SATISFIED.value):
            raise ValueError("sample-size assessment state disagrees with deficits")
        if not self.rationale or not self.evidence_refs or not self.interpretation_constraints:
            raise ValueError("sample-size assessment requires rationale, evidence, and constraints")


def load_sample_size_assessment(path: Path) -> SampleSizeAssessment:
    return SampleSizeAssessment.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )


def scoreable_counts_by_role(
    records: tuple[MaterialCoverageRecord, ...],
) -> Mapping[str, int]:
    roles = {
        TruthClass.POSITIVE.value: 0,
        TruthClass.NEGATIVE.value: 0,
        TruthClass.BORDERLINE.value: 0,
    }
    for record in records:
        if record.proposed_role not in roles:
            continue
        if (
            record.truth_bundle_availability
            == TruthBundleAvailability.CURATED_FOR_B2.value
            and record.scorable_stages
        ):
            roles[record.proposed_role] += 1
    return roles
