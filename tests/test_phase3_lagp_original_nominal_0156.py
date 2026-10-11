"""0156 source-family nominal versus refined x and no false specimen promotion."""
import pytest
from scripts.science import obelix_lagp_nominal_series_0156 as m

@pytest.mark.parametrize("name,x",[
 ("lagp-1.2.cif",0.2),("folder/lagp-1.5.cif",0.5),
 ("lagp-1.8.cif",0.8),("lgp-1.0.cif",0.0)])
def test_original_filename_nominal_labels(name,x):
    assert m.nominal_x(name)==x

@pytest.mark.parametrize("name",["lagp-1.2-guess.cif","lagp-x0.2.cif","lagp-1.5.pdf","lagp-2.5.cif"])
def test_non_original_filename_never_guessed(name):
    with pytest.raises(ValueError):
        m.nominal_x(name)

def test_refined_x_is_not_nominal_x():
    a=m.refined_x("Li7.44Al1.452Ge10.548P18O72")
    b=m.refined_x("Li8.868Al2.88Ge9.12P18O72")
    assert (a["Al"],a["Li"],a["Ge"])==(0.242,0.24,0.242)
    assert (b["Al"],b["Li"],b["Ge"])==(0.48,0.478,0.48)

def test_wrong_chemistry_rejected():
    with pytest.raises(ValueError):
        m.refined_x("Li2O")

def artifact_stub():
    return {
     "structure_pair_attempts":16,
     "exact_match_original_TRAIN_rows_reexamined":2,
     "publisher_original_SI_CIF_members_reexamined":8,
     "original_public_TEST_rows_reserved_unread":121,
     "independent_experimental_specimens_verified":0,
     "scientific_GO":False,
     "source_records":[{"source_entry_id":id,
       "reduced_formula":"Li7.44Al1.452Ge10.548P18O72" if id=="0fh" else "Li8.868Al2.88Ge9.12P18O72"} for id in m.MATCHES],
     "publisher_CIF_records":[{"cif_sha256":pair[1],
       "reduced_formula":"Li7.44Al1.452Ge10.548P18O72" if id=="0fh" else "Li8.868Al2.88Ge9.12P18O72"} for id,pair in m.MATCHES.items()],
     "pair_diagnostics":[{"source_train_entry_id":id,
       "source_cif_sha256":pair[0],"publisher_cif_sha256":pair[1],
       "geometry_equivalent_heuristic":True,"composition_compatible_0p02_diagnostic":True}
       for id,pair in m.MATCHES.items()]
    }

def test_real_hash_nominal_binding_cannot_qualify_experiment():
    a=artifact_stub()
    names={m.MATCHES["0fh"][1]:"lagp-1.2.cif",
           m.MATCHES["1dm"][1]:"lagp-1.6.cif"}
    out=m.assign_publisher_nominal_structure_labels(a,names)
    assert [(x["OBELiX_TRAIN_entry"],x["CIF_filename_nominal_series_x"]) for x in out]==[("0fh",0.2),("1dm",0.6)]
    assert out[0]["publisher_Rietveld_refined_x_Al"]==0.242
    assert out[1]["publisher_Rietveld_refined_x_Al"]==0.48
    assert all(x["original_EXPERIMENTAL_SPECIMEN_PHASE_MATCH"]=="NOT_ADJUDICATED" for x in out)
    assert all(x["original_measured_temperature_K"] is None for x in out)
    assert all(x["original_measured_bulk_total_conductivity"] is None for x in out)

def test_digest_drift_or_test_leak_fails_closed():
    a=artifact_stub()
    a["pair_diagnostics"][0]["publisher_cif_sha256"]="0"*64
    with pytest.raises(ValueError,match="identity drift"):
        m.assign_publisher_nominal_structure_labels(a,{})
    a=artifact_stub()
    a["original_public_TEST_rows_reserved_unread"]=120
    with pytest.raises(ValueError,match="unqualified"):
        m.assign_publisher_nominal_structure_labels(a,{})
