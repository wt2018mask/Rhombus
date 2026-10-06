from rudeus.science.known_material_b5_p0_material_semantics import (
    B5P0MaterialAssessment,
)
from rudeus.science.known_material_b5_p1_entry import (
    P1EntryDisposition,
    decide_p1_entry,
)


def assessment(disposition: str):
    return B5P0MaterialAssessment(
        semantics_version="known-material-b5-p0-material-semantics-v1",
        material_key="m",
        representation_mode="DIRECT",
        component_count=1,
        disposition=disposition,
        applicable_failed_checks=(),
        unsupported_checks=(),
        unresolved_checks=(),
        execution_error_count=0,
        source_observation_hashes=("1" * 64,),
        qualification_evidence_authorized=False,
        production_search_authorized=False,
    )


def test_plausible_p0_is_p1_eligible():
    result = decide_p1_entry(assessment("PLAUSIBLE"))
    assert result.p1_entry_disposition == P1EntryDisposition.ELIGIBLE.value
    assert result.p1_execution_authorized is True


def test_fail_p0_is_blocked():
    item = assessment("FAIL")
    item = B5P0MaterialAssessment(
        **{
            **item.__dict__,
            "applicable_failed_checks": ("geometry",),
        }
    )
    result = decide_p1_entry(item)
    assert result.p1_entry_disposition == P1EntryDisposition.BLOCKED_P0_FAIL.value
    assert result.p1_execution_authorized is False


def test_indeterminate_p0_is_held_not_promoted():
    item = assessment("INDETERMINATE")
    item = B5P0MaterialAssessment(
        **{
            **item.__dict__,
            "unsupported_checks": ("neutrality",),
        }
    )
    result = decide_p1_entry(item)
    assert result.p1_entry_disposition == P1EntryDisposition.HELD_P0_INDETERMINATE.value
    assert result.p1_execution_authorized is False
