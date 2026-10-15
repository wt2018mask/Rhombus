"""0179 scientific anti-promotion fixture using actual published method/0178 labels."""
import copy
import json
from pathlib import Path
import pytest
from scripts.science import physical_sample_join_eligibility_0179 as m

ROOT=Path(__file__).resolve().parents[1]
def original():
    return json.loads((ROOT/"data/development/phase3_0179_pellet_bridge_source_v1.json").read_text(encoding="utf-8"))

def test_exact_original_XRD_EIS_overlap_is_below_physical_same_specimen_evidence():
    r=m.audit(original())
    assert [x["treatment"] for x in r["matched_conditions_only"]]==["Pristine","2 Li-OPA"]
    assert all(x["join_level"]=="TREATMENT_ONLY" for x in r["matched_conditions_only"])
    assert r["unique_independently_attested_pellet_pairs"]==0
    assert r["XRD_9_percent_RH_4h_has_exact_matching_EIS_exposure_time"] is False
    assert r["source_specific_raw_XRD_EIS_individual_pellet_IDs"] is None
    assert r["scientific_GO"] is False
    assert all(r[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))

@pytest.mark.parametrize("mutation",[
    lambda s:s.update(actual_0178_source_receipt_sha256="0"*64),
    lambda s:s.update(actual_original_supporting_workbook_sha256="0"*64),
    lambda s:s.update(article_DOI="10.0000/fake"),
    lambda s:s["actual_raw_source_text_groups"][1]["source_cells"].update(O1="another pellet"),
    lambda s:s["actual_raw_source_text_groups"][2]["source_cells"].update(E3="2 OPA"),
    lambda s:s["actual_raw_source_text_groups"][2].update(exposure_hours=[12,24]),
    lambda s:s.update(lab_signed_pellet_EIS_XRD_join_received=True),
    lambda s:s.update(independent_external_evaluator_signed_roster_received=True),
    lambda s:s.update(validated_exact_eis_pellet_to_xrd_specimen_pairs=2),
    lambda s:s["author_reported_EIS_method_not_pellet_specific"].update(approx_thickness_mm=0.9),
    lambda s:s.update(scientific_GO=True),
])
def test_false_same_physical_pellet_proof_and_source_drifts_fail_closed(mutation):
    o=original();mutation(o)
    with pytest.raises(ValueError):m.audit(o)
