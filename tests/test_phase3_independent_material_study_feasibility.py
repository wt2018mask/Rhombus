"""Adversarial material-level design: precision assumptions are not evidence."""
import copy
import json
import math
from statistics import NormalDist

import pytest

from scripts.science.independent_material_study_feasibility import (
    COHORT, ENDPOINT, IID_DESIGN, NONIID_DESIGN, SCHEMA, UNIT,
    _maximum_wilson_half_width, plan_independent_material_study, main,
)


def request(**updates):
    data = {
        "schema_version": SCHEMA,
        "unit": UNIT,
        "cohort_source": COHORT,
        "sampling_design": IID_DESIGN,
        "endpoint": ENDPOINT,
        "confidence_level": 0.95,
        "maximum_wilson_half_width": 0.10,
        "prospective_pre_enrollment_nonacquisition_fraction": 0.20,
        "post_enrollment_failures_count_in_denominator": True,
    }
    data.update(updates)
    return data


def test_worst_case_95pct_10pct_20pct_shortfall_is_93_and_117():
    r = plan_independent_material_study(request())
    assert r["independent_materials_needed_if_IID"] == 93
    assert r["prospective_minimum_recruitment_if_IID"] == 117
    assert r["worst_case_Wilson_half_width_if_IID"] <= 0.1
    assert r["actual_independent_material_sample_count_authenticated"] is None
    assert r["real_external_blind_material_roster_supplied"] is False
    assert r["external_steward_authentication_present"] is False
    assert r["scientific_release_authorized"] is False
    assert r["P0_01_status"] == "BLOCKED"
    assert r["P0_02_status"] == "BLOCKED"
    assert r["P0_03_status"] == "BLOCKED"
    assert r["plan_status"] == "PLAN_ONLY_NOT_EVIDENCE"


def test_95pct_5pct_requires_381_materials_not_six_legacy_materials():
    r = plan_independent_material_study(
        request(maximum_wilson_half_width=0.05,
                prospective_pre_enrollment_nonacquisition_fraction=0.0))
    assert r["independent_materials_needed_if_IID"] == 381
    assert r["prospective_minimum_recruitment_if_IID"] == 381
    assert r["public_OBELiX_TEST_and_old_B3_not_new_blind_materials"] is True
    assert r["repeated_trajectories_or_source_rows_not_independent_materials"] is True
    assert r["new_materials_scientifically_qualified"] == 0


@pytest.mark.parametrize("width,confidence", [
    (0.1, 0.95), (0.05, 0.95), (0.03, 0.99),
    (0.15, 0.80), (0.01, 0.90),
])
def test_minimum_is_numerically_exact_under_worst_case_wilson(width, confidence):
    r = plan_independent_material_study(
        request(maximum_wilson_half_width=width, confidence_level=confidence,
                prospective_pre_enrollment_nonacquisition_fraction=0.0))
    n = r["independent_materials_needed_if_IID"]
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    assert _maximum_wilson_half_width(n, z) <= width
    if n > 1:
        assert _maximum_wilson_half_width(n - 1, z) > width


@pytest.mark.parametrize("proportion", [0, 0.1, 0.2, 0.3, 0.5])
def test_prospective_pre_enrollment_shortfall_budget_only(proportion):
    r = plan_independent_material_study(
        request(prospective_pre_enrollment_nonacquisition_fraction=proportion))
    n, m = (r["independent_materials_needed_if_IID"],
            r["prospective_minimum_recruitment_if_IID"])
    assert (m * (1 - proportion)) >= n
    assert m == math.ceil(n/(1-proportion))
    assert r["post_enrollment_model_failures_abstentions_unknowns_count_as_outcomes"]


def test_known_role_quotas_and_dependent_materials_cannot_claim_iid_precision():
    r = plan_independent_material_study(request(sampling_design=NONIID_DESIGN))
    assert r["plan_status"] == "BLOCKED_NON_IID"
    assert r["statistical_precision_method"] == "NOT_DEFENSIBLE_FOR_NON_IID"
    assert r["independent_materials_needed_if_IID"] is None
    assert r["worst_case_Wilson_half_width_if_IID"] is None
    assert r["prospective_minimum_recruitment_if_IID"] is None
    assert r["scientific_release_authorized"] is False


