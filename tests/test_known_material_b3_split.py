"""B3 split-authorization transition tests."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from rudeus.science.known_material_b3_split import authorize_b3_split
from rudeus.science.known_material_sample_size import (
    SampleSizeAssessmentState,
    load_sample_size_assessment,
)
from tests.test_known_material_b2_coverage import canonical_audit


ROOT = Path("data/benchmarks/known_material")


def test_canonical_b2_state_authorizes_b3_split_construction_only():
    audit = canonical_audit()
    sample_size = load_sample_size_assessment(ROOT / "sample_size_assessment_v1.json")
    authorization = authorize_b3_split(audit, sample_size)

    assert audit.global_blockers == ()
    assert audit.b3_split_authorized is False
    assert authorization.authorized is True
    assert authorization.split_membership_assigned is False
    assert authorization.b2_audit_hash == audit.content_hash
    assert authorization.sample_size_assessment_hash == sample_size.content_hash


def test_b3_authorization_rejects_any_b2_blocker():
    audit = replace(canonical_audit(), global_blockers=("SYNTHETIC_BLOCKER",))
    sample_size = load_sample_size_assessment(ROOT / "sample_size_assessment_v1.json")
    with pytest.raises(ValueError, match="B2 blockers remain"):
        authorize_b3_split(audit, sample_size)


def test_b3_authorization_rejects_unsatisfied_role_counts():
    audit = canonical_audit()
    sample_size = load_sample_size_assessment(ROOT / "sample_size_assessment_v1.json")
    sample_size = replace(
        sample_size,
        state=SampleSizeAssessmentState.UNSATISFIED.value,
        required_additional_scoreable_per_role={
            "POSITIVE": 1,
            "NEGATIVE": 0,
            "BORDERLINE": 0,
        },
        observed_scoreable_per_role={
            "POSITIVE": 1,
            "NEGATIVE": 2,
            "BORDERLINE": 2,
        },
    )
    with pytest.raises(ValueError, match="satisfied pre-split role counts"):
        authorize_b3_split(audit, sample_size)
