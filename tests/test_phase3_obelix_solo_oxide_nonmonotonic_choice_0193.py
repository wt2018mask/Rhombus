import pytest
from scripts.science.obelix_solo_oxide_nonmonotonic_choice_0193 import SOURCES,classify,report

def test_original_2018_rejects_always_hotter():
    r=classify(SOURCES[0])
    assert not r["admitted"] and r["diagnostic_eligible"] and r["nonmonotonic"]
    assert r["max_temperature_C"]==1220
    assert r["observed_best_temperature_C"]==1210
    assert r["trivial_hotter_top1_correct"] is False

def test_original_2020_tied_maximum_does_not_falsely_claim_win():
    r=classify(SOURCES[1])
    assert not r["admitted"] and r["diagnostic_eligible"] and r["nonmonotonic"] is False
    assert r["trivial_hotter_top1_correct"] is None

def test_2022_room_temperature_not_admitted_as_exact_25C():
    r=classify(SOURCES[2])
    assert not r["admitted"] and r["reason"]=="NOT_EXACT_25C"

def test_fail_closed_unverified_temperature_and_pairing():
    for change in ({"exact_25C":None},{"sample_names":["x","x"]},
                   {"best_sample":"not-a-source-sample"},{"temp_C":[1500,1200,1200,1200,1200]}):
        s=dict(SOURCES[0],**change)
        with pytest.raises(ValueError):classify(s)

def test_scientific_go_never_from_retrospective_source_metadata():
    d=report()
    assert d["diagnostic_nonmonotonic_source_count"]==1
    assert d["new_independent_unexposed_DOIs"]==0
    assert d["verdict"]=="INCONCLUSIVE"
    assert not d["scientific_GO"] and not d["production_enabled"]
    assert all(d[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))

@pytest.mark.parametrize("change", [
    {"doi":"10.0000/fabricated"},
    {"sample_names":["fake1","fake2","fake3","fake4","fake5"],"best_sample":"fake4"},
    {"temp_C":[1220,1210,1200,1150,1100]},
    {"best_sample":"LLZALO-1"},
    {"evidence":"room temperature claimed to equal exactly 25 C","exact_25C":True},
])
def test_caller_assertions_never_authenticate_source(change):
    row=classify(dict(SOURCES[0],**change))
    assert row["admitted"] is False
    assert row["source_authentication"]=="NOT_PERFORMED"

def test_empty_report_labels_historical_assertions():
    d=report([])
    assert d["0191_RSC_process_model_wrong_choice"]
    assert d["historical_assertions_provenance"]=="HISTORICAL_RECORD_NOT_RECOMPUTED_FROM_INPUT"
    assert d["source_authentication"]=="NOT_PERFORMED"