@pytest.mark.parametrize("changes", [
    {"schema_version": "unexpected"},
    {"unit": "TRAJECTORY"},
    {"cohort_source": "PUBLIC_OBELIX_TEST"},
    {"cohort_source": "SIX_OLD_B3"},
    {"sampling_design": "SELF_SELECTED_COHORT"},
    {"endpoint": "ACCURACY_ONLY_ON_SUCCESSFUL_ATTEMPTS"},
    {"post_enrollment_failures_count_in_denominator": False},
    {"post_enrollment_failures_count_in_denominator": 1},
    {"confidence_level": True},
    {"confidence_level": 0.5},
    {"confidence_level": 1.0},
    {"confidence_level": math.inf},
    {"maximum_wilson_half_width": float("nan")},
    {"maximum_wilson_half_width": 0},
    {"maximum_wilson_half_width": 0.25},
    {"prospective_pre_enrollment_nonacquisition_fraction": -0.01},
    {"prospective_pre_enrollment_nonacquisition_fraction": 0.75},
    {"prospective_pre_enrollment_nonacquisition_fraction": "0.2"},
    {"original_material_identifiers": ["PRIVATE_SAMPLE_1"]},
])
def test_no_scientifically_invalid_plan_can_sneak_through(changes):
    with pytest.raises(ValueError):
        plan_independent_material_study(request(**changes))


def test_wilson_assumption_is_not_statistical_power_or_classwise_precision():
    r = plan_independent_material_study(request())
    assert r["precision_target_only_NOT_statistical_power"] is True
    assert r["precision_for_subgroups_or_strata_not_established"] is True
    assert r["actual_precision_empirically_observed"] is False
    assert r["recruitment_target_achieved"] is False


def test_independent_source_identifiers_not_part_of_aggregate_receipt():
    r = plan_independent_material_study(request())
    text = json.dumps(r)
    for forbidden in ("PRIVATE_SAMPLE_1", "formula", "paper_doi", "key_material"):
        assert forbidden not in text


def test_cli_writes_new_aggregate_only_and_rejects_rewrite(tmp_path, capsys):
    source = tmp_path/"planned.json"
    source.write_text(json.dumps(request()))
    dest = tmp_path/"receipt"
    assert main(["--study-plan-json", str(source), "--output-dir", str(dest)]) == 0
    report = json.loads((dest/"prospective_material_feasibility.json").read_text())
    assert report["independent_materials_needed_if_IID"] == 93
    assert report["scientific_release_authorized"] is False
    with pytest.raises(SystemExit):
        main(["--study-plan-json", str(source), "--output-dir", str(dest)])


@pytest.mark.parametrize("invalid", [
    '{"confidence_level":0.95,"confidence_level":0.99}',
    '{"foo":NaN}',
    '{"foo":Infinity}',
    '{"not-an-object": [1, 2, 3]}',
    '{"schema_version": 0',
])
def test_cli_rejects_ambiguous_or_invalid_json(tmp_path, invalid):
    src = tmp_path/"plan.json"
    src.write_text(invalid)
    with pytest.raises(SystemExit):
        main(["--study-plan-json", str(src), "--output-dir", str(tmp_path/"out")])
    assert not (tmp_path/"out").exists()


def test_cli_rejects_oversized_input_and_symlink(tmp_path):
    src = tmp_path/"plan.json"
    src.write_bytes(b" " * 16385)
    with pytest.raises(SystemExit):
        main(["--study-plan-json", str(src), "--output-dir", str(tmp_path/"out")])
    src.write_text(json.dumps(request()))
    link = tmp_path/"alias"
    link.symlink_to(src)
    with pytest.raises(SystemExit):
        main(["--study-plan-json", str(link), "--output-dir", str(tmp_path/"out2")])
