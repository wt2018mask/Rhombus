"""0151-B synthetic CIF occupancy, phase and original public TEST embargo tests."""
import copy
import hashlib
import json

import numpy as np
import pytest
from pymatgen.core import Structure, Lattice

from tests.test_phase3_obelix_benchmark_intake import checkout
from scripts.science.obelix_original_cif_occupancy_0151 import (
    _source_verified_cif, _parsed_crystal_status,
    analyze_pinned_train_cif_cohort, run_original_cif_audit,
)
from rhombus.qualification.obelix_benchmark_intake import build_obelix_benchmark_intake


def ordered_cif():
    return Structure(Lattice.cubic(6), ["Li", "O"], [[0, 0, 0], [0.5, 0.5, 0.5]]).to(fmt="cif").encode()


def disordered_cif():
    return Structure(Lattice.cubic(6), [{"Li": 0.6, "Na": 0.4}, "O"],
                     [[0, 0, 0], [0.5, 0.5, 0.5]]).to(fmt="cif").encode()


def sample(tmp_path, *, disorder=False, test_broken=True):
    return checkout(tmp_path,
        cifs={"a.cif": disordered_cif() if disorder else ordered_cif(),
              "c.cif": b"ERROR! MALFORMED OFFICIAL TEST ORIGINAL CIF" if test_broken else ordered_cif()})


def test_original_public_test_cif_never_read_or_parsed(tmp_path):
    root, commit=sample(tmp_path)
    result=analyze_pinned_train_cif_cohort(root,expected_commit=commit,require_official=False)
    assert result["original_all_source_rows"]==4
    assert result["original_official_train_rows"]==3
    assert result["original_official_test_rows_reserved_unparsed"]==1
    assert result["train_exact_match_source_CIF_count"]==1
    assert result["train_close_match_CIF_count_NOT_phase_qualified"]==0
    assert result["train_no_matched_CIF_count"]==2
    assert result["reproduced_0145_train_model_eligible_ORDERED_source_structures"]==1
    assert result["source_paper_review_queue_count"]==1
    assert result["primary_source_papers_actually_read"]==0
    assert result["new_independent_physical_materials_qualified"]==0
    assert result["scientific_qualification_authorized"] is False
    assert result["P0_01_status"]==result["P0_02_status"]==result["P0_03_status"]=="BLOCKED"
    q=result["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"][0]
    assert q["source_entry_id"]=="a"
    assert q["source_dois"]==["10.1234/alpha"]
    assert q["original_cif_sha256"]==hashlib.sha256(ordered_cif()).hexdigest()
    assert q["paper_review_status"]=="NOT_REVIEWED"
    assert "reported_ionic_conductivity_text" not in json.dumps(result)
    assert "MALFORMED OFFICIAL TEST" not in json.dumps(result)
    with pytest.raises(ValueError, match="official"):
        analyze_pinned_train_cif_cohort(root,expected_commit=commit,require_official=True)


def test_fractional_occupancy_is_not_rounded_to_ordered_mace(tmp_path):
    root, commit=sample(tmp_path,disorder=True)
    result=analyze_pinned_train_cif_cohort(root,expected_commit=commit,require_official=False)
    assert result["train_structures_containing_fractional_occupancy_sites"]==1
    assert result["train_site_count_total_fractional"]>=1
    assert result["train_CIF_parse_category_counts"]["DISORDERED_OCCUPANCY_PRESERVED_NO_MODEL"]==1
    assert result["reproduced_0145_train_model_eligible_ORDERED_source_structures"]==0
    assert result["partial_occupancy_rounded_into_ordered_model"] is False
    assert result["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"][0]["fractional_site_count"]>=1


def test_true_original_close_match_must_not_qualify_as_phase(tmp_path):
    root, commit=checkout(tmp_path,train=["a","b","c"],test=["d"],
                         cifs={"a.cif":ordered_cif(),"c.cif":disordered_cif()})
    result=analyze_pinned_train_cif_cohort(root,expected_commit=commit,require_official=False)
    assert result["train_exact_match_source_CIF_count"]==1
    assert result["train_close_match_CIF_count_NOT_phase_qualified"]==1
    assert result["train_CIF_parse_category_counts"]["DISORDERED_OCCUPANCY_PRESERVED_NO_MODEL"]==1
    assert result["source_paper_review_queue_count"]==1
    assert all(x["original_cif_match"]=="Match" for x in
               result["review_queue_first_party_public_DOI_and_source_CIF_links_ONLY"])
    assert result["geometry_CIF_close_match_promoted_to_exact_phase"] is False


def test_ordered_partial_vacancy_and_mixed_species_diagnostics():
    row={"reported_composition":"LiO"}
    raw=Structure(Lattice.cubic(6),[{"Li":0.6},"O"],
                  [[0,0,0],[0.5,0.5,0.5]]).to(fmt="cif").encode()
    r=_parsed_crystal_status(raw,row)
    assert r["status"]=="DISORDERED_OCCUPANCY_PRESERVED_NO_MODEL"
    assert r["partial_vacancy_sites"]>=1
    assert r["fractional_sites"]>=1


def test_sha_source_corruption_never_counted_as_science(tmp_path):
    root,commit=sample(tmp_path)
    records,_=build_obelix_benchmark_intake(root,expected_commit=commit)
    first=records[0]
    wrong=dict(first);wrong["cif_content_sha256"]="0"*64
    with pytest.raises(ValueError,match="SHA256"):
        _source_verified_cif(root,wrong)
    wrong=dict(first);wrong["official_split"]="TEST"
    with pytest.raises(ValueError,match="TEST"):
        _source_verified_cif(root,wrong)
    wrong=dict(first);wrong["cif_relative_path"]="../../etc/passwd"
    with pytest.raises(ValueError,match="approved"):
        _source_verified_cif(root,wrong)


def test_original_source_output_atomic_and_immutable(tmp_path):
    root,commit=sample(tmp_path)
    path=tmp_path/"new_0151_output"
    r=run_original_cif_audit(root,path,expected_commit=commit,require_official=False)
    assert json.loads((path/"cif_occupancy_source_audit_aggregate.json").read_text())==r
    with pytest.raises(ValueError,match="new"):
        run_original_cif_audit(root,path,expected_commit=commit,require_official=False)
    with pytest.raises(ValueError,match="output"):
        run_original_cif_audit(root,root/"not_allowed",expected_commit=commit,require_official=False)


def test_corrupt_exact_source_parser_counted_not_authenticated(tmp_path):
    root,commit=checkout(tmp_path,cifs={"a.cif":b"invalid CIF not crystal","c.cif":b"TEST never parsed"})
    r=analyze_pinned_train_cif_cohort(root,expected_commit=commit,require_official=False)
    assert r["train_CIF_parse_category_counts"]["CIF_PARSE_FAILED"]==1
    assert r["reproduced_0145_train_model_eligible_ORDERED_source_structures"]==0
    assert r["source_paper_review_queue_count"]==0
    assert r["new_independent_physical_materials_qualified"]==0


def test_no_source_physical_qualification_even_with_valid_crystal(tmp_path):
    root,commit=sample(tmp_path)
    r=analyze_pinned_train_cif_cohort(root,expected_commit=commit,require_official=False)
    assert r["specimen_phase_and_exact_measurement_temperature_verified"]==0
    assert r["primary_source_papers_actually_read"]==0
    assert not r["MD_or_ionic_transport_computed_this_checkpoint"]
    assert "experimental_source_temperature_K" not in r
