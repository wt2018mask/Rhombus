"""B2 sample-size / split-feasibility tests."""
from pathlib import Path

from rudeus.science.known_material_sample_size import (
    SAMPLE_SIZE_ASSESSMENT_VERSION,
    SampleSizeAssessmentState,
    load_sample_size_assessment,
)

ROOT = Path("data/benchmarks/known_material")


def test_canonical_sample_size_assessment_is_explicitly_unsatisfied():
    assessment = load_sample_size_assessment(
        ROOT / "sample_size_assessment_v1.json"
    )
    assert assessment.assessment_version == SAMPLE_SIZE_ASSESSMENT_VERSION
    assert assessment.state == SampleSizeAssessmentState.UNSATISFIED.value
    assert assessment.minimum_scoreable_per_role_pre_split == {
        "POSITIVE": 2,
        "NEGATIVE": 1,
        "BORDERLINE": 2,
    }
    assert assessment.observed_scoreable_per_role == {
        "POSITIVE": 1,
        "NEGATIVE": 1,
        "BORDERLINE": 0,
    }
    assert assessment.required_additional_scoreable_per_role == {
        "POSITIVE": 1,
        "NEGATIVE": 2,
        "BORDERLINE": 2,
    }


def test_sample_size_assessment_does_not_claim_b6_thresholds_or_independence():
    assessment = load_sample_size_assessment(
        ROOT / "sample_size_assessment_v1.json"
    )
    joined = " ".join(assessment.interpretation_constraints).lower()
    assert "not a b6 qualification threshold" in joined
    assert "no sensitivity, specificity, or power claim is authorized" in joined
    assert "do not create independent benchmark materials" in joined
