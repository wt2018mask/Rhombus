"""Synthetic-only negative tests. No LiTraj reference targets or MLIP calls."""
from __future__ import annotations

from copy import deepcopy
import math

import pytest

from rhombus.benchmark.tier_a_selective_design import (
    FIXTURE_SCHEMA, REQUIRED_MODEL_IDS,
    make_decision_design, inspect_decision_design,
    summarize_synthetic_paired_decisions,
)
from tests.test_tier_a_budget_contract_0204 import ready_draft


ARMS = sorted(REQUIRED_MODEL_IDS)


def fixture():
    records=[]
    for edge,group in [("synthetic-a","CHEMSYS:Li-O"),("synthetic-b","CHEMSYS:Li-S"),
                       ("synthetic-c","CHEMSYS:Li-Al-O")]:
        for arm in ARMS:
            records.append({"edge_id":edge,"group_id":group,"arm_id":arm,
                            "decision":"ABSTAIN","run_outcome":"CONVERGED",
                            "severe_error":None,"cpu_seconds":2.0})
    return {"schema_version":FIXTURE_SCHEMA,"scope":"SYNTHETIC_ONLY_NO_REAL_LABELS",
            "model_arms":ARMS,
            "planned_edges":[{"edge_id":edge,"group_id":group} for edge,group in
                 [("synthetic-a","CHEMSYS:Li-O"),("synthetic-b","CHEMSYS:Li-S"),
                  ("synthetic-c","CHEMSYS:Li-Al-O")]],
            "rows":records}


def test_draft_is_bound_and_cannot_authorize_run():
    p=ready_draft()
    d=make_decision_design(p)
    review=inspect_decision_design(d,p)
    assert review["execution_authorized"] is False
    assert review["requires_independent_pre_registration"]
    assert len(review["owner_thresholds_missing"])==5
    assert d["result_qualification"]=="NOT_EVALUATED"
    assert d["decision_inputs"].startswith("PRE_REFERENCE_ONLY")


def test_draft_refuses_reference_or_authority_spoof():
    p=ready_draft(); d=make_decision_design(p)
    for field, bad in [("execution_authorized",True),("reference_access","OPEN"),
                       ("scientific_verdict","GO"),("model_overlap","CLEAR"),
                       ("budget_draft_sha256","0"*64)]:
        x=deepcopy(d);x[field]=bad
        with pytest.raises(ValueError,match="DESIGN_TAMPERING"):
            inspect_decision_design(x,p)
    x=deepcopy(d);x["em_dft"]=1.0
    with pytest.raises(ValueError,match="EXACT_FIELDS"):
        inspect_decision_design(x,p)


def test_owner_thresholds_unset_or_numeric_but_not_frozen():
    p=ready_draft();d=make_decision_design(p)
    d["owner_review"].update({"severe_error_delta_eV":0.1,
                              "maximum_false_accept_risk":0.05,
                              "minimum_coverage":0.20,
                              "uncertainty_threshold":0.4,
                              "escalation_cost_budget_cpu_seconds":100})
    s=inspect_decision_design(d,p)
    assert not s["owner_thresholds_missing"]
    assert s["status"]=="CANDIDATE_ONLY_NEVER_FROZEN"
    assert not s["execution_authorized"]
    for field,val in [("maximum_false_accept_risk",1), ("minimum_coverage",0),
                      ("severe_error_delta_eV",-1), ("uncertainty_threshold",float('nan')),
                      ("escalation_cost_budget_cpu_seconds",float('inf'))]:
        invalid=deepcopy(d);invalid["owner_review"][field]=val
        with pytest.raises(ValueError,match="INVALID_OWNER_THRESHOLD"):
            inspect_decision_design(invalid,p)


def test_all_abstain_risk_is_undefined_for_both():
    s=summarize_synthetic_paired_decisions(fixture())
    assert not s["can_claim_paired_superiority"]
    assert s["matched_coverage_decision_sets"]
    for arm in ARMS:
        row=s["model_summaries"][arm]
        assert row["planned_edges"]==3
        assert row["coverage_all_planned_edges"]==0
        assert row["risk_if_no_accepts"]=="UNDEFINED_NOT_ZERO"
        assert row["severe_error_fraction_accepted_edges"] is None
        assert row["group_wilson_interval_DESCRIPTIVE_ONLY"] is None
        assert row["observed_cpu_seconds_all_edges_including_failures"]==6


def test_group_is_statistical_unit_and_failures_stay_in_cost_denominator():
    f=fixture();r=f["rows"]
    r[0].update(decision="ACCEPT",severe_error=True)
    r[1].update(decision="ACCEPT",severe_error=False)
    r[2].update(decision="ACCEPT",severe_error=False)
    r[3].update(decision="ESCALATE",run_outcome="TIMEOUT",cpu_seconds=11)
    # Both arms retain three planned records, even when one timed out.
    s=summarize_synthetic_paired_decisions(f)
    m0=s["model_summaries"][ARMS[0]]
    m1=s["model_summaries"][ARMS[1]]
    assert m0["accepted_edges"]==2 and m0["accepted_chemsys_groups"]==2
    assert m0["groups_with_any_severe_error"]==1
    assert m0["group_any_severe_error_fraction"]==.5
    assert m0["coverage_all_planned_edges"]==2/3
    assert 0<=m0["group_wilson_interval_DESCRIPTIVE_ONLY"][0]<.5
    assert m1["failed_edges"]==1 and m1["escalated_edges"]==1
    assert m1["observed_cpu_seconds_all_edges_including_failures"]==15
    assert not s["matched_coverage_decision_sets"]
    assert not s["can_claim_paired_superiority"]


def test_failed_run_must_never_accept():
    f=fixture();f["rows"][0].update(decision="ACCEPT",run_outcome="NONCONVERGED",severe_error=False)
    with pytest.raises(ValueError,match="FAILED_RUN_CANNOT_BE_ACCEPTED"):
        summarize_synthetic_paired_decisions(f)


def test_duplicate_pair_cannot_inflate_denominator():
    f=fixture();f["rows"][1]=deepcopy(f["rows"][0])
    with pytest.raises(ValueError,match="DUPLICATE_PAIRED_EDGE_ARM"):
        summarize_synthetic_paired_decisions(f)


def test_mismatched_group_cannot_hide_leakage():
    f=fixture();f["rows"][1]["group_id"]="CHEMSYS:Li-Cl"
    with pytest.raises(ValueError,match="EDGE_GROUP_INCONSISTENCY"):
        summarize_synthetic_paired_decisions(f)


def test_synthetic_only_banned_real_target_fields_and_scope():
    f=fixture();f["rows"][0]["em_dft"]=.01
    with pytest.raises(ValueError,match="EXACT_FIELDS"):
        summarize_synthetic_paired_decisions(f)
    f=fixture();f["scope"]="HELDOUT_REAL_DATA"
    with pytest.raises(ValueError,match="REAL_DATA_SCORING_FORBIDDEN"):
        summarize_synthetic_paired_decisions(f)


def test_missing_arm_record_never_silently_disappears():
    f=fixture();f["rows"].pop()
    with pytest.raises(ValueError,match="INVALID_SYNTHETIC_PAIR_COUNT"):
        summarize_synthetic_paired_decisions(f)
    f=fixture();f["rows"]=[x for x in f["rows"] if x["edge_id"]!="synthetic-c"]
    with pytest.raises(ValueError,match="MISSING_PAIRED_ARM_EDGE_OR_UNREPORTED_FAILURE"):
        summarize_synthetic_paired_decisions(f)


def test_synthetic_severity_allowed_only_on_accepted():
    f=fixture();f["rows"][0]["severe_error"]=False
    with pytest.raises(ValueError,match="SYNTHETIC_SEVERITY_ONLY_FOR_ACCEPTED"):
        summarize_synthetic_paired_decisions(f)
    f=fixture();f["rows"][0]["decision"]="ACCEPT"
    with pytest.raises(ValueError,match="SYNTHETIC_SEVERITY_ONLY_FOR_ACCEPTED"):
        summarize_synthetic_paired_decisions(f)


def test_nan_inf_negative_costs_are_invalid():
    for cost in (-1,float('nan'),float('inf'),True):
        f=fixture();f["rows"][0]["cpu_seconds"]=cost
        with pytest.raises(ValueError,match="INVALID_SYNTHETIC_COST"):
            summarize_synthetic_paired_decisions(f)


def test_model_role_substitution_rejected():
    f=fixture();f["model_arms"]=[ARMS[0],"FAKE_MODEL"]
    with pytest.raises(ValueError,match="INCORRECT_PAIRED_MODEL_ROLES"):
        summarize_synthetic_paired_decisions(f)


def test_report_makes_no_independence_or_real_science_claim():
    f=fixture()
    s=summarize_synthetic_paired_decisions(f)
    assert s["group_intervals_not_independent_certification"]
    assert s["chemistry_source_prototype_independence"]=="UNKNOWN"
    assert s["pretrained_model_overlap"]=="UNKNOWN"
    assert s["scientific_verdict"]=="SCIENTIFIC_NO_GO_ABSTAIN"


def test_insufficient_independent_chemical_groups_rejected():
    f=fixture()
    for row in f["rows"]:row["group_id"]="CHEMSYS:Li-O"
    for row in f["planned_edges"]:row["group_id"]="CHEMSYS:Li-O"
    with pytest.raises(ValueError,match="INSUFFICIENT"):
        summarize_synthetic_paired_decisions(f)


def test_new_draft_cli_reproducible_no_overwrite(tmp_path):
    import json
    from scripts.benchmark.prepare_tier_a_selective_design_0205 import main
    budget = tmp_path/'budget.json'
    budget.write_text(json.dumps(ready_draft()), encoding='utf-8')
    out = tmp_path/'new-output'
    assert main(['--budget-draft', str(budget), '--out-dir', str(out)]) == 0
    result = json.loads((out/'tier_a_selective_decision_NON_EXECUTABLE.json').read_text())
    assert result['execution_authorized'] is False
    assert result['owner_review']['severe_error_delta_eV'] is None
    assert not any(k in result for k in ('em_dft', 'target', 'predictions'))
    with pytest.raises(ValueError, match='OUTPUT_MUST_BE_NEW'):
        main(['--budget-draft',str(budget),'--out-dir',str(out)])
    out2=tmp_path/'second'
    assert main(['--budget-draft',str(budget),'--out-dir',str(out2)])==0
    for name in ('tier_a_selective_decision_NON_EXECUTABLE.json',
                 'tier_a_selective_design_inspection.json'):
        assert (out/name).read_bytes()==(out2/name).read_bytes()


def test_cli_malformed_and_forbidden_target_failed_closed(tmp_path):
    import json
    from scripts.benchmark.prepare_tier_a_selective_design_0205 import main
    b=tmp_path/'budget.json';o=tmp_path/'out'
    bad=ready_draft();bad['em_dft']=[0.1]
    b.write_text(json.dumps(bad),encoding='utf-8')
    with pytest.raises(ValueError):
        main(['--budget-draft',str(b),'--out-dir',str(o)])
    assert not o.exists()
    b.write_text('{"bogus":1,"bogus":2}',encoding='utf-8')
    with pytest.raises(ValueError,match='DUPLICATE_JSON_KEY'):
        main(['--budget-draft',str(b),'--out-dir',str(o)])
    assert not o.exists()
